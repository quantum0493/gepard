"""Definition of theory frameworks."""

# from joblib import Parallel, delayed
from numpy import array, ndarray, sqrt
from scipy.stats import scoreatpercentile

from . import data, eff, gpd, model, quadrature

NCPU = 23  # how many CPUs to use in parallel


class Theory(object):
    """Class of theory frameworks for calculation of observables.

    This is a base class for a complete theory framework.
    It implements the generic routines for calculation of
    observables and uncertainty propagation.
    """

    def __init__(self, **kwargs) -> None:
        """This init is guaranteed to run.

        Args:
            name: short unique model name
            texname: TeX model name for (e.g. for plot annotation)
            description: longer description of the model
        """
        self.name = kwargs.setdefault('name', 'N/A')
        self.texname = kwargs.setdefault('texname', self.name)
        self.description = kwargs.setdefault('description', 'N/A')
        self.model = self       # to make old .m code work
        self.m = self       # to make old .m code work
        # print('theory.Theory init done.')
        # We do NOT call super().__init__ here because object class will
        # not accapt **kwargs. This means that Theory has to be the last
        # class in mro.

    def chisq_single(self, points: data.DataSet, asym: bool = False,
                     **kwargs) -> float:
        """Return total chi-square.

        Args:
            points: measurements with uncertainties, observable is
                named in `observable` attribute of each DataPoint,
                value is `val` and uncertainty is `err`.
            asym: if measurements provide asymmetric uncertainties
                `errplus` and `errminus`, this enables their usage
            observable (str): overrides `observable` of DataPoints

        Notes:
            If the theory or model provide uncertainties, they are ignored -
            only experimental uncertainties are taken into account.
           """
        allpulls = []
        for pt in points:
            diff = (self.predict(pt, observable=pt.observable, **kwargs) - pt.val)
            if asym:
                if diff > 0:
                    allpulls.append(diff/pt.errplus)
                else:
                    allpulls.append(diff/pt.errminus)
            else:
                allpulls.append(diff/pt.err)
        chi = sum(p*p for p in allpulls)  # equal to m.fval if minuit fit is done
        return chi

    def pull(self, pt: data.DataPoint):
        """Return pull of a single Datapoint."""
        return (self.predict(pt, observable=pt.observable) - pt.val) / pt.err

#     def chisq_para(self, points: DataSet, asym: bool = False,
#                    **kwargs) -> float:
#         """Return total chi-square - parallel version.
# 
#         Warning:
#             Cannot be used until underlying global Fortran variables can change
#             during session. (Like different kinematics of data points.)
#         """
#         allpulls = Parallel(n_jobs=NCPU)(delayed(self.pull)(pt) for pt in points)
#         chi = sum(p*p for p in allpulls)  # equal to m.fval if minuit fit is done
#         return chi

    chisq = chisq_single

    def predict(self, pt, uncertainty=False, **kwargs):
        """Give prediction for DataPoint pt.

        Args:
            pt: instance of DataPoint
            uncertainty: if available, produce tuple (mean, uncertainty)
            observable: string. Default is pt.observable. It is acceptable also
                        to pass CFF or x-space GPD as observable, e.g., observable = 'ImH'
            parameters: dictionary which will temporarily update model's one
            orig_conventions: give prediction using original conventions of
                              the given DataPoint (e.g. for plotting)
        """
        if 'observable' in kwargs:
            obs = kwargs['observable']
        else:
            obs = pt.observable

        if 'parameters' in kwargs:
            old = m.parameters.copy()
            self.parameters.update(kwargs['parameters'])

        fun = getattr(self, obs)

        if uncertainty:
            # We now do standard propagation of uncertainty from m to observable
            # using simplified procedure
            pars = self.free_parameters()
            var = 0
            dfdp = {}
            for p in pars:
                # calculating dfdp = derivative of observable w.r.t. parameter:
                h=sqrt(self.covariance[p,p])
                mem = self.parameters[p]
                self.parameters[p] = mem+h/2.
                up = fun(pt)
                self.parameters[p] = mem-h/2.
                down = fun(pt)
                self.parameters[p] = mem
                dfdp[p] = (up-down)/h
            for p1 in pars:
                for p2 in pars:
                    var += dfdp[p1]*self.covariance[p1,p2]*dfdp[p2]
            result = (fun(pt), sqrt(var))
        else:
            result = fun(pt)

        if 'parameters' in kwargs:
            # restore old values
            self.parameters.update(old)

        if kwargs.pop('orig_conventions', False):
            # express result in conventions of original datapoint
            try:
                result = (pt.orig_conventions(result[0]),) + result[1:]
            except (IndexError, TypeError):
                result = pt.orig_conventions(result)
        return result

# Photoproduction - select DVCS or DVMP

    def _XGAMMA_int(self, t, pt):
        """Same as _XGAMMA_DVCS_t/_XGAMMA_rho_t but with additional variable t
        to facilitate integration over it.

        """
        aux = []
        for t_single in t:
            pt.t = t_single
            if hasattr(pt, 'process') and pt.process == 'gammastarp2rho0p':
                res = self._XGAMMA_rho_t(pt)
            else:
                res = self._XGAMMA_DVCS_t(pt)
            del pt.t
            aux.append(res)
        return array(aux)


    def XGAMMA(self, pt):
        """Total gamma* DVCS or DVMP cross section.

        For DVMP, this calculates only longitudinal_gamma* part.
        If `pt` has no momentum transfer defined, it calculates
        total xs.

        """
        if 't' in pt or 'tm' in pt:
            # XGAMMA differential in momentum transfer t
            if hasattr(pt, 'process') and pt.process == 'gammastarp2rho0p':
                return self._XGAMMA_rho_t(pt)
            else:
                return self._XGAMMA_DVCS_t(pt)

        else:
            # total XGAMMA
            if 'tmmax' in pt:
                tmmax = pt.tmmax
            else:
                tmmax = 1.  # default -t cuttoff in GeV^2
            res = quadrature.tquadrature(lambda t: self._XGAMMA_int(t, pt), -tmmax, 0)
            return res
