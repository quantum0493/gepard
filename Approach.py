from IPython.Debugger import Tracer; debug_here = Tracer()

import copy, sys

from numpy import sin, cos, pi, sqrt, array, linspace
from scipy.special import gammainc

import utils, quadrature, Data
from constants import *

class Approach(object):
    """Class of approaches to calculation of observables.

    This is a base class and subclasses should implement
    various observables as methods. Instances of subclasses
    are instantiated with specific functions for modelling
    CFFs and FFs, so they contain complete algorithm for
    calculation of specific observable.

    Boolean variable 'optimization' (default is False) controls
    whether faster (but analytically more complicated) formulas
    are used. This is for development purposes only. When
    fitting optimization=True is better choice.

    Implemented subclases:  BMK, hotfixedBMK
    TODO: VGG, Guichon?
    """


    def __init__(self, m, optimization=False):
        """Initialize with m as instance of Model class."""
        self.model = m
        self.m = self.model  # shortcut
        self.optimization = optimization
        self.name = 'N/A'  # to be used as identifier in theory database
        self.description = 'N/A'  # something human-understandable

    def __repr__(self):
        return "<Theory: %s + %s at %s>" % utils.flatten(
                (str(self.__class__).split()[1][1:-2],
                  tuple(str(self.model).split()[::3])))

    def copy(self):
        """Return deep copy of itself."""
        return copy.deepcopy(self)

    def save(self, db):
        """Save theory to database."""
        db[self.name] = self

    def chisq(self, points, sigmas=False):
        """Return tuple (chi-square, d.o.f., probability). If the approach and model
           provide uncertainties, they are ignored - only experimental uncertainties
           are taken into account."""
        nfreepars=utils.npars(self.model)
        dof = len(points) - nfreepars
        allsigmas = [(self.predict(pt, observable=pt.yaxis) - pt.val) / pt.err for
                    pt in points]
        chi = sum(s*s for s in allsigmas)  # equal to m.fval if minuit fit is done
        fitprob = (1.-gammainc(dof/2., chi/2.)) # probability of this chi-sq
        if sigmas:
            return allsigmas
        else:
            return (chi, dof, fitprob)

    def scan(self, parname, points, npoints=5):
        """Scan chi-square dependence on single parameter."""
        mem = self.m.parameters[parname]
        chis = []
        for val in linspace(0.5*mem, 1.5 * mem, npoints):
            self.m.parameters[parname] = val
            self.m.ndparameters[self.m.parameter_names.index(parname)] = val
            chi, dof, fitprob = self.chisq(points)
            print '%s  ->  %s' % (val, chi)
        self.m.parameters[parname] = mem  # restore original value
        self.m.ndparameters[self.m.parameter_names.index(parname)] = mem


    def print_chisq(self, points, sigmas=False):
        """Pretty-print the chi-square."""
        if sigmas:
            print self.chisq(points, sigmas=True)
        print 'P(chi-square, d.o.f) = P(%1.2f, %2d) = %5.4f' % self.chisq(points)

    def predict(self, pt, error=False, **kwargs):
        """Give prediction for DataPoint pt.

        Keyword arguments:
        error - if available, produce tuple (mean, error)
        observable - string. Default is pt.yaxis
        parameters - dictionary which will update model's one

        """
        if kwargs.has_key('observable'):
            obs = kwargs['observable']
        else:
            obs = pt.yaxis

        if kwargs.has_key('parameters'):
            old = self.model.parameters.copy()
            self.model.parameters.update(kwargs['parameters'])
        #elif isinstance(self.model, Model.ComptonNeuralNets):
        #    # It is not training (which always uses 'parameters'), and
        #    # we are not asked for particular net (call would again come
        #    # with 'parameters'), so we want mean of all nets
        #    self.model.parameters['nnet'] = 'ALL'
        #    result = getattr(self, obs)(pt)
        #    if error:
        #        return (result.mean(), result.std())
        #    else:
        #        return result.mean()

        result = getattr(self, obs)(pt)

        if kwargs.has_key('parameters'):
            # restore old values
            self.model.parameters.update(old)

        return result


class BMK(Approach):
    """Implementation of formulas from hep-ph/0112108  (BMK)"""

    ### Kinematics ###
    # (implemented as static and class methods)

    def tmin(Q2, xB, eps2):
        """BMK Eq. (31)"""
        return -Q2 * ( 2. * (1.-xB)*(1. - sqrt(1.+eps2)) + eps2 ) / (
                4. * xB * (1.-xB) + eps2 )
    tmin = staticmethod(tmin)

    def K2(Q2, xB, t, y, eps2):
        """BMK Eq. (30)"""
        tm = BMK.tmin(Q2, xB, eps2)
        brace = sqrt(1.+eps2) + (4. * xB * (1.-xB) + eps2 ) / (
                4. * (1.-xB) ) * (t - tm) / Q2
        return -(t/Q2) * (1.-xB) * (1.-y-y*y*eps2/4.) * (
                1. - tm / t ) * brace
    K2 = staticmethod(K2)

    def J(Q2, xB, t, y, eps2):
        """BMK below Eq. (32)"""
        return (1.-y-y*eps2/2.) * (1. + t/Q2) - (1.-xB)*(2.-y)*t/Q2
    J = staticmethod(J)

    def r(Q2, xB, t, y, eps2):
        """DM's fitting notes, below Eq. (13)"""
        K = sqrt(BMK.K2(Q2, xB, t, y, eps2))
        brace = (2.-y)**2 * K / (1.-y) + (1./K)*(t/Q2)*(1.-y)*(2.-xB)
        return - (2.-y) / (2.-2.*y+y**2) * brace
    r = staticmethod(r)

    def P1P2(pt):
        """ Product of Bethe-Heitler propagators, Eq(32) """
        P1 = - ( BMK.J(pt.Q2, pt.xB, pt.t, pt.y, pt.eps2) + 2. * 
                sqrt(BMK.K2(pt.Q2, pt.xB, pt.t, pt.y, pt.eps2)) * cos(pt.phi) ) / (
                        pt.y * (1. + pt.eps2) )
        P2 = 1. + pt.t / pt.Q2  - P1
        return P1 * P2
    P1P2 = staticmethod(P1P2)

    def anintP1P2(pt):
        """ Analitical integral of \int P1 P2 d\phi """
        xB, Q2, t, y, eps2, K2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2, pt.K2
        brace = ( (1 - y - (1+eps2/2.) * y**2 * eps2/2.) * (1. + t/Q2)**2 +
                  2.*K2 - (1.-xB)*(2.-y)**2 * (1. + xB*t/Q2) * t/Q2 )
        return -2. * pi * brace / (1+eps2)**2 / y**2
    anintP1P2 = staticmethod(anintP1P2)

    def PreFacSigma(self, pt):
        """ Prefactor of 4-fold xs. Take prefactor in Eq(22) times 2\pi because of proton Phi integration
        and times y/Q2 because of dy -> dQ2. Convert to nanobarns."""
        return alpha**3 * pt.xB * pt.y**2 / (8. * pi * pt.Q2**2 * sqrt(1.+pt.eps2)) * GeV2nb

    def PreFacBH(self, pt):
        """ Prefactor from Eq. (25), without e^6 """
        return 1./(pt.xB**2 * pt.y**2 * (1.+pt.eps2)**2 * pt.t * pt.P1P2)

    def PreFacDVCS(self, pt):
        """ Prefactor from Eq. (26), without e^6 """
        return 1./(pt.y**2 * pt.Q2 )

    def PreFacINT(self, pt):
        """ Prefactor from Eq. (27), without e^6 """
        return 1./(pt.xB * pt.y**3 * pt.t * pt.P1P2)

    def w(self, pt):
        """ Weight factor removing BH propagators from INT and BH amplitudes. 
        It is normalized to \int_0^2pi w  2pi as in BMK. """
        return 2.*pi*pt.P1P2 / pt.intP1P2

    def to_conventions(pt):
        """Transform stuff into Approach's conventions."""
        ##  --- go to BMK conventions ----
        # C1. azimutal angle phi should be in radians ...
        if pt.has_key('phi'):
            if pt.units['phi'][:3]== 'deg': # deg, degree, degrees -> radians
                pt.phi = pt.phi * pi / 180.
                pt.newunits['phi'] = 'rad'
        # C2. ... and in BMK convention. `frame` attribute is
        # obligatory for phi-dependent data.
            if pt.frame == 'Trento':  # Trento -> BMK
                pt.phi = pi - pt.phi
                pt.newframe = 'BMK'
    to_conventions = staticmethod(to_conventions)

    def from_conventions(pt):
        """Transform stuff from Approach's conventions into original data's."""
        # C1. azimutal angle phi should be in radians ...
        if pt.has_key('phi'):
            if pt.units['phi'][:3]== 'deg': # deg, degree, degrees -> radians
                pt.phi = pt.phi * pi / 180.
                pt.units['phi'] = 'rad'
        # C2. ... and in BKM convention. `frame` attribute is
        # obligatory for phi-dependent data.
            if pt.frame == 'Trento':  # Trento -> BKM
                pt.phi = pi - pt.phi
    from_conventions = staticmethod(from_conventions)

    def prepare(pt):
        """Pre-calculate GPD-independent kinamatical constants and functions."""
        pt.y = (pt.W**2 + pt.Q2 - Mp2) / (pt.s - Mp2)
        pt.eps = 2. * pt.xB * Mp / sqrt(pt.Q2)
        pt.eps2 = pt.eps**2
        if pt.has_key('t'):
            pt.J = BMK.J(pt.Q2, pt.xB, pt.t, pt.y, pt.eps2)
            pt.K2 = BMK.K2(pt.Q2, pt.xB, pt.t, pt.y, pt.eps2)
            pt.K = sqrt(pt.K2)
            pt.tK2 = pt.K2*pt.Q2/(1-pt.y-pt.eps2*pt.y**2/4.)
            pt.tK = sqrt(pt.tK2)
            pt.r = BMK.r(pt.Q2, pt.xB, pt.t, pt.y, pt.eps2)
            # First option is numerical, second is analytical and faster
            #pt.intP1P2 = quadrature.Hquadrature(lambda phi: P1P2(pt, phi), 0, 2.0*pi)
            pt.intP1P2 = BMK.anintP1P2(pt)
        if pt.has_key('phi'):
            pt.P1P2 = BMK.P1P2(pt)
    prepare = staticmethod(prepare)


    ################################################
    #                                              #
    ###  Terms of squared ep->epgamma amplitude  ###
    #                                              #
    ################################################


    #### Bethe-Heitler amplitude squared Fourier coefficients

    def cBH0unpSX(self, pt):
        """ BKM Eq. (35) - small-x approximation """
        return 16. * pt.K2 * (pt.Q2/pt.t) * ( 
                self.m.F1(pt.t)**2 - (pt.t/(4.0*Mp2)) * self.m.F2(pt.t)**2 
                  ) + 8. * (2. - pt.y)**2 * ( 
                self.m.F1(pt.t)**2 - (pt.t/(4.0*Mp2)) * self.m.F2(pt.t)**2 )

    def cBH0unp(self, pt):
        """ BKM Eq. (35) """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        FE2 = self.m.F1(t)**2 - t * self.m.F2(t)**2 / (4.0 * Mp2) 
        FM2 = (self.m.F1(t) + self.m.F2(t))**2
        # braces are expressions in {..} in Eq. (35)
        brace1 = (2.+3.*eps2) * (Q2/t) * FE2 + 2.* xB**2 * FM2
        brace2 = (  (2.+eps2)*( (4.*xB**2*Mp2/t)*(1.+t/Q2)**2 +
                       4.*(1.-xB)*(1.+xB*t/Q2) ) * FE2 +
                    4.*xB**2*( xB + (1.-xB+eps2/2.)*(1.-t/Q2)**2 -
                       xB*(1.-2.*xB)*t**2/Q2**2 )  * FM2  )
        brace3 = 2.*eps2*(1.-t/(4.*Mp2)) * FE2 - xB**2*(1.-t/Q2)**2 * FM2
        return ( 8. * pt.K2 * brace1 + 
                (2.-y)**2 * brace2 + 
                 8. * (1.+eps2) * (1.-y-eps2*y**2/4.) * brace3  )

    def cBH1unp(self, pt):
        """ BKM Eq. (36) """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        FE2 = self.m.F1(t)**2 - t * self.m.F2(t)**2 / (4.0 * Mp2) 
        FM2 = (self.m.F1(t) + self.m.F2(t))**2
        brace = ( (4.*xB**2*Mp2/t - 2.*xB - eps2) * FE2 + 
                   2.*xB**2*(1.-(1.-2.*xB)*t/Q2) * FM2 )
        return 8. * pt.K * (2.-y) * brace

    def cBH2unp(self, pt):
        """ BKM Eq. (37) """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        FE2 = self.m.F1(t)**2 - t * self.m.F2(t)**2 / (4.0 * Mp2) 
        FM2 = (self.m.F1(t) + self.m.F2(t))**2
        brace = 4.*Mp2/t * FE2 + 2. * FM2
        return 8. * xB**2 * pt.K2 * brace

    def TBH2unp(self, pt):
        """ Bethe-Heitler amplitude squared. BKM Eq. (25)  """
        return  self.PreFacBH(pt) * ( self.cBH0unp(pt) + 
                   self.cBH1unp(pt)*cos(pt.phi) + self.cBH2unp(pt)*cos(2.*pt.phi) )


    #### DVCS

    # {\cal C} coefficients

    def CCALDVCSunp(self, pt):
        """ BKM Eq. (66) """

        xB2 = pt.xB**2
        ReH = self.m.ReH(pt)
        ImH = self.m.ImH(pt)
        ReE = self.m.ReE(pt)
        ImE = self.m.ImE(pt)
        ReHt = self.m.ReHt(pt)
        ImHt = self.m.ImHt(pt)
        ReEt = self.m.ReEt(pt)
        ImEt = self.m.ImEt(pt)
        parenHH = ReH**2 + ImH**2 + ReHt**2 + ImHt**2
        parenEH = 2.*( ReE*ReH + ImE*ImH + ReEt*ReHt + ImEt*ImHt ) 
        parenEE =  ReE**2 + ImE**2 
        parenEtEt = ReEt**2 + ImEt**2
        brace = 4. * (1.-pt.xB) * parenHH - xB2 * parenEH - (xB2 
                + (2.-pt.xB)**2 * pt.t/(4.*Mp2)) * parenEE - xB2 * pt.t/(4.*Mp2) * parenEtEt
        return brace / (2.-pt.xB)**2
           
    # DVCS amplitude squared Fourier coefficients

    def CDVCSunpPP(self, pt):
        """BMK Eq. (43)"""

        return 2. * (2. - 2.*pt.y + pt.y**2)


    def cDVCS0unp(self, pt):
        """ BKM Eq. (43) """
        return self.CDVCSunpPP(pt) * self.CCALDVCSunp(pt)

    def TDVCS2unp(self, pt):
        """ DVCS amplitude squared. BKM Eq. (26) - FIXME: only twist two now """
        return  self.PreFacDVCS(pt) * self.cDVCS0unp(pt)

    #### Interference

    def ReCCALINTunp(self, pt):
        """ Real part of BKM Eq. (69) """

        return self.m.F1(pt.t)*self.m.ReH(pt) + pt.xB/(2.-pt.xB)*(self.m.F1(pt.t)+
                self.m.F2(pt.t))*self.m.ReHt(pt) - pt.t/(4.*Mp2)*self.m.F2(pt.t)*self.m.ReE(pt)

    def ImCCALINTunp(self, pt):
        """ Imag part of BKM Eq. (69) """

        return self.m.F1(pt.t)*self.m.ImH(pt) + pt.xB/(2.-pt.xB)*(self.m.F1(pt.t)+
                self.m.F2(pt.t))*self.m.ImHt(pt) - pt.t/(4.*Mp2)*self.m.F2(pt.t)*self.m.ImE(pt)

    def ReDELCCALINTunp(self, pt):
        """ Real part of BKM Eq. (72) """

        fx = pt.xB / (2. - pt.xB)
        return - fx * (self.m.F1(pt.t)+self.m.F2(pt.t)) * ( fx *(self.m.ReH(pt) 
            + self.m.ReE(pt)) + self.m.ReHt(pt) )

    def ImDELCCALINTunp(self, pt):
        """ Imag part of BKM Eq. (72) """

        fx = pt.xB / (2. - pt.xB)
        return - fx * (self.m.F1(pt.t)+self.m.F2(pt.t)) * ( fx *(self.m.ImH(pt) 
            + self.m.ImE(pt)) + self.m.ImHt(pt) )

    def ReCCALINTunpEFF(self, pt):
        return 0

    def ImCCALINTunpEFF(self, pt):
        return 0

    def cINT0unpSX(self, pt):
        """ BKM Eq. (53) - small-x approximation!! """
        return -8. * (2. - pt.y) * (2. - 2. * pt.y + pt.y**2) *  (
                -pt.t/pt.Q2) * self.ReCCALINTunp(pt)

    def cINT0unp(self, pt):
        """ BKM Eq. (53) """
        return -8. * (2. - pt.y) * (
                   (2.-pt.y)**2 * pt.K2 * self.ReCCALINTunp(pt) / (1.-pt.y) + 
                   (pt.t/pt.Q2) * (1.-pt.y) * (2.-pt.xB) * 
                      ( self.ReCCALINTunp(pt) + self.ReDELCCALINTunp(pt) ) )

    def cINT1unp(self, pt):
        """ BKM Eq. (54) """
        return -8. * pt.K * (2. - 2. * pt.y + pt.y**2) * self.ReCCALINTunp(pt)

    def sINT1unp(self, pt):
        """ BKM Eq. (54) """
        return  pt.in1polarization * 8. * pt.K * pt.y * (2.-pt.y) * self.ImCCALINTunp(pt)

    def cINT2unp(self, pt):
        """ BKM Eq. (55) """
        return  -16. * pt.K2 * (2. - pt.y) / (2.-pt.xB) * self.ReCCALINTunpEFF(pt)

    def sINT2unp(self, pt):
        """ BKM Eq. (55) """
        return  16. * pt.K2 * pt.y / (2.-pt.xB) * self.ImCCALINTunpEFF(pt)

    def TINTunp(self, pt):
        """ BH-DVCS interference. BKM Eq. (27) - FIXME: only twist two """
        return  - pt.in1charge * self.PreFacINT(pt) * ( self.cINT0unp(pt)  
                + self.cINT1unp(pt) * cos(pt.phi)
                #+ self.cINT2unp(pt) * cos(2.*pt.phi) 
                + self.sINT1unp(pt) * sin(pt.phi)
                #+ lam * self.sINT2unp(pt) * sin(2.*pt.phi)
                )
           
    #def TINTunpd(self, pt):
    #    """ BH-DVCS interference. (Normalized) part surviving after taking difference 
    #    of two lepton longitudinal polarization states.
    #    BKM Eq. (27) - FIXME: only twist two """
    #    return  - pt.in1charge * self.PreFacINT(pt) * self.sINT1unp(pt) * sin(pt.phi)

## Observables ##

    def Xunp(self, pt, **kwargs):
        """ Calculate 4-fold differential cross section for unpolarized target. 

        lam is lepton polarization \lambda .
        FIXME: Is this 'phi' bussiness below ugly?
        
        """
        if kwargs.has_key('vars'):
            ptvars = Data.DummyPoint(init=kwargs['vars'])
            kin = utils.fill_kinematics(ptvars, old=pt)
            BMK.prepare(kin)
        else:
            # just copy everything from pt
            ptempty = Data.DummyPoint()
            kin = utils.fill_kinematics(ptempty, old=pt)
            BMK.prepare(kin)
            ## Nothing seems to be gained by following approach:
            #kin = dict((i, getattr(pt, i)) for i in 
            #        ['xB', 'Q2', 'W', 's', 't', 'mt', 'phi', 'in1charge',
            #            'in1polarization', 'in2particle'])

        # copy non-kinematical info
        for atr in ['in1charge', 'in1polarization', 'in2polarization']:
            if pt.has_key(atr):
                setattr(kin, atr, getattr(pt, atr))

        if kwargs.has_key('zeropolarized') and kwargs['zeropolarized']:
            kin.in1polarization = 0

        if kwargs.has_key('flip') and kwargs['flip']:
            if isinstance(kwargs['flip'], list):
                for item in kwargs['flip']:
                    setattr(kin, item, - getattr(pt, item))
            else:
                setattr(kin, kwargs['flip'], - getattr(pt, kwargs['flip']))

        if kwargs.has_key('weighted') and kwargs['weighted']:
            wgh = self.w(kin)
        else:
            wgh = 1

        # Gepard needs resetting
        if self.model.__dict__.has_key('Gepard'): self.m.g.newcall = 1

        return wgh * self.PreFacSigma(kin) * ( self.TBH2unp(kin) 
                + self.TINTunp(kin) 
                + self.TDVCS2unp(kin) )

    def BSD(self, pt, **kwargs):
        """Calculate 4-fold helicity-dependent cross section measured by HALL A """

        R = kwargs.copy()
        R.update({'flip':'in1polarization'})
        return ( self.Xunp(pt, **kwargs) 
                - self.Xunp(pt, **R) ) / 2.

    def BSS(self, pt, **kwargs):
        """4-fold helicity-independent cross section measured by HALL A """
        R = kwargs.copy()
        R.update({'flip':'in1polarization'})
        return ( self.Xunp(pt, **kwargs) 
                + self.Xunp(pt, **R) ) / 2.

    def _BSA(self, pt, **kwargs):
        """Calculate beam spin asymmetry (BSA)."""
        return self.BSD(pt, **kwargs) / self.BSS(pt, **kwargs)

    def BSA(self, pt, **kwargs):
        """Calculate beam spin asymmetry (BSA) or its harmonics."""
        if pt.has_key('phi'):
            return self._BSA(pt, **kwargs)
        elif pt.has_key('FTn') and pt.FTn == -1:
            # FIXME: faster shortcut (approximate!)
            if kwargs.has_key('vars'):
                kwargs['vars'].update({'phi':pi/2.})
            else:
                kwargs['vars'] = {'phi':pi/2.}
            return  self._BSA(pt, **kwargs) 
        ### Exact but slower:
            #res = quadrature.Hquadrature(lambda phi: 
            #        self._BSA(pt, vars={'phi':phi}) * sin(phi), 0, 2*pi)
            #return  res / pi

    def _BCA(self, pt, **kwargs):
        """Calculate beam charge asymmetry (BCA)."""

        kwargs.update({'zeropolarized':True})
        R = kwargs.copy()
        R.update({'flip':'in1charge'})
        return (
           self.Xunp(pt, **kwargs) 
             - self.Xunp(pt, **R) )/(
           self.Xunp(pt, **kwargs )
             + self.Xunp(pt, **R) )
        # optimized formula (remove parts which cancel anyway)
        # return  self.TINTunp(pt, phi, 0, 1) / ( 
        #               self.TBH2unp(pt, phi) + self.TDVCS2unp(pt, phi) )

    def BCA(self, pt):
        """Calculate beam charge asymmetry (BCA) or its harmonics."""
        if pt.has_key('phi'):
            return self._BCA(pt)
        elif pt.has_key('FTn') and pt.FTn == 0:
            res = quadrature.Hquadrature(lambda phi: 
                    self._BCA(pt, vars={'phi':phi}), 0, 2.0*pi)
            return res / (2.0*pi)
        elif pt.has_key('FTn') and pt.FTn == 1:
            res = quadrature.Hquadrature(lambda phi: 
                    self._BCA(pt, vars={'phi':phi}) * cos(phi), 0, 2*pi)
            return  - res / pi

    def BCSD(self, pt, **kwargs):
        """4-fold beam charge-spin cross section difference measured by COMPASS """
        R = kwargs.copy()
        R.update({'flip':['in1polarization', 'in1charge']})
        return (self.Xunp(pt, **kwargs) 
                - self.Xunp(pt, **R))/2.

    def BCSS(self, pt, **kwargs):
        """4-fold beam charge-spin cross section sum measured by COMPASS. """
        R = kwargs.copy()
        R.update({'flip':['in1polarization', 'in1charge']})
        return (self.Xunp(pt, **kwargs) 
                + self.Xunp(pt, **R))/2.

    def BCSA(self, pt, **kwargs):
        """Beam charge-spin asymmetry as measured by COMPASS. """
        return  self.BCSD(pt, **kwargs) / self.BCSS(pt, **kwargs)

    def _XDVCSt4int(self, t, pt):
        """Same as XDVCSt but with additional variable t 
        to facilitate integration over it.
        
        """
        aux = []
        for t_single in t:
            pt.t = t_single
            res = self.XDVCSt(pt)
            #if debug == 2: print "t = %s  =>  dsig/dt = %s" % (t_single, res)
            aux.append(res)

        return array(aux)


    def XDVCSt(self, pt):
        """Partial DVCS cross section w.r.t. Mandelstam t."""

        W2 = pt.W * pt.W
        self.m.g.newcall = 1
        # Simplified formula used also in Fortran gepard code
        res = 260.5633976788416 * W2 * ( 
                (self.m.ImH(pt)**2 + self.m.ReH(pt)**2)
                - pt.t/(4.*Mp2)*(self.m.ReE(pt)**2 + self.m.ImE(pt)**2)) / (
            (W2 + pt.Q2) * (2.0 * W2 + pt.Q2)**2 )
        #sys.stderr.write('%s\n' % (res,))
        return res


    def XDVCS(self, pt):
        """Total DVCS cross section."""

        res = quadrature.tquadrature(lambda t: self._XDVCSt4int(t, pt), -1, 0)
        return res

    def BCA0minusr1(self, pt):
        return self.BCAcos0(pt) - pt.r * self.BCAcos1(pt)

    def BSDw2C(self, pt):
        """Im(C^I) as defined by HALL A """
        return self.ImCCALINTunp(pt)

    def BSSw2C(self, pt):
        """Re(C^I) or Re(C^I + Del C^I) as defined by HALL A.

        FIXME: Although it is attributed to FTn=0, Re(C^I + Del C^I)
        is only a part of zeroth harmonic.

        """
        if pt.FTn == 0:
            return self.ReCCALINTunp(pt) + self.ReDELCCALINTunp(pt)
        elif pt.FTn == 1:
            return self.ReCCALINTunp(pt)

    def BSDw(self, pt):
        """Weighted BSD harmonics.

        """
        if pt.FTn == -1:
            return quadrature.Hquadrature(lambda phi: self.BSD(pt, vars={'phi':phi},
                weighted=True) * sin(phi), 0, 2.0*pi) / pi
        elif pt.FTn == -2:
            return quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi},
                weighted=True) * sin(2.*phi), 0, 2.0*pi) / pi

    def BSDw(self, pt, **kwargs):
        """Calculate weighted beam spin difference (BSD) or its harmonics."""
        if pt.has_key('phi'):
            kwargs[weighted] = True
            #return self.BSD(pt, **kwargs)
            raise ValueError('Untested!')
        elif pt.has_key('FTn'):
            if pt.FTn < 0:
                res = quadrature.Hquadrature(lambda phi: self.BSD(pt, vars={'phi':phi},
                weighted=True) * sin(-pt.FTn*phi), 0, 2.0*pi)
            elif pt.FTn > 0:
                res = quadrature.Hquadrature(lambda phi: self.BSD(pt, vars={'phi':phi},
                weighted=True) * cos(pt.FTn*phi), 0, 2.0*pi)
            elif pt.FTn == 0:
                res = quadrature.Hquadrature(lambda phi: self.BSD(pt, vars={'phi':phi},
                weighted=True), 0, 2.0*pi) / 2.0
            else:
                raise ValueError('This should never happen!')
            return  res / pi
        else:
            raise ValueError('[%s] has neither azimuthal angle phi\
 nor harmonic FTn defined!' % pt)

    def BSSw(self, pt, **kwargs):
        """Calculate weighted beam spin sum (BSS) or its harmonics."""
        if pt.has_key('phi'):
            kwargs[weighted] = True
            #return self.BSS(pt, **kwargs)
            raise ValueError('Untested!')
        elif pt.has_key('FTn'):
            if pt.FTn < 0:
                res = quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi},
                weighted=True) * sin(-pt.FTn*phi), 0, 2.0*pi)
            elif pt.FTn > 0:
                res = quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi},
                weighted=True) * cos(pt.FTn*phi), 0, 2.0*pi)
            elif pt.FTn == 0:
                res = quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi},
                weighted=True), 0, 2.0*pi) / 2.0
            else:
                raise ValueError('This should never happen!')
            return  res / pi
        else:
            raise ValueError('[%s] has neither azimuthal angle phi\
 nor harmonic FTn defined!' % pt)

    def BSSwOLD(self, pt):
        """Weighted BSS harmonics.

        """
        if pt.FTn == 0:
            return quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi}, 
                weighted=True), 0, 2.0*pi) / (2.0*pi)
        elif pt.FTn == 1:
            return quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi},
                weighted=True) * cos(phi), 0, 2.0*pi) / pi
        elif pt.FTn == 2:
            return quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi},
                weighted=True) * cos(2.*phi), 0, 2.0*pi) / pi

    def XwA(self, pt):
        """Ratio of first two cos harmonics of w-weighted cross section. In BMK, not Trento??"""

        b0 = quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi}, weighted=True), 
                0, 2.0*pi) / (2.0*pi)
        b1 = quadrature.Hquadrature(lambda phi: self.BSS(pt, vars={'phi':phi}, weighted=True) * cos(phi), 
                0, 2.0*pi) / pi
        return b1/b0


class hotfixedBMK(BMK):
    """Some BMK formulas are hotfixed here according to BM"""


    def CDVCSunpPP(self, pt):
        """BMK Eq. (43) + BM hotfix"""

        return 2.*( (2. - 2.*pt.y + pt.y**2 + 
            (pt.eps2*pt.y**2)/2.) / (1. + pt.eps2) )

    def CINTunpPP0(self, pt):
        """ Obtained by saving from DM's notebook """

        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return (
           (-((8.*(2. - y)*(1. + sqrt(1. + eps2)))/(2.*(1. + eps2)**2.5)))*
         ((pt.K2*(2. - y)**2)/(1. - y - (y**2*eps2)/4.) + (t/Q2)*(2. - xB)*
           sqrt(1. + eps2)*(1. - y - (y**2*eps2)/4.)*
           (1. + (eps2 + (2.*xB*t*(2. - xB + eps2/(2.*xB) + 0.5*(-1. + sqrt(
                    1. + eps2))))/Q2)/((2. - xB)*(1. + sqrt(1. + eps2)))))
         )

    def CINTunpPP0q(self, pt):
        """ Obtained by saving from DM's notebook """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return (
        (-((8.*(2. - y)*(1. + sqrt(1. + eps2)))/(2.*(1. + eps2)**2.5)))*(t/Q2)*
         (2. - xB)*sqrt(1. + eps2)*(1. - y - (y**2*eps2)/4.)*
         (1. + (eps2 + (2.*xB*t*(2. - xB + eps2/(2.*xB) + 
               0.5*(-1. + sqrt(1. + eps2))))/Q2)/((2. - xB)*(1. + sqrt(1. + eps2))))
         )

    def CINTunpPP1(self, pt):
        """ Obtained by saving from DM's notebook """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return (
        (-((8.*pt.K*(2. - 2.*y + y**2 + (y**2*eps2)/2.))/(1. + eps2)**2.5))*
         (((1. - eps2 + sqrt(1. + eps2))/2.)*(1. - ((1. - 3.*xB)*t)/Q2 + 
            (xB*t*(1. + 3.*eps2 - sqrt(1. + eps2)))/
             (Q2*(1. - eps2 + sqrt(1. + eps2)))) + 
          ((2.*(1. - y - (y**2*eps2)/4.))/(2. - 2.*y + y**2 + (y**2*eps2)/2.))*
           (-((3.*eps2)/4.) + (xB*t*(1. + eps2/(4.*xB) + 
               ((1. - xB)*(-1. + sqrt(1. + eps2)))/(2.*xB)))/Q2))
           )

    def CINTunpPM3(self, pt): 
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        """ Obtained by saving from DM's notebook """
        return -((8.*Q2*pt.K**3)/(Mp2*(2. - xB)**2))

    def SINTunpPP1(self, pt):
        """ Obtained by saving from DM's notebook """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return (
                # OLD INCORRECT: (1. + eps2)**2*((8.*pt.K*(2. - y)*y)/(1. + eps2))*
                # CORRECT: ((8.*pt.K*(2. - y)*y)/(1. + eps2))*
                ((8.*pt.K*(2. - y)*y)/(1. + eps2))*
         (1. + ((t - self.tmin(Q2, xB, eps2))*(1. - xB + 0.5*(-1. + sqrt(1. + eps2))))/
           (Q2*(1. + eps2)))
         )


    def cINT0unp(self, pt):
        """ hotfixed BKM Eq. (53) """

        return (self.CINTunpPP0(pt) * self.ReCCALINTunp(pt)
                + self.CINTunpPP0q(pt) * self.ReDELCCALINTunp(pt))

    def cINT1unp(self, pt):
        """ hotfixed BKM Eq. (54) """
        return self.CINTunpPP1(pt) * self.ReCCALINTunp(pt)

    def sINT1unp(self, pt):
        """ hotfixed BKM Eq. (54) """

        return pt.in1polarization * self.SINTunpPP1(pt) * self.ImCCALINTunp(pt)

class BM10ex(hotfixedBMK):
    """According to BM arXiv:1005.5209 [hep-ph] - exact formulas
    
    Only this Approach implements observables for longitudinally polarized target!
    """


    #### Bethe-Heitler - also longitudinally polarized target  (LP)

    def cBH0LP(self, pt):
        """ BKM Eq. (38) """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        FE = self.m.F1(t) + t * self.m.F2(t) / (4.0 * Mp2) 
        FM = self.m.F1(t) + self.m.F2(t)
        # brackets are expressions in [..] in Eq. (39)
        bracket1 = (xB/2.)*(1.-t/Q2) - t/(4.*Mp2)
        bracket2 = ( 2 - xB - 2.*(1.-xB)**2 * t/Q2 + eps2*(1-t/Q2) -
                xB*(1-2*xB)*t**2/Q2**2 )
        bracket3 = ( (xB**2*Mp2/t) * (1+t/Q2)**2 +
                (1.-xB)*(1.+xB*t/Q2) )
        return ( 8.*pt.in1polarization*pt.in2polarization*xB*(2.-y) *
                y*sqrt(1.+eps2)/(1.-t/(4.*Mp2)) * FM * (
                    0.5*bracket1*bracket2*FM +
                    (1.-(1.-xB)*t/Q2)*bracket3*FE ) )

    def cBH1LP(self, pt):
        """ BKM Eq. (39) """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        FE = self.m.F1(t) + t * self.m.F2(t) / (4.0 * Mp2) 
        FM = self.m.F1(t) + self.m.F2(t)
        bracket1 = t/(2.*Mp2) - xB*(1.-t/Q2)
        bracket2 = ( 1.+xB-(3.-2.*xB)*(1.+xB*t/Q2) - 
                4.*xB**2*Mp2/t*(1.+t**2/Q2**2) )
        return ( -8.*pt.in1polarization*pt.in2polarization*xB*y*pt.K * 
                sqrt(1.+eps2)/(1.-t/(4.*Mp2)) * FM * (
                    bracket1 * (1.-xB+xB*t/Q2) * FM + bracket2 * FE ) )

    def TBH2LP(self, pt):
        """ Bethe-Heitler amplitude squared for polarized target. BKM Eq. (25)  """
        return  self.PreFacBH(pt) * ( self.cBH0LP(pt) + self.cBH1LP(pt)*cos(pt.phi) )

    #### DVCS - also longitudinally polarized target  (LP)

    def CDVCSunpPPeff(self, pt):
        """BM10 (2.18)"""

        return 16.*pt.K2/(2.-pt.xB)**2/(1+pt.eps2)
                
    def cDVCS0unp(self, pt):
        """ BM10 (2.18)"""

        return (self.CDVCSunpPP(pt) * self.CCALDVCSunp(pt) +
                self.CDVCSunpPPeff(pt) * self.CCALDVCSunp(pt, leff=1, reff=1))

    def cDVCS1unp(self, pt):
        """ BM10 (2.19)"""

        PP = 8.*pt.K/(2.-pt.xB)/(1+pt.eps2)
        return PP*(2.-pt.y) * self.CCALDVCSunp(pt, im=0, leff=1)

    def sDVCS1unp(self, pt):
        """ BM10 (2.19)"""

        PP = 8.*pt.K/(2.-pt.xB)/(1+pt.eps2)
        return PP*(- pt.in1polarization * pt.y 
                * sqrt(1.+pt.eps2)) * self.CCALDVCSunp(pt, im=1, leff=1)

    def cDVCS0LP(self, pt):
        """ BM10 (2.20)"""

        return 2.*pt.in1polarization*pt.in2polarization*pt.y*(
                2.-pt.y)/sqrt(1.+pt.eps2) * self.CCALDVCSLP(pt) 

    def cDVCS1LP(self, pt):
        """ BM10 (2.21)"""

        PP = - 8.*pt.in2polarization*pt.K/(2.-pt.xB)/(1+pt.eps2)
        return PP*(- pt.in1polarization * pt.y 
                * sqrt(1.+pt.eps2)) * self.CCALDVCSLP(pt, im=0, leff=1)

    def sDVCS1LP(self, pt):
        """ BM10 (2.21)"""

        PP = - 8.*pt.in2polarization*pt.K/(2.-pt.xB)/(1+pt.eps2)
        return PP*(2.-pt.y) * self.CCALDVCSLP(pt, im=1, leff=1)

    def CCALDVCSunp(self, pt, im=0, leff=0, reff=0): 
        """ BM10 (2.22), from DM's notebook """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        if leff:
            H = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            EE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            tH = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            tE = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            H = complex(self.m.ReH(pt), self.m.ImH(pt))
            EE = complex(self.m.ReE(pt), self.m.ImE(pt))
            tH = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            tE = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        if reff:
            HCC = complex(self.m.ReHeff(pt), -self.m.ImHeff(pt))
            EECC = complex(self.m.ReEeff(pt), -self.m.ImEeff(pt))
            tHCC = complex(self.m.ReHteff(pt), -self.m.ImHteff(pt))
            tECC = complex(self.m.ReEteff(pt), -self.m.ImEteff(pt))
        else:
            HCC = complex(self.m.ReH(pt), -self.m.ImH(pt))
            EECC = complex(self.m.ReE(pt), -self.m.ImE(pt))
            tHCC = complex(self.m.ReHt(pt), -self.m.ImHt(pt))
            tECC = complex(self.m.ReEt(pt), -self.m.ImEt(pt))
        res = (Q2*(Q2 + t*xB)*(4*H*HCC*(1 - xB) - 
           ((EECC*H + EE*HCC)*(Q2 + t)**2*xB**2)/(Q2*(Q2 + t*xB)) - 
           (Q2*t*tE*tECC*xB**2)/(4*Mp2*(Q2 + t*xB)) - 
           (Q2*(tECC*tH + tE*tHCC)*xB**2)/(Q2 + t*xB) + 
           4*tH*tHCC*(1 - xB + (eps2*(2*Q2 + t))/(4*(Q2 + t*xB))) + 
           EE*EECC*(-(((Q2 + t)**2*xB**2)/(Q2*(Q2 + t*xB))) - 
             (t*(Q2*(2 - xB) + t*xB)**2)/(4*Mp2*Q2*(Q2 + t*xB))))
           )/(Q2*(2 - xB) + t*xB)**2
        if im:
            return res.imag
        else:
            return res.real
 
    def CCALDVCSLP(self, pt, im=0, leff=0, reff=0): 
        """ BM10 (2.23), from DM's notebook """
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        if leff:
            H = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            EE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            tH = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            tE = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            H = complex(self.m.ReH(pt), self.m.ImH(pt))
            EE = complex(self.m.ReE(pt), self.m.ImE(pt))
            tH = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            tE = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        if reff:
            HCC = complex(self.m.ReHeff(pt), -self.m.ImHeff(pt))
            EECC = complex(self.m.ReEeff(pt), -self.m.ImEeff(pt))
            tHCC = complex(self.m.ReHteff(pt), -self.m.ImHteff(pt))
            tECC = complex(self.m.ReEteff(pt), -self.m.ImEteff(pt))
        else:
            HCC = complex(self.m.ReH(pt), -self.m.ImH(pt))
            EECC = complex(self.m.ReE(pt), -self.m.ImE(pt))
            tHCC = complex(self.m.ReHt(pt), -self.m.ImHt(pt))
            tECC = complex(self.m.ReEt(pt), -self.m.ImEt(pt))
        res = (Q2*(Q2 + t*xB)*(4*H*HCC*(1 - xB) - 
           ((EECC*H + EE*HCC)*(Q2 + t)**2*xB**2)/(Q2*(Q2 + t*xB)) - 
           (Q2*t*tE*tECC*xB**2)/(4*Mp2*(Q2 + t*xB)) - 
           (Q2*(tECC*tH + tE*tHCC)*xB**2)/(Q2 + t*xB) + 
           4*tH*tHCC*(1 - xB + (eps2*(2*Q2 + t))/(4*(Q2 + t*xB))) + 
           EE*EECC*(-(((Q2 + t)**2*xB**2)/(Q2*(Q2 + t*xB))) - 
             (t*(Q2*(2 - xB) + t*xB)**2)/(4*Mp2*Q2*(Q2 + t*xB))))
            )/ (Q2*(2 - xB) + t*xB)**2
        if im:
            return res.imag
        else:
            return res.real

    def TDVCS2unp(self, pt):
        """ DVCS amplitude squared. BM10 Eq. (2.17)"""
        return  self.PreFacDVCS(pt) * (self.cDVCS0unp(pt)
                + self.cDVCS1unp(pt) * cos(pt.phi)
                + self.sDVCS1unp(pt) * sin(pt.phi) )

    def TDVCS2LP(self, pt):
        """ DVCS amplitude squared. BM10 Eq. (2.17)"""
        return  self.PreFacDVCS(pt) * (self.cDVCS0LP(pt)
                + self.cDVCS1LP(pt) * cos(pt.phi)
                + self.sDVCS1LP(pt) * sin(pt.phi) )

    #### INTERFERENCE - also longitudinally polarized target  (LP)

    def CCALINTunp(self, pt, im=0, eff=0):
        """ BM10 Eq. (2.28) ... set im=1 for imag part, eff=1 for F_eff """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
    self.m.F1(t)*CFFH - (t/(4*Mp2))*self.m.F2(t)*CFFE + 
     (xB/((2 - xB) + (t*xB)/pt.Q2))*(self.m.F1(t) + self.m.F2(t))*CFFHt
    )
        if im:
            return res.imag
        else:
            return res.real
    
    def CCALINTunpV(self, pt, im=0, eff=0):
        """ BM10 Eq. (2.29) ... set im=1 for imag part, eff=1 for F_eff """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
    (xB/((2 - xB) + (t*xB)/pt.Q2))*(self.m.F1(t) + self.m.F2(t))*
     (CFFH + CFFE)
    )
        if im:
            return res.imag
        else:
            return res.real
    

    def CCALINTunpA(self, pt, im=0, eff=0):
        """ ... set im=1 for imag part, eff=1 for F_eff """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
    (xB/((2 - xB) + (t*xB)/pt.Q2))*(self.m.F1(t) + self.m.F2(t))*CFFHt
    )
        if im:
            return res.imag
        else:
            return res.real
    

    def CCALINTLP(self, pt, im=0, eff=0):
        """ ... set im=1 for imag part, eff=1 for F_eff """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
    (xB/((2 - xB) + (t*xB)/pt.Q2))*(self.m.F1(t) + self.m.F2(t))*
      (CFFH + (xB/2)*(1 - t/pt.Q2)*
        CFFE) + (1 + (Mp2/pt.Q2)*
        ((2*xB**2)/((2 - xB) + (t*xB)/pt.Q2))*
        (3 + t/pt.Q2))*self.m.F1(t)*CFFHt - 
     (t/pt.Q2)*((xB*(1 - 2*xB))/((2 - xB) + 
        (t*xB)/pt.Q2))*self.m.F2(t)*CFFHt - 
     (xB/((2 - xB) + (t*xB)/pt.Q2))*
      ((xB/2)*(1 - t/pt.Q2)*self.m.F1(t) + (t/(4*Mp2))*self.m.F2(t))*
      CFFEt
    )
        if im:
            return res.imag
        else:
            return res.real
    

    def CCALINTLPV(self, pt, im=0, eff=0):
        """ ... set im=1 for imag part, eff=1 for F_eff """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
    (xB/((2 - xB) + (t*xB)/pt.Q2))*(self.m.F1(t) + self.m.F2(t))*
     (CFFH + (xB/2)*(1 - t/pt.Q2)*
       CFFE)
    )
        if im:
            return res.imag
        else:
            return res.real
    

    def CCALINTLPA(self, pt, im=0, eff=0):
        """ ... set im=1 for imag part, eff=1 for F_eff """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
    (xB/((2 - xB) + (t*xB)/pt.Q2))*(self.m.F1(t) + self.m.F2(t))*
     ((1 + (2*Mp2*xB)/pt.Q2)*CFFHt + 
      (xB/2)*CFFEt)
    )
        if im:
            return res.imag
        else:
            return res.real
    

    CINT = {} # name mapping dictionary - just for convenience
    SINT = {} # name mapping dictionary - just for convenience

    def CINTLP210(self, pt):
        """Same as CINT["LP", (-1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-pt.in2polarization)*((4*pt.in1polarization*y)/
      (1 + eps2)**(5/2.))*
     ((pt.tK2*(2 - y)**2*(-1 + sqrt(1 + eps2)))/pt.Q2 + 
      (1 - y - (y**2*eps2)/4)*((xB*t)/pt.Q2 - 
        (1/2.)*(1 - t/pt.Q2)*eps2)*
       (-1 + sqrt(1 + eps2) + (t*(1 - 2*xB + sqrt(1 + eps2)))/
         pt.Q2))
    )
    
    CINT['LP', (-1, 1), (0)] = CINTLP210

    def CINTLP211(self, pt):
        """Same as CINT["LP", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-pt.in2polarization)*((4*pt.K*y*(2 - y)*pt.in1polarization)/
      (1 + eps2)**(5/2.))*(-1 + eps2 + sqrt(1 + eps2) - 
      (t*(-1 + eps2 + sqrt(1 + eps2) + 
         2*xB*(2 - sqrt(1 + eps2))))/pt.Q2)
    )
    
    CINT['LP', (-1, 1), (1)] = CINTLP211

    def CINTLP212(self, pt):
        """Same as CINT["LP", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-pt.in2polarization)*
     ((2*pt.in1polarization*y*(1 - y - (y**2*eps2)/4))/
      (1 + eps2)**(5/2.))*(eps2*(1 + sqrt(1 + eps2)) - 
      (t/pt.Q2)*((t*(2*xB + eps2)*
          (-1 + 2*xB + sqrt(1 + eps2)))/pt.Q2 + 
        2*(eps2 + xB*(1 - eps2 + sqrt(1 + eps2)))))
    )
    
    CINT['LP', (-1, 1), (2)] = CINTLP212

    def CINTLP213(self, pt):
        """Same as CINT["LP", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LP', (-1, 1), (3)] = CINTLP213

    def CINTLP010(self, pt):
        """Same as CINT["LP", (0, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( pt.in2polarization*
     ((8*sqrt(2)*pt.K*(1 - xB)*y*sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization)/
      (1 + eps2)**2)*(t/pt.Q2)
    )
    
    CINT['LP', (0, 1), (0)] = CINTLP010

    def CINTLP011(self, pt):
        """Same as CINT["LP", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-pt.in2polarization)*
     ((8*sqrt(2)*(2 - y)*y*sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization)/
      (1 + eps2)**2)*(pt.tK2/pt.Q2)
    )
    
    CINT['LP', (0, 1), (1)] = CINTLP011

    def CINTLP012(self, pt):
        """Same as CINT["LP", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-pt.in2polarization)*
     ((8*sqrt(2)*pt.K*y*sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization)/
      (1 + eps2)**2)*(1 + (xB*t)/pt.Q2)
    )
    
    CINT['LP', (0, 1), (2)] = CINTLP012

    def CINTLP013(self, pt):
        """Same as CINT["LP", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LP', (0, 1), (3)] = CINTLP013

    def CINTLP110(self, pt):
        """Same as CINT["LP", (1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-((4*(1 + sqrt(1 + eps2))*y*pt.in1polarization*
        pt.in2polarization)/(1 + eps2)**(5/2.)))*
     ((2 - y)**2*(pt.tK2/pt.Q2) + (1 - y - (y**2*eps2)/4)*
       ((xB*t)/pt.Q2 - (1/2.)*(1 - t/pt.Q2)*
         eps2)*(1 + ((sqrt(1 + eps2) - 1 + 2*xB)/
          (1 + sqrt(1 + eps2)))*(t/pt.Q2)))
    )
    
    CINT['LP', (1, 1), (0)] = CINTLP110

    def CINTLP111(self, pt):
        """Same as CINT["LP", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-((8*pt.K*(2 - y)*y*pt.in1polarization*pt.in2polarization)/
       (1 + eps2)**(5/2.)))*((1 + sqrt(1 + eps2) - 
       eps2)/2)*(1 - (1 - (2*xB*(2 + sqrt(1 + eps2)))/
         (1 - eps2 + sqrt(1 + eps2)))*(t/pt.Q2))
    )
    
    CINT['LP', (1, 1), (1)] = CINTLP111

    def CINTLP112(self, pt):
        """Same as CINT["LP", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-((4*(1 - y - (y**2*eps2)/4)*y*pt.in1polarization*
        pt.in2polarization)/(1 + eps2)**(5/2.)))*
     ((xB*t)/pt.Q2 - (1 - t/pt.Q2)*
       (eps2/2.))*(1 - sqrt(1 + eps2) - 
      (1 + sqrt(1 + eps2) - 2*xB)*(t/pt.Q2))
    )
    
    CINT['LP', (1, 1), (2)] = CINTLP112

    def CINTLP113(self, pt):
        """Same as CINT["LP", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LP', (1, 1), (3)] = CINTLP113

    def CINTLPA210(self, pt):
        """Same as CINT["LPA", (-1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (4*t*xB*y*(2*(2 - y)**2*((t*(1 - xB)*(1 + (t*xB)/pt.Q2))/
          pt.Q2 + ((1 + t/pt.Q2)**2*eps2)/
          4) - (1 - (t*(1 - 2*xB))/pt.Q2)*
        (1 - y - (y**2*eps2)/4)*(1 - sqrt(1 + eps2) - 
         (t*(1 - 2*xB + sqrt(1 + eps2)))/pt.Q2))*
      pt.in1polarization*pt.in2polarization)/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['LPA', (-1, 1), (0)] = CINTLPA210

    def CINTLPA211(self, pt):
        """Same as CINT["LPA", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-16*pt.K*t*xB*(2 - y)*y*
      (1 - (t*(1 - 2*xB))/pt.Q2)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['LPA', (-1, 1), (1)] = CINTLPA211

    def CINTLPA212(self, pt):
        """Same as CINT["LPA", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (-4*t*xB*y*(1 - (t*(1 - 2*xB))/pt.Q2)*
      (1 - y - (y**2*eps2)/4)*(1 + sqrt(1 + eps2) + 
       (t*(-1 + 2*xB + sqrt(1 + eps2)))/pt.Q2)*
      pt.in1polarization*pt.in2polarization)/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['LPA', (-1, 1), (2)] = CINTLPA212

    def CINTLPA213(self, pt):
        """Same as CINT["LPA", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LPA', (-1, 1), (3)] = CINTLPA213

    def CINTLPA010(self, pt):
        """Same as CINT["LPA", (0, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*sqrt(2)*pt.K*t*xB*y*(1 + t/pt.Q2)*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**2)
    )
    
    CINT['LPA', (0, 1), (0)] = CINTLPA010

    def CINTLPA011(self, pt):
        """Same as CINT["LPA", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LPA', (0, 1), (1)] = CINTLPA011

    def CINTLPA012(self, pt):
        """Same as CINT["LPA", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*pt.K*t*xB*y*(1 + t/pt.Q2)*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**2)
    )
    
    CINT['LPA', (0, 1), (2)] = CINTLPA012

    def CINTLPA013(self, pt):
        """Same as CINT["LPA", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LPA', (0, 1), (3)] = CINTLPA013

    def CINTLPA110(self, pt):
        """Same as CINT["LPA", (1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*t*xB*y*((pt.tK2*(2 - y)**2)/pt.Q2 + 
       ((1 - (t*(1 - 2*xB))/pt.Q2)*
         (1 - y - (y**2*eps2)/4)*(1 + sqrt(1 + eps2))*
         (1 + (t*(-1 + 2*xB + sqrt(1 + eps2)))/(pt.Q2*
            (1 + sqrt(1 + eps2)))))/2)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['LPA', (1, 1), (0)] = CINTLPA110

    def CINTLPA111(self, pt):
        """Same as CINT["LPA", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (16*pt.K*t*xB*(2 - y)*y*
      (1 - (t*(1 - 2*xB))/pt.Q2)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['LPA', (1, 1), (1)] = CINTLPA111

    def CINTLPA112(self, pt):
        """Same as CINT["LPA", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*t*xB*y*(1 - (t*(1 - 2*xB))/pt.Q2)*
      (1 - y - (y**2*eps2)/4)*(1 - sqrt(1 + eps2) - 
       (t*(1 - 2*xB + sqrt(1 + eps2)))/pt.Q2)*pt.in1polarization*
      pt.in2polarization)/(pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['LPA', (1, 1), (2)] = CINTLPA112

    def CINTLPA113(self, pt):
        """Same as CINT["LPA", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LPA', (1, 1), (3)] = CINTLPA113

    def CINTLPV210(self, pt):
        """Same as CINT["LPV", (-1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (2*t*y*((2*pt.tK2*(2 - y)**2*(-1 + 2*xB + sqrt(1 + eps2)))/
        pt.Q2 + (4 - 2*xB + 3*eps2)*
        (1 - y - (y**2*eps2)/4)*
        (1 + (t*(4*(1 - xB)*xB + eps2))/(pt.Q2*
           (4 - 2*xB + 3*eps2)))*(-1 + sqrt(1 + eps2) + 
         (t*(1 - 2*xB + sqrt(1 + eps2)))/pt.Q2))*
      pt.in1polarization*pt.in2polarization)/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['LPV', (-1, 1), (0)] = CINTLPV210

    def CINTLPV211(self, pt):
        """Same as CINT["LPV", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-4*pt.K*t*(2 - y)*y*(5 - 4*xB + 3*eps2 - 
       sqrt(1 + eps2) - (t*(1 - eps2 - 
          sqrt(1 + eps2) + 2*xB*(-4 + 4*xB + 
            sqrt(1 + eps2))))/pt.Q2)*pt.in1polarization*
      pt.in2polarization)/(pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['LPV', (-1, 1), (1)] = CINTLPV211

    def CINTLPV212(self, pt):
        """Same as CINT["LPV", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-2*t*y*(1 - y - (y**2*eps2)/4)*
      (4 - 2*xB + 3*eps2 + (t*(4*xB - 4*xB**2 + eps2))/
        pt.Q2)*(1 + sqrt(1 + eps2) + 
       (t*(-1 + 2*xB + sqrt(1 + eps2)))/pt.Q2)*
      pt.in1polarization*pt.in2polarization)/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['LPV', (-1, 1), (2)] = CINTLPV212

    def CINTLPV213(self, pt):
        """Same as CINT["LPV", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LPV', (-1, 1), (3)] = CINTLPV213

    def CINTLPV010(self, pt):
        """Same as CINT["LPV", (0, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*sqrt(2)*pt.K*t*y*
      (-xB + (t*(1 - 2*xB))/pt.Q2)*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**2)
    )
    
    CINT['LPV', (0, 1), (0)] = CINTLPV010

    def CINTLPV011(self, pt):
        """Same as CINT["LPV", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*t*pt.tK2*(2 - y)*y*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2**2*(1 + eps2)**2)
    )
    
    CINT['LPV', (0, 1), (1)] = CINTLPV011

    def CINTLPV012(self, pt):
        """Same as CINT["LPV", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*pt.K*t*(1 - xB)*y*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**2)
    )
    
    CINT['LPV', (0, 1), (2)] = CINTLPV012

    def CINTLPV013(self, pt):
        """Same as CINT["LPV", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LPV', (0, 1), (3)] = CINTLPV013

    def CINTLPV110(self, pt):
        """Same as CINT["LPV", (1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*t*y*(1 + sqrt(1 + eps2))*
      ((pt.tK2*(2 - y)**2*(1 - 2*xB + sqrt(1 + eps2)))/
        (pt.Q2*(1 + sqrt(1 + eps2))) + 
       (2 - xB + (3*eps2)/2)*(1 - y - (y**2*eps2)/4)*
        (1 + (t*(4*(1 - xB)*xB + eps2))/(pt.Q2*
           (4 - 2*xB + 3*eps2)))*
        (1 + (t*(-1 + 2*xB + sqrt(1 + eps2)))/(pt.Q2*
           (1 + sqrt(1 + eps2)))))*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['LPV', (1, 1), (0)] = CINTLPV110

    def CINTLPV111(self, pt):
        """Same as CINT["LPV", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*pt.K*t*(2 - y)*y*(2*(1 - xB) + 
       sqrt(1 + eps2))*
      (1 - ((t - self.tmin(Q2, xB, eps2))*(1 + (1 - eps2)/sqrt(1 + eps2) - 
          2*xB*(1 + (4*(1 - xB))/sqrt(1 + eps2))))/
        (2*pt.Q2*(2*(1 - xB) + sqrt(1 + eps2))))*
      pt.in1polarization*pt.in2polarization)/(pt.Q2*(1 + eps2)**2)
    )
    
    CINT['LPV', (1, 1), (1)] = CINTLPV111

    def CINTLPV112(self, pt):
        """Same as CINT["LPV", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-2*t*y*(4 - 2*xB + 3*eps2)*
      (1 - y - (y**2*eps2)/4)*(1 + (t*(4*(1 - xB)*xB + eps2))/
        (pt.Q2*(4 - 2*xB + 3*eps2)))*
      (-1 + sqrt(1 + eps2) + (t*(1 - 2*xB + sqrt(1 + eps2)))/
        pt.Q2)*pt.in1polarization*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['LPV', (1, 1), (2)] = CINTLPV112

    def CINTLPV113(self, pt):
        """Same as CINT["LPV", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['LPV', (1, 1), (3)] = CINTLPV113

    def CINTunp210(self, pt):
        """Same as CINT["unp", (-1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (8*(2 - y)*((pt.tK2*(2 - y)**2*(-1 + sqrt(1 + eps2)))/
        (2*pt.Q2*(1 + eps2)) + 
       (t*(t - self.tmin(Q2, xB, eps2))*xB*(1 - y - (y**2*eps2)/4)*
         (1 - xB + eps2/(2*xB) + (1 - sqrt(1 + eps2))/2))/
        (pt.Q2**2*sqrt(1 + eps2))))/
     (1 + eps2)**(3/2.)
    )
    
    CINT['unp', (-1, 1), (0)] = CINTunp210

    def CINTunp211(self, pt):
        """Same as CINT["unp", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (8*pt.K*((2*(1 - y - (y**2*eps2)/4)*
         ((t*(1 - (3*xB)/2 + (xB + eps2/2.)/(2*sqrt(1 + eps2))))/pt.Q2 + (1 + eps2/2. - 
            sqrt(1 + eps2))/(2*sqrt(1 + eps2))))/
        sqrt(1 + eps2) + ((2 - y)**2*(2 - sqrt(1 + eps2))*
         (-((t*xB)/pt.Q2) + ((1 - t/pt.Q2)*
            (-1 + eps2 + sqrt(1 + eps2)))/
           (2*(2 - sqrt(1 + eps2)))))/(1 + eps2)))/
     (1 + eps2)**(3/2.)
    )
    
    CINT['unp', (-1, 1), (1)] = CINTunp211

    def CINTunp212(self, pt):
        """Same as CINT["unp", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*(2 - y)*(1 - y - (y**2*eps2)/4)*
      (1 + sqrt(1 + eps2))*
      (eps2*(1 + (t*(xB + (t*(1 - xB))/pt.Q2 + 
            sqrt(1 + eps2)))/(pt.Q2*
           (1 + sqrt(1 + eps2)))) + 
       (t*(2 - 3*xB + (t*xB*(1 - 2*xB + (2*(1 - xB))/(1 + sqrt(
                1 + eps2))))/pt.Q2))/
        pt.Q2))/(1 + eps2)**(5/2.)
    )
    
    CINT['unp', (-1, 1), (2)] = CINTunp212

    def CINTunp213(self, pt):
        """Same as CINT["unp", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*pt.K*(1 - y - (y**2*eps2)/4)*
      (1 + eps2/2. + sqrt(1 + eps2))*
      (1 + (t*xB*(1 + eps2/(2*xB) + sqrt(1 + eps2)))/
        (pt.Q2*(1 + eps2/2. + sqrt(1 + eps2)))))/
     (1 + eps2)**(5/2.)
    )
    
    CINT['unp', (-1, 1), (3)] = CINTunp213

    def CINTunp010(self, pt):
        """Same as CINT["unp", (0, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (12*sqrt(2)*pt.K*(2 - y)*
      sqrt(1 - y - (y**2*eps2)/4)*(eps2 + 
       (t*(2 - 6*xB - eps2))/(3*pt.Q2)))/
     (1 + eps2)**(5/2.)
    )
    
    CINT['unp', (0, 1), (0)] = CINTunp010

    def CINTunp011(self, pt):
        """Same as CINT["unp", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*sqrt(1 - y - (y**2*eps2)/4)*
      (((t - self.tmin(Q2, xB, eps2))*(2 - y)**2*(1 - xB + ((t - self.tmin(Q2, xB, eps2))*((1 - xB)*xB + 
             eps2/4))/(pt.Q2*sqrt(1 + eps2))))/
        pt.Q2 + ((1 - (t*(1 - 2*xB))/pt.Q2)*
         (1 - y - (y**2*eps2)/4)*(eps2 - 
          (2*t*xB*(1 + eps2/(2*xB)))/pt.Q2))/
        sqrt(1 + eps2)))/(1 + eps2)**2
    )
    
    CINT['unp', (0, 1), (1)] = CINTunp011

    def CINTunp012(self, pt):
        """Same as CINT["unp", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*sqrt(2)*pt.K*(2 - y)*(1 + eps2/2.)*
      sqrt(1 - y - (y**2*eps2)/4)*
      (1 + (t*xB*(1 + eps2/(2*xB)))/(pt.Q2*
         (1 + eps2/2.))))/(1 + eps2)**(5/2.)
    )
    
    CINT['unp', (0, 1), (2)] = CINTunp012

    def CINTunp013(self, pt):
        """Same as CINT["unp", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['unp', (0, 1), (3)] = CINTunp013

    def CINTunp110(self, pt):
        """Same as CINT["unp", (1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-4*(2 - y)*(1 + sqrt(1 + eps2))*
      ((pt.tK2*(2 - y)**2)/(pt.Q2*sqrt(1 + eps2)) + 
       (t*(2 - xB)*(1 - y - (y**2*eps2)/4)*
         (1 + (eps2 + (2*t*xB*(2 - xB + eps2/(2*xB) + 
               (-1 + sqrt(1 + eps2))/2))/pt.Q2)/
           ((2 - xB)*(1 + sqrt(1 + eps2)))))/pt.Q2))/
     (1 + eps2)**2
    )
    
    CINT['unp', (1, 1), (0)] = CINTunp110

    def CINTunp111(self, pt):
        """Same as CINT["unp", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-4*pt.K*(2 - 2*y + y**2 + (y**2*eps2)/2)*
       (1 - eps2 + sqrt(1 + eps2))*
       (1 - (t*(1 - 3*xB))/pt.Q2 + 
        (t*xB*(1 + 3*eps2 - sqrt(1 + eps2)))/
         (pt.Q2*(1 - eps2 + sqrt(1 + eps2)))))/
      (1 + eps2)**(5/2.) - (16*pt.K*(1 - y - (y**2*eps2)/4)*
       ((-3*eps2)/4 + (t*xB*(1 + eps2/(4*xB) + 
           ((1 - xB)*(-1 + sqrt(1 + eps2)))/(2*xB)))/
         pt.Q2))/(1 + eps2)**(5/2.)
    )
    
    CINT['unp', (1, 1), (1)] = CINTunp111

    def CINTunp112(self, pt):
        """Same as CINT["unp", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*(2 - y)*(1 - y - (y**2*eps2)/4)*
      ((2*pt.tK2*eps2)/(pt.Q2*(1 + eps2 + 
          sqrt(1 + eps2))) + (t*(t - self.tmin(Q2, xB, eps2))*xB*
         (1 - xB + eps2/(2*xB) + (1 - sqrt(1 + eps2))/2))/
        pt.Q2**2))/(1 + eps2)**2
    )
    
    CINT['unp', (1, 1), (2)] = CINTunp112

    def CINTunp113(self, pt):
        """Same as CINT["unp", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*pt.K*(1 - y - (y**2*eps2)/4)*
      (-1 + sqrt(1 + eps2))*((t*(1 - xB))/pt.Q2 + 
       ((1 + t/pt.Q2)*(-1 + sqrt(1 + eps2)))/2))/
     (1 + eps2)**(5/2.)
    )
    
    CINT['unp', (1, 1), (3)] = CINTunp113

    def CINTunpA210(self, pt):
        """Same as CINT["unpA", (-1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (-4*t*(2 - y)*(((t - self.tmin(Q2, xB, eps2))*(1 - y - (y**2*eps2)/4)*
         (-2*xB**2 + eps2 + xB*(3 - sqrt(1 + eps2))))/
        pt.Q2 + (pt.tK2*(-4 + 2*xB*(-2 + y)**2 + 4*y + 
          y**2*(-1 + sqrt(1 + eps2) + eps2*
             sqrt(1 + eps2))))/(pt.Q2*
         sqrt(1 + eps2))))/(pt.Q2*(1 + eps2)**2)
    )
    
    CINT['unpA', (-1, 1), (0)] = CINTunpA210

    def CINTunpA211(self, pt):
        """Same as CINT["unpA", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (4*pt.K*t*((2 - 2*y + y**2 + (y**2*eps2)/2)*
        (5 - 4*xB + 3*eps2 - sqrt(1 + eps2) - 
         (t*(1 - eps2 - sqrt(1 + eps2) - 
            2*xB*(4 - 4*xB - sqrt(1 + eps2))))/pt.Q2) + 
       (1 - y - (y**2*eps2)/4)*(8 + 5*eps2 + 
         2*xB*(-3 + sqrt(1 + eps2)) - 
         (t*(2 - eps2 + 2*sqrt(1 + eps2) - 
            4*xB*(3 - 3*xB + sqrt(1 + eps2))))/pt.Q2)))/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['unpA', (-1, 1), (1)] = CINTunpA211

    def CINTunpA212(self, pt):
        """Same as CINT["unpA", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-16*t*(2 - y)*(1 - y - (y**2*eps2)/4)*
      (-((pt.tK2*(1 - 2*xB))/(pt.Q2*(1 + eps2))) + 
       ((1 - xB)*(2*xB**2 - eps2 - xB*(3 + sqrt(1 + eps2))))/
        (4*(1 - xB)*xB + eps2) - 
       ((t - self.tmin(Q2, xB, eps2))*(-2*xB**2 + eps2 + 
          xB*(3 + sqrt(1 + eps2))))/(4*pt.Q2*
         sqrt(1 + eps2))))/(pt.Q2*
      (1 + eps2)**(3/2.))
    )
    
    CINT['unpA', (-1, 1), (2)] = CINTunpA212

    def CINTunpA213(self, pt):
        """Same as CINT["unpA", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (16*pt.K*t*(1 - y - (y**2*eps2)/4)*
      (1 - xB + ((t - self.tmin(Q2, xB, eps2))*((1 - xB)*xB + eps2/4))/
        (pt.Q2*sqrt(1 + eps2))))/
     (pt.Q2*(1 + eps2)**2)
    )
    
    CINT['unpA', (-1, 1), (3)] = CINTunpA213

    def CINTunpA010(self, pt):
        """Same as CINT["unpA", (0, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*sqrt(2)*pt.K*t*(2 - y)*
      (8 - 6*xB + 5*eps2)*sqrt(1 - y - (y**2*eps2)/4)*
      (1 - (t*(2 - 12*(1 - xB)*xB - eps2))/(pt.Q2*
         (8 - 6*xB + 5*eps2))))/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['unpA', (0, 1), (0)] = CINTunpA010

    def CINTunpA011(self, pt):
        """Same as CINT["unpA", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*t*sqrt(1 - y - (y**2*eps2)/4)*
      ((pt.tK2*(1 - 2*xB)*(2 - y)**2)/pt.Q2 + 
       (1 - (t*(1 - 2*xB))/pt.Q2)*
        (1 - y - (y**2*eps2)/4)*(4 - 2*xB + 3*eps2 + 
         (4*t*((1 - xB)*xB + eps2/4))/pt.Q2)))/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['unpA', (0, 1), (1)] = CINTunpA011

    def CINTunpA012(self, pt):
        """Same as CINT["unpA", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*pt.K*t*(2 - y)*
      sqrt(1 - y - (y**2*eps2)/4)*(1 - xB + 
       (2*(t - self.tmin(Q2, xB, eps2))*((1 - xB)*xB + eps2/4))/(pt.Q2*
         sqrt(1 + eps2))))/(pt.Q2*(1 + eps2)**2)
    )
    
    CINT['unpA', (0, 1), (2)] = CINTunpA012

    def CINTunpA013(self, pt):
        """Same as CINT["unpA", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['unpA', (0, 1), (3)] = CINTunpA013

    def CINTunpA110(self, pt):
        """Same as CINT["unpA", (1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (8*t*(2 - y)*((pt.tK2*(2 - y)**2*(1 - 2*xB + sqrt(1 + eps2)))/
        (2*pt.Q2*sqrt(1 + eps2)) + 
       (1 - y - (y**2*eps2)/4)*((-2*pt.tK2)/pt.Q2 + 
         ((1 + sqrt(1 + eps2))*(1 - xB + sqrt(1 + eps2) + 
            (t*(-1 + sqrt(1 + eps2) + (xB*(3 - 2*xB + 
                  sqrt(1 + eps2)))/(1 + sqrt(1 + eps2))))/
             pt.Q2))/2)))/(pt.Q2*
      (1 + eps2)**2)
    )
    
    CINT['unpA', (1, 1), (0)] = CINTunpA110

    def CINTunpA111(self, pt):
        """Same as CINT["unpA", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (-16*pt.K*t*((1 - y - (y**2*eps2)/4)*
        (1 - (t*(1 - 2*xB))/pt.Q2 + 
         ((t - self.tmin(Q2, xB, eps2))*(4*(1 - xB)*xB + eps2))/(4*pt.Q2*
           sqrt(1 + eps2))) - (2 - y)**2*(1 - xB/2 + 
         ((t - self.tmin(Q2, xB, eps2))*(4*(1 - xB)*xB + eps2))/(2*pt.Q2*
           sqrt(1 + eps2)) + ((1 - t/pt.Q2)*
           (1 - 2*xB + sqrt(1 + eps2)))/4)))/
     (pt.Q2*(1 + eps2)**2)
    )
    
    CINT['unpA', (1, 1), (1)] = CINTunpA111

    def CINTunpA112(self, pt):
        """Same as CINT["unpA", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*t*(2 - y)*(1 - y - (y**2*eps2)/4)*
      ((4*pt.tK2*(1 - 2*xB))/(pt.Q2*sqrt(1 + eps2)) - 
       ((t - self.tmin(Q2, xB, eps2))*xB*(3 - 2*xB + eps2/xB - sqrt(1 + eps2)))/
        pt.Q2))/(pt.Q2*(1 + eps2)**2)
    )
    
    CINT['unpA', (1, 1), (2)] = CINTunpA112

    def CINTunpA113(self, pt):
        """Same as CINT["unpA", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (16*pt.K*t*(t - self.tmin(Q2, xB, eps2))*((1 - xB)*xB + eps2/4)*
      (1 - y - (y**2*eps2)/4))/(pt.Q2**2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['unpA', (1, 1), (3)] = CINTunpA113

    def CINTunpV210(self, pt):
        """Same as CINT["unpV", (-1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (-4*t*xB*(2 - y)*((-2*pt.tK2*(2 - 2*y + y**2 + (y**2*eps2)/2))/
        pt.Q2 + (1 - (t*(1 - 2*xB))/pt.Q2)*
        (1 - y - (y**2*eps2)/4)*(1 + sqrt(1 + eps2))*
        ((-1 + sqrt(1 + eps2))/(1 + sqrt(1 + eps2)) + 
         (t*(1 - 2*xB + sqrt(1 + eps2)))/(pt.Q2*
           (1 + sqrt(1 + eps2))))))/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (-1, 1), (0)] = CINTunpV210

    def CINTunpV211(self, pt):
        """Same as CINT["unpV", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (8*pt.K*t*xB*(2*(1 - (t*(1 - 2*xB))/pt.Q2)*
        (2 - 2*y + y**2 + (y**2*eps2)/2) + 
       (1 - y - (y**2*eps2)/4)*(3 - sqrt(1 + eps2) - 
         (t*(3*(1 - 2*xB) + sqrt(1 + eps2)))/pt.Q2)))/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (-1, 1), (1)] = CINTunpV211

    def CINTunpV212(self, pt):
        """Same as CINT["unpV", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*t*xB*(2 - y)*(1 - y - (y**2*eps2)/4)*
      (1 + (4*pt.tK2)/pt.Q2 + sqrt(1 + eps2) + 
       (t*((t*(1 - 2*xB)*(1 - 2*xB - sqrt(1 + eps2)))/
           pt.Q2 - 2*(1 - xB*(2 + sqrt(1 + eps2)))))/
        pt.Q2))/(pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (-1, 1), (2)] = CINTunpV212

    def CINTunpV213(self, pt):
        """Same as CINT["unpV", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*pt.K*t*xB*(1 - y - (y**2*eps2)/4)*
      (1 + sqrt(1 + eps2))*
      (1 - (t*(1 - 2*xB - sqrt(1 + eps2)))/(pt.Q2*
         (1 + sqrt(1 + eps2)))))/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (-1, 1), (3)] = CINTunpV213

    def CINTunpV010(self, pt):
        """Same as CINT["unpV", (0, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (24*sqrt(2)*pt.K*t*xB*(2 - y)*
      (1 - (t*(1 - 2*xB))/pt.Q2)*
      sqrt(1 - y - (y**2*eps2)/4))/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (0, 1), (0)] = CINTunpV010

    def CINTunpV011(self, pt):
        """Same as CINT["unpV", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (16*sqrt(2)*t*xB*sqrt(1 - y - (y**2*eps2)/4)*
      ((pt.tK2*(2 - y)**2)/pt.Q2 + 
       (1 - (t*(1 - 2*xB)*(2 - (t*(1 - 2*xB))/pt.Q2))/
          pt.Q2)*(1 - y - (y**2*eps2)/4)))/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (0, 1), (1)] = CINTunpV011

    def CINTunpV012(self, pt):
        """Same as CINT["unpV", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*pt.K*t*xB*(2 - y)*
      (1 - (t*(1 - 2*xB))/pt.Q2)*
      sqrt(1 - y - (y**2*eps2)/4))/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (0, 1), (2)] = CINTunpV012

    def CINTunpV013(self, pt):
        """Same as CINT["unpV", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    CINT['unpV', (0, 1), (3)] = CINTunpV013

    def CINTunpV110(self, pt):
        """Same as CINT["unpV", (1, 1), (0)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (8*t*xB*(2 - y)*((pt.tK2*(2 - y)**2)/(pt.Q2*
         sqrt(1 + eps2)) + ((1 + t/pt.Q2)*
         (1 - y - (y**2*eps2)/4)*(1 + sqrt(1 + eps2))*
         (1 + (t*(-1 + 2*xB + sqrt(1 + eps2)))/(pt.Q2*
            (1 + sqrt(1 + eps2)))))/2))/(pt.Q2*
      (1 + eps2)**2)
    )
    
    CINT['unpV', (1, 1), (0)] = CINTunpV110

    def CINTunpV111(self, pt):
        """Same as CINT["unpV", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (16*pt.K*t*xB*((2 - y)**2*(1 - (t*(1 - 2*xB))/pt.Q2) + 
       ((t - self.tmin(Q2, xB, eps2))*(1 - y - (y**2*eps2)/4)*(1 - 2*xB + 
          sqrt(1 + eps2)))/(2*pt.Q2)))/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (1, 1), (1)] = CINTunpV111

    def CINTunpV112(self, pt):
        """Same as CINT["unpV", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*t*xB*(2 - y)*(1 - y - (y**2*eps2)/4)*
      ((4*pt.tK2)/(pt.Q2*sqrt(1 + eps2)) + 
       ((t - self.tmin(Q2, xB, eps2))*(1 + t/pt.Q2)*(1 - 2*xB + 
          sqrt(1 + eps2)))/(2*pt.Q2)))/
     (pt.Q2*(1 + eps2)**2)
    )
    
    CINT['unpV', (1, 1), (2)] = CINTunpV112

    def CINTunpV113(self, pt):
        """Same as CINT["unpV", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*pt.K*t*xB*(1 - y - (y**2*eps2)/4)*
      (-1 + sqrt(1 + eps2) + (t*(1 - 2*xB + sqrt(1 + eps2)))/
        pt.Q2))/(pt.Q2*(1 + eps2)**(5/2.))
    )
    
    CINT['unpV', (1, 1), (3)] = CINTunpV113

    def SINTLP211(self, pt):
        """Same as SINT["LP", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-pt.in2polarization)*((4*K)/(1 + eps2)**3)*
     ((-(2 - y)**2)*(-1 - 2*eps2 + sqrt(1 + eps2) + 
        (t*(-1 + 2*xB + sqrt(1 + eps2)))/pt.Q2) + 
      (1 - y - (y**2*eps2)/4)*(-2 - eps2 + 
        2*sqrt(1 + eps2) + 
        (t*(-eps2 + 4*sqrt(1 + eps2) - 
           2*xB*(1 + sqrt(1 + eps2))))/pt.Q2))
    )
    
    SINT['LP', (-1, 1), (1)] = SINTLP211

    def SINTLP212(self, pt):
        """Same as SINT["LP", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-pt.in2polarization)*
     ((4*(2 - y)*(1 - y - (y**2*eps2)/4))/(1 + eps2)**3)*
     (eps2*(1 + sqrt(1 + eps2)) + 
      (t*(2 + 2*sqrt(1 + eps2) + eps2*
          sqrt(1 + eps2) + xB*(-3 + eps2 - 
           3*sqrt(1 + eps2))))/pt.Q2 + 
      (t**2*(eps2 - 2*xB**2*(2 + sqrt(1 + eps2)) + 
         xB*(3 - eps2 + sqrt(1 + eps2))))/pt.Q2**2)
    )
    
    SINT['LP', (-1, 1), (2)] = SINTLP212

    def SINTLP213(self, pt):
        """Same as SINT["LP", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( pt.in2polarization*
     ((4*pt.K*(1 - y - (y**2*eps2)/4))/(1 + eps2)**3)*
     (2 + eps2 + 2*sqrt(1 + eps2) + 
      (t*(eps2 + 2*xB*(1 + sqrt(1 + eps2))))/
       pt.Q2)
    )
    
    SINT['LP', (-1, 1), (3)] = SINTLP213

    def SINTLP011(self, pt):
        """Same as SINT["LP", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( pt.in2polarization*
     ((8*sqrt(2)*sqrt(1 - y - (y**2*eps2)/4))/
      (1 + eps2)**(5/2.))*((pt.tK2*(2 - y)**2)/pt.Q2 + 
      (1 + t/pt.Q2)*(1 - y - (y**2*eps2)/4)*
       ((2*xB*t)/pt.Q2 - (1 - t/pt.Q2)*
         eps2))
    )
    
    SINT['LP', (0, 1), (1)] = SINTLP011

    def SINTLP012(self, pt):
        """Same as SINT["LP", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( pt.in2polarization*
     ((8*sqrt(2)*pt.K*(2 - y)*sqrt(1 - y - (y**2*eps2)/4))/
      (1 + eps2)**(5/2.))*(1 + (xB*t)/pt.Q2)
    )
    
    SINT['LP', (0, 1), (2)] = SINTLP012

    def SINTLP013(self, pt):
        """Same as SINT["LP", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['LP', (0, 1), (3)] = SINTLP013

    def SINTLP111(self, pt):
        """Same as SINT["LP", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    ((8*pt.K*pt.in2polarization*(2 - 2*y + y**2 + (y**2*eps2)/2))/
       (1 + eps2)**3)*((1 + sqrt(1 + eps2))/2)*
      (2*sqrt(1 + eps2) - 1 + (t/pt.Q2)*
        ((1 + sqrt(1 + eps2) - 2*xB)/(1 + sqrt(1 + eps2)))) + 
     ((8*pt.K*pt.in2polarization*(1 - y - (y**2*eps2)/4))/
       (1 + eps2)**3)*((3*eps2)/2 + 
       (1 - sqrt(1 + eps2) - eps2/2. - 
         xB*(3 - sqrt(1 + eps2)))*(t/pt.Q2))
    )
    
    SINT['LP', (1, 1), (1)] = SINTLP111

    def SINTLP112(self, pt):
        """Same as SINT["LP", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( ((-8*pt.in2polarization*(2 - y)*
       (1 - y - (y**2*eps2)/4))/(1 + eps2)**(5/2.))*
     ((2*pt.tK2)/(pt.Q2*sqrt(1 + eps2)) + 
      ((1 + sqrt(1 + eps2) - 2*xB)/2)*(1 + sqrt(1 + eps2) + 
        (xB*t)/pt.Q2)*((t - self.tmin(Q2, xB, eps2))/pt.Q2))
    )
    
    SINT['LP', (1, 1), (2)] = SINTLP112

    def SINTLP113(self, pt):
        """Same as SINT["LP", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    ((-8*pt.K*pt.in2polarization*(1 - y - (y**2*eps2)/4))/
      (1 + eps2)**3)*((1 + sqrt(1 + eps2) - 2*xB)/
      (2*(sqrt(1 + eps2) + 1)))*eps2*
     ((t - self.tmin(Q2, xB, eps2))/pt.Q2)
    )
    
    SINT['LP', (1, 1), (3)] = SINTLP113

    def SINTLPA211(self, pt):
        """Same as SINT["LPA", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*pt.K*t*xB*(1 - y - (y**2*eps2)/4)*
       (3 - sqrt(1 + eps2) - (t*(3 - 6*xB + sqrt(1 + eps2)))/
         pt.Q2)*pt.in2polarization)/(pt.Q2*
       (1 + eps2)**3) - 
     (8*pt.K*t*xB*(2 - 2*y + y**2 + (y**2*eps2)/2)*
       (1 + sqrt(1 + eps2))*
       (1 + (t*(-1 + 2*xB + sqrt(1 + eps2)))/(pt.Q2*
          (1 + sqrt(1 + eps2))))*pt.in2polarization)/
      (pt.Q2*(1 + eps2)**3)
    )
    
    SINT['LPA', (-1, 1), (1)] = SINTLPA211

    def SINTLPA212(self, pt):
        """Same as SINT["LPA", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-4*t*xB*(2 - y)*(1 - y - (y**2*eps2)/4)*
      (1 + (4*pt.tK2)/pt.Q2 + sqrt(1 + eps2) - 
       (t*(2 - (t*(1 - 2*xB)*(1 - 2*xB - sqrt(1 + eps2)))/
           pt.Q2 - 2*xB*(2 + sqrt(1 + eps2))))/
        pt.Q2)*pt.in2polarization)/(pt.Q2*
      (1 + eps2)**3)
    )
    
    SINT['LPA', (-1, 1), (2)] = SINTLPA212

    def SINTLPA213(self, pt):
        """Same as SINT["LPA", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*pt.K*t*xB*(1 - y - (y**2*eps2)/4)*
      (1 + sqrt(1 + eps2) - (t*(1 - 2*xB - sqrt(1 + eps2)))/
        pt.Q2)*pt.in2polarization)/(pt.Q2*
      (1 + eps2)**3)
    )
    
    SINT['LPA', (-1, 1), (3)] = SINTLPA213

    def SINTLPA011(self, pt):
        """Same as SINT["LPA", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-16*sqrt(2)*t*xB*(1 + t/pt.Q2)*
      (1 - (t*(1 - 2*xB))/pt.Q2)*(1 - y - (y**2*eps2)/4)**
       (3/2.)*pt.in2polarization)/(pt.Q2*(1 + eps2)**(5/2.))
    )
    
    SINT['LPA', (0, 1), (1)] = SINTLPA011

    def SINTLPA012(self, pt):
        """Same as SINT["LPA", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*sqrt(2)*pt.K*t*xB*(2 - y)*
      (1 + t/pt.Q2)*sqrt(1 - y - (y**2*eps2)/4)*
      pt.in2polarization)/(pt.Q2*(1 + eps2)**(5/2.))
    )
    
    SINT['LPA', (0, 1), (2)] = SINTLPA012

    def SINTLPA013(self, pt):
        """Same as SINT["LPA", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['LPA', (0, 1), (3)] = SINTLPA013

    def SINTLPA111(self, pt):
        """Same as SINT["LPA", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*pt.K*t*xB*(1 - y - (y**2*eps2)/4)*
       (3 + sqrt(1 + eps2))*
       (1 - (t*(3 - 6*xB - sqrt(1 + eps2)))/(pt.Q2*
          (3 + sqrt(1 + eps2))))*pt.in2polarization)/
      (pt.Q2*(1 + eps2)**3) - 
     (8*pt.K*t*xB*(2 - 2*y + y**2 + (y**2*eps2)/2)*
       (-1 + sqrt(1 + eps2) + (t*(1 - 2*xB + sqrt(1 + eps2)))/
         pt.Q2)*pt.in2polarization)/(pt.Q2*
       (1 + eps2)**3)
    )
    
    SINT['LPA', (1, 1), (1)] = SINTLPA111

    def SINTLPA112(self, pt):
        """Same as SINT["LPA", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*t*xB*(2 - y)*(1 - y - (y**2*eps2)/4)*
      ((2*pt.tK2)/pt.Q2 - 
       ((t - self.tmin(Q2, xB, eps2))*(1 - (t*(1 - 2*xB))/pt.Q2)*
         (1 - 2*xB + sqrt(1 + eps2)))/(2*pt.Q2))*
      pt.in2polarization)/(pt.Q2*(1 + eps2)**3)
    )
    
    SINT['LPA', (1, 1), (2)] = SINTLPA112

    def SINTLPA113(self, pt):
        """Same as SINT["LPA", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*pt.K*t*(t - self.tmin(Q2, xB, eps2))*xB*
      (1 - y - (y**2*eps2)/4)*(1 - 2*xB + sqrt(1 + eps2))*
      pt.in2polarization)/(pt.Q2**2*(1 + eps2)**3)
    )
    
    SINT['LPA', (1, 1), (3)] = SINTLPA113

    def SINTLPV211(self, pt):
        """Same as SINT["LPV", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (-4*pt.K*t*((2 - 2*y + y**2 + (y**2*eps2)/2)*(3 + 2*eps2 + 
         sqrt(1 + eps2) - 2*xB*(1 + sqrt(1 + eps2)) + 
         (t*(1 - 2*xB)*(-1 + 2*xB + sqrt(1 + eps2)))/
          pt.Q2) + (1 - y - (y**2*eps2)/4)*
        (8 + 5*eps2 + 2*xB*(-3 + sqrt(1 + eps2)) - 
         (t*(2 - eps2 + 2*sqrt(1 + eps2) - 
            4*xB*(3*(1 - xB) + sqrt(1 + eps2))))/sqrt(pt.Q2)**
           2))*pt.in2polarization)/(pt.Q2*(1 + eps2)**3)
    )
    
    SINT['LPV', (-1, 1), (1)] = SINTLPV211

    def SINTLPV212(self, pt):
        """Same as SINT["LPV", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-4*t*(2 - y)*(1 - y - (y**2*eps2)/4)*
      (2 + eps2 + (4*pt.tK2*(1 - 2*xB))/(pt.Q2*
         sqrt(1 + eps2)) + 2*sqrt(1 + eps2) - 
       xB*(1 + sqrt(1 + eps2)) + 
       (t*(eps2 + xB*(3 - 2*xB + sqrt(1 + eps2))))/
        pt.Q2)*pt.in2polarization)/(pt.Q2*
      (1 + eps2)**(5/2.))
    )
    
    SINT['LPV', (-1, 1), (2)] = SINTLPV212

    def SINTLPV213(self, pt):
        """Same as SINT["LPV", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-16*pt.K*t*(1 - y - (y**2*eps2)/4)*
      (1 - xB + ((t - self.tmin(Q2, xB, eps2))*((1 - xB)*xB + eps2/4))/
        (pt.Q2*sqrt(1 + eps2)))*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    SINT['LPV', (-1, 1), (3)] = SINTLPV213

    def SINTLPV011(self, pt):
        """Same as SINT["LPV", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*sqrt(2)*t*sqrt(1 - y - (y**2*eps2)/4)*
      ((pt.tK2*(2 - y)**2)/pt.Q2 + (1 + t/pt.Q2)*
        (1 - y - (y**2*eps2)/4)*(4 - 2*xB + 3*eps2 + 
         (t*(4*xB - 4*xB**2 + eps2))/pt.Q2))*
      pt.in2polarization)/(pt.Q2*(1 + eps2)**(5/2.))
    )
    
    SINT['LPV', (0, 1), (1)] = SINTLPV011

    def SINTLPV012(self, pt):
        """Same as SINT["LPV", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*sqrt(2)*pt.K*t*(1 - xB)*(2 - y)*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in2polarization)/
     (pt.Q2*(1 + eps2)**(5/2.))
    )
    
    SINT['LPV', (0, 1), (2)] = SINTLPV012

    def SINTLPV013(self, pt):
        """Same as SINT["LPV", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['LPV', (0, 1), (3)] = SINTLPV013

    def SINTLPV111(self, pt):
        """Same as SINT["LPV", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*pt.K*t*(2 - 2*y + y**2 + (y**2*eps2)/2)*
       (1 - ((t - self.tmin(Q2, xB, eps2))*(1 - 2*xB)*(1 - 2*xB + sqrt(1 + eps2)))/
         (2*pt.Q2*(1 + eps2)))*pt.in2polarization)/
      (pt.Q2*(1 + eps2)**2) + 
     (32*pt.K*t*(1 - y - (y**2*eps2)/4)*(1 + (5*eps2)/8 - 
        (xB*(3 + sqrt(1 + eps2)))/4)*
       (1 - (t*(1 - eps2/2. - sqrt(1 + eps2) - 
           2*xB*(3*(1 - xB) - sqrt(1 + eps2))))/(pt.Q2*
          (4 + (5*eps2)/2 - xB*(3 + sqrt(1 + eps2)))))*
       pt.in2polarization)/(pt.Q2*(1 + eps2)**3)
    )
    
    SINT['LPV', (1, 1), (1)] = SINTLPV111

    def SINTLPV112(self, pt):
        """Same as SINT["LPV", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*t*(2 - y)*(1 - y - (y**2*eps2)/4)*
      ((4*pt.tK2*(1 - 2*xB))/(pt.Q2*sqrt(1 + eps2)) - 
       ((t - self.tmin(Q2, xB, eps2))*(-2*xB**2 + eps2 + 
          xB*(3 - sqrt(1 + eps2))))/pt.Q2)*
      pt.in2polarization)/(pt.Q2*(1 + eps2)**(5/2.))
    )
    
    SINT['LPV', (1, 1), (2)] = SINTLPV112

    def SINTLPV113(self, pt):
        """Same as SINT["LPV", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (16*pt.K*t*(t - self.tmin(Q2, xB, eps2))*((1 - xB)*xB + eps2/4)*
      (1 - y - (y**2*eps2)/4)*pt.in2polarization)/
     (pt.Q2**2*(1 + eps2)**3)
    )
    
    SINT['LPV', (1, 1), (3)] = SINTLPV113

    def SINTunp211(self, pt):
        """Same as SINT["unp", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*pt.K*(2 - y)*y*(1 + 2*eps2 - 
       sqrt(1 + eps2) - (2*t*xB*(1 + (-1 + sqrt(1 + eps2))/
           (2*xB)))/pt.Q2)*pt.in1polarization)/(1 + eps2)**2
    )
    
    SINT['unp', (-1, 1), (1)] = SINTunp211

    def SINTunp212(self, pt):
        """Same as SINT["unp", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (2*y*(1 - y - (y**2*eps2)/4)*
      (1 + sqrt(1 + eps2))*(eps2 - 
       (2*t*xB*(1 + eps2/(2*xB)))/pt.Q2)*
      (1 + (t*(-1 + 2*xB + sqrt(1 + eps2)))/(pt.Q2*
         (1 + sqrt(1 + eps2))))*pt.in1polarization)/(1 + eps2)**2
    )
    
    SINT['unp', (-1, 1), (2)] = SINTunp212

    def SINTunp213(self, pt):
        """Same as SINT["unp", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unp', (-1, 1), (3)] = SINTunp213

    def SINTunp011(self, pt):
        """Same as SINT["unp", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*pt.tK2*(2 - y)*y*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization)/
     (pt.Q2*(1 + eps2)**2)
    )
    
    SINT['unp', (0, 1), (1)] = SINTunp011

    def SINTunp012(self, pt):
        """Same as SINT["unp", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*sqrt(2)*pt.K*y*(1 + eps2/2.)*
      sqrt(1 - y - (y**2*eps2)/4)*
      (1 + (t*xB*(1 + eps2/(2*xB)))/(pt.Q2*
         (1 + eps2/2.)))*pt.in1polarization)/(1 + eps2)**2
    )
    
    SINT['unp', (0, 1), (2)] = SINTunp012

    def SINTunp013(self, pt):
        """Same as SINT["unp", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unp', (0, 1), (3)] = SINTunp013

    def SINTunp111(self, pt):
        """Same as SINT["unp", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (8*pt.K*(2 - y)*y*(1 + ((t - self.tmin(Q2, xB, eps2))*(1 - xB + (-1 + sqrt(1 + eps2))/
           2))/(pt.Q2*(1 + eps2)))*pt.in1polarization)/
     (1 + eps2)
    )
    
    SINT['unp', (1, 1), (1)] = SINTunp111

    def SINTunp112(self, pt):
        """Same as SINT["unp", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-4*(t - self.tmin(Q2, xB, eps2))*y*(1 - y - (y**2*eps2)/4)*
      (1 - 2*xB + sqrt(1 + eps2))*
      (-((t - self.tmin(Q2, xB, eps2))*(2*xB + eps2))/(2*pt.Q2*
         sqrt(1 + eps2)) + (eps2 - 
         xB*(-1 + sqrt(1 + eps2)))/(1 - 2*xB + 
         sqrt(1 + eps2)))*pt.in1polarization)/(pt.Q2*
      (1 + eps2)**(3/2.))
    )
    
    SINT['unp', (1, 1), (2)] = SINTunp112

    def SINTunp113(self, pt):
        """Same as SINT["unp", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unp', (1, 1), (3)] = SINTunp113

    def SINTunpA211(self, pt):
        """Same as SINT["unpA", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*pt.K*t*(2 - y)*y*(3 + 2*eps2 + 
       sqrt(1 + eps2) - 2*xB*(1 + sqrt(1 + eps2)) + 
       (t*(1 - 2*xB)*(-1 + 2*xB + sqrt(1 + eps2)))/
        pt.Q2)*pt.in1polarization)/(pt.Q2*
      (1 + eps2)**2)
    )
    
    SINT['unpA', (-1, 1), (1)] = SINTunpA211

    def SINTunpA212(self, pt):
        """Same as SINT["unpA", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (2*t*y*(1 - y - (y**2*eps2)/4)*
      (4 - 2*xB + 3*eps2 + (t*(4*xB - 4*xB**2 + eps2))/
        pt.Q2)*(1 + sqrt(1 + eps2) + 
       (t*(-1 + 2*xB + sqrt(1 + eps2)))/pt.Q2)*
      pt.in1polarization)/(pt.Q2*(1 + eps2)**2)
    )
    
    SINT['unpA', (-1, 1), (2)] = SINTunpA212

    def SINTunpA213(self, pt):
        """Same as SINT["unpA", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unpA', (-1, 1), (3)] = SINTunpA213

    def SINTunpA011(self, pt):
        """Same as SINT["unpA", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*sqrt(2)*t*pt.tK2*(1 - 2*xB)*(2 - y)*y*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization)/
     (pt.Q2**2*(1 + eps2)**2)
    )
    
    SINT['unpA', (0, 1), (1)] = SINTunpA011

    def SINTunpA012(self, pt):
        """Same as SINT["unpA", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-2*sqrt(2)*pt.K*t*y*
      sqrt(1 - y - (y**2*eps2)/4)*(4 - 4*xB + 2*eps2 + 
       (2*t*(4*xB - 4*xB**2 + eps2))/pt.Q2)*pt.in1polarization)/
     (pt.Q2*(1 + eps2)**2)
    )
    
    SINT['unpA', (0, 1), (2)] = SINTunpA012

    def SINTunpA013(self, pt):
        """Same as SINT["unpA", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unpA', (0, 1), (3)] = SINTunpA013

    def SINTunpA111(self, pt):
        """Same as SINT["unpA", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( ((8*pt.in1polarization*pt.K*(2 - y)*y)/(1 + eps2))*
     (t/pt.Q2)*(1 - (1 - 2*xB)*((1 + sqrt(1 + eps2) - 
         2*xB)/(2*(1 + eps2)))*((t - self.tmin(Q2, xB, eps2))/pt.Q2))
    )
    
    SINT['unpA', (1, 1), (1)] = SINTunpA111

    def SINTunpA112(self, pt):
        """Same as SINT["unpA", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (-((16*pt.in1polarization*(1 - y - (y**2*eps2)/4)*y)/(1 + eps2)**2))*
     (t/pt.Q2)*((t - self.tmin(Q2, xB, eps2))/pt.Q2)*
     (1 - xB/2 + (3*eps2)/4)*((1 + sqrt(1 + eps2) - 2*xB)/2)*
     (1 + ((4*(1 - xB)*xB + eps2)/(4 - 2*xB + 3*eps2))*
       (t/pt.Q2))
    )
    
    SINT['unpA', (1, 1), (2)] = SINTunpA112

    def SINTunpA113(self, pt):
        """Same as SINT["unpA", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unpA', (1, 1), (3)] = SINTunpA113

    def SINTunpV211(self, pt):
        """Same as SINT["unpV", (-1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (8*pt.K*t*xB*(2 - y)*y*(1 + sqrt(1 + eps2))*
      (1 + (t*(-1 + 2*xB + sqrt(1 + eps2)))/(pt.Q2*
         (1 + sqrt(1 + eps2))))*pt.in1polarization)/(pt.Q2*
      (1 + eps2)**2)
    )
    
    SINT['unpV', (-1, 1), (1)] = SINTunpV211

    def SINTunpV212(self, pt):
        """Same as SINT["unpV", (-1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (4*t*xB*y*(1 - (t*(1 - 2*xB))/pt.Q2)*
      (1 - y - (y**2*eps2)/4)*(1 + sqrt(1 + eps2))*
      (1 + (t*(-1 + 2*xB + sqrt(1 + eps2)))/(pt.Q2*
         (1 + sqrt(1 + eps2))))*pt.in1polarization)/(pt.Q2*
      (1 + eps2)**2)
    )
    
    SINT['unpV', (-1, 1), (2)] = SINTunpV212

    def SINTunpV213(self, pt):
        """Same as SINT["unpV", (-1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unpV', (-1, 1), (3)] = SINTunpV213

    def SINTunpV011(self, pt):
        """Same as SINT["unpV", (0, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (4*sqrt(2)*t*xB*(2 - y)*y*
      sqrt(1 - y - (y**2*eps2)/4)*
      ((4*t*(1 - xB)*(1 + (t*xB)/pt.Q2))/pt.Q2 + 
       (1 + t/pt.Q2)**2*eps2)*pt.in1polarization)/
     (pt.Q2*(1 + eps2)**2)
    )
    
    SINT['unpV', (0, 1), (1)] = SINTunpV011

    def SINTunpV012(self, pt):
        """Same as SINT["unpV", (0, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-8*sqrt(2)*pt.K*t*xB*y*
      (1 - (t*(1 - 2*xB))/pt.Q2)*
      sqrt(1 - y - (y**2*eps2)/4)*pt.in1polarization)/
     (pt.Q2*(1 + eps2)**2)
    )
    
    SINT['unpV', (0, 1), (2)] = SINTunpV012

    def SINTunpV013(self, pt):
        """Same as SINT["unpV", (0, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unpV', (0, 1), (3)] = SINTunpV013

    def SINTunpV111(self, pt):
        """Same as SINT["unpV", (1, 1), (1)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( (-((8*pt.K*(2 - y)*y*xB*pt.in1polarization)/
       (1 + eps2)**2))*(t/pt.Q2)*
     (sqrt(1 + eps2) - 1 + (1 + sqrt(1 + eps2) - 2*xB)*
       (t/pt.Q2))
    )
    
    SINT['unpV', (1, 1), (1)] = SINTunpV111

    def SINTunpV112(self, pt):
        """Same as SINT["unpV", (1, 1), (2)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 
    (-((4*(1 - y - (y**2*eps2)/4)*y*xB*pt.in1polarization)/
       (1 + eps2)**2))*(t/pt.Q2)*
     (1 - (1 - 2*xB)*(t/pt.Q2))*(sqrt(1 + eps2) - 1 + 
      (1 + sqrt(1 + eps2) - 2*xB)*(t/pt.Q2))
    )
    
    SINT['unpV', (1, 1), (2)] = SINTunpV112

    def SINTunpV113(self, pt):
        """Same as SINT["unpV", (1, 1), (3)] """

        
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        return ( 0
    )
    
    SINT['unpV', (1, 1), (3)] = SINTunpV113

    def cINTunp(self, pt, n):
        """BM10 (2.35) and (2.36)."""

        return (
         self.CINT["unp", (1, 1), n](self, pt) * self.CCALINTunp(pt) +
         self.CINT["unpV", (1, 1), n](self, pt) * self.CCALINTunpV(pt) +
         self.CINT["unpA", (1, 1), n](self, pt) * self.CCALINTunpA(pt) +
         sqrt(2.)/(2.-pt.xB+pt.xB*pt.t/pt.Q2)*pt.tK/sqrt(pt.Q2)*(
         self.CINT["unp", (0, 1), n](self, pt) * self.CCALINTunp(pt, eff=1) +
         self.CINT["unpV", (0, 1), n](self, pt) * self.CCALINTunpV(pt, eff=1) +
         self.CINT["unpA", (0, 1), n](self, pt) * self.CCALINTunpV(pt, eff=1) )
         )

    def sINTunp(self, pt, n):
        """BM10 (2.35) and (2.36)."""

        return (
         self.SINT["unp", (1, 1), n](self, pt) * self.CCALINTunp(pt, im=1) +
         self.SINT["unpV", (1, 1), n](self, pt) * self.CCALINTunpV(pt, im=1) +
         self.SINT["unpA", (1, 1), n](self, pt) * self.CCALINTunpA(pt, im=1) +
         sqrt(2.)/(2.-pt.xB+pt.xB*pt.t/pt.Q2)*pt.tK/sqrt(pt.Q2)*(
         self.SINT["unp", (0, 1), n](self, pt) * self.CCALINTunp(pt, im=1, eff=1) +
         self.SINT["unpV", (0, 1), n](self, pt) * self.CCALINTunpV(pt, im=1, eff=1) +
         self.SINT["unpA", (0, 1), n](self, pt) * self.CCALINTunpA(pt, im=1, eff=1) )
         )

    def cINT0unp(self, pt): return self.cINTunp(pt, 0)
    def cINT1unp(self, pt): return self.cINTunp(pt, 1)
    def cINT2unp(self, pt): return self.cINTunp(pt, 2)
    def cINT3unp(self, pt): return self.cINTunp(pt, 3)
    def sINT1unp(self, pt): return self.sINTunp(pt, 1)
    def sINT2unp(self, pt): return self.sINTunp(pt, 2)
    def sINT3unp(self, pt): return self.sINTunp(pt, 3)

    def cINTLP(self, pt, n):
        """BM10 (2.35) and (2.36)."""

        return (
         self.CINT["LP", (1, 1), n](self, pt) * self.CCALINTLP(pt) +
         self.CINT["LPV", (1, 1), n](self, pt) * self.CCALINTLPV(pt) +
         self.CINT["LPA", (1, 1), n](self, pt) * self.CCALINTLPA(pt) +
         sqrt(2.)/(2.-pt.xB+pt.xB*pt.t/pt.Q2)*pt.tK/sqrt(pt.Q2)*(
         self.CINT["LP", (0, 1), n](self, pt) * self.CCALINTLP(pt, eff=1) +
         self.CINT["LPV", (0, 1), n](self, pt) * self.CCALINTLPV(pt, eff=1) +
         self.CINT["LPA", (0, 1), n](self, pt) * self.CCALINTLPV(pt, eff=1) )
         )

    def sINTLP(self, pt, n):
        """BM10 (2.35) and (2.36)."""

        return (
         self.SINT["LP", (1, 1), n](self, pt) * self.CCALINTLP(pt, im=1) +
         self.SINT["LPV", (1, 1), n](self, pt) * self.CCALINTLPV(pt, im=1) +
         self.SINT["LPA", (1, 1), n](self, pt) * self.CCALINTLPA(pt, im=1) +
         sqrt(2.)/(2.-pt.xB+pt.xB*pt.t/pt.Q2)*pt.tK/sqrt(pt.Q2)*(
         self.SINT["LP", (0, 1), n](self, pt) * self.CCALINTLP(pt, im=1, eff=1) +
         self.SINT["LPV", (0, 1), n](self, pt) * self.CCALINTLPV(pt, im=1, eff=1) +
         self.SINT["LPA", (0, 1), n](self, pt) * self.CCALINTLPV(pt, im=1, eff=1) )
         )

    def cINT0LP(self, pt): return self.cINTLP(pt, 0)
    def cINT1LP(self, pt): return self.cINTLP(pt, 1)
    def cINT2LP(self, pt): return self.cINTLP(pt, 2)
    def cINT3LP(self, pt): return self.cINTLP(pt, 3)
    def sINT1LP(self, pt): return self.sINTLP(pt, 1)
    def sINT2LP(self, pt): return self.sINTLP(pt, 2)
    def sINT3LP(self, pt): return self.sINTLP(pt, 3)

    def TINTunp(self, pt):
        """ BH-DVCS interference. BM10 Eq. (2.34)"""

        return  - pt.in1charge * self.PreFacINT(pt) * ( self.cINT0unp(pt)  
                + self.cINT1unp(pt) * cos(pt.phi)
                + self.cINT2unp(pt) * cos(2.*pt.phi) 
                + self.cINT3unp(pt) * cos(3.*pt.phi) 
                + self.sINT1unp(pt) * sin(pt.phi)
                + self.sINT2unp(pt) * sin(2.*pt.phi)
                + self.sINT3unp(pt) * sin(3.*pt.phi)
                )

    def TINTLP(self, pt):
        """ BH-DVCS interference. BM10 Eq. (2.34)"""

        return  - pt.in1charge * self.PreFacINT(pt) * (self.cINT0LP(pt)  
                + self.cINT1LP(pt) * cos(pt.phi)
                + self.cINT2LP(pt) * cos(2.*pt.phi) 
                + self.cINT3LP(pt) * cos(3.*pt.phi) 
                + self.sINT1LP(pt) * sin(pt.phi)
                + self.sINT2LP(pt) * sin(2.*pt.phi)
                + self.sINT3LP(pt) * sin(3.*pt.phi)
                )

    #### OBSERVABLES
           
    def XLP(self, pt, **kwargs):
        """ Calculate 4-fold differential cross section for polarized target. 

        FIXME: Is this 'phi' bussiness below ugly?
        FIXME: Code should be merged with Xunp above taking into account
               pt.in2polarization
        
        """
        if kwargs.has_key('vars'):
            ptvars = Data.DummyPoint(init=kwargs['vars'])
            kin = utils.fill_kinematics(ptvars, old=pt)
            BMK.prepare(kin)
        else:
            # just copy everything from pt
            ptempty = Data.DummyPoint()
            kin = utils.fill_kinematics(ptempty, old=pt)
            BMK.prepare(kin)
            ## Nothing seems to be gained by following approach:
            #kin = dict((i, getattr(pt, i)) for i in 
            #        ['xB', 'Q2', 'W', 's', 't', 'mt', 'phi', 'in1charge',
            #            'in1polarization', 'in2particle'])

        # copy non-kinematical info
        for atr in ['in1charge', 'in1polarization', 'in2polarization']:
            if pt.has_key(atr):
                setattr(kin, atr, getattr(pt, atr))

        if kwargs.has_key('zeropolarized') and kwargs['zeropolarized']:
            kin.in1polarization = 0

        if kwargs.has_key('flip') and kwargs['flip']:
            if isinstance(kwargs['flip'], list):
                for item in kwargs['flip']:
                    setattr(kin, item, - getattr(pt, item))
            else:
                setattr(kin, kwargs['flip'], - getattr(pt, kwargs['flip']))

        if kwargs.has_key('weighted') and kwargs['weighted']:
            wgh = self.w(kin)
        else:
            wgh = 1

        # Gepard needs resetting
        if self.model.__dict__.has_key('Gepard'): self.m.g.newcall = 1

        #print 'BH2 = ' + str(self.PreFacSigma(kin) *self.TBH2LP(kin))
        #print 'DVCS2 = ' + str(self.PreFacSigma(kin) *self.TDVCS2LP(kin))
        #print 'INT = ' + str(self.PreFacSigma(kin) *self.TINTLP(kin))
        return wgh * self.PreFacSigma(kin) * ( self.TBH2LP(kin) 
                + self.TINTLP(kin) 
                + self.TDVCS2LP(kin) )

    def _TSA(self, pt, **kwargs):
        """Calculate target spin asymmetry (TSA)."""

        kwargs.update({'zeropolarized':True})
        return self.XLP(pt, **kwargs) / self.Xunp(pt, **kwargs)

    def TSA(self, pt, **kwargs):
        """Calculate target spin asymmetry or its harmonics."""
        if pt.has_key('phi'):
            return self._TSA(pt, **kwargs)
        elif pt.has_key('FTn'):
            if pt.FTn < 0:
                res = quadrature.Hquadrature(lambda phi: 
                        self._TSA(pt, vars={'phi':phi}) * sin(-pt.FTn*phi), 0, 2*pi)
            elif pt.FTn > 0:
                res = quadrature.Hquadrature(lambda phi: 
                        self._TSA(pt, vars={'phi':phi}) * cos(pt.FTn*phi), 0, 2*pi)
            elif pt.FTn == 0:
                res = quadrature.Hquadrature(lambda phi: 
                        self._TSA(pt, vars={'phi':phi}), 0, 2*pi)/2.
            else:
                raise ValeError('This should never happen!')
            return  res / pi
        else:
            raise ValueError('[%s] has neither azimuthal angle phi\
 nor harmonic FTn defined!' % pt)

                    
    def _BTSA(self, pt, **kwargs):
        """Calculate beam-target spin asymmetry (BTSA)."""

        R = kwargs.copy()
        R.update({'flip':'in1polarization'})
        return (
           self.XLP(pt, **kwargs) 
             - self.XLP(pt, **R) )/(
           self.Xunp(pt, **kwargs )
             + self.Xunp(pt, **R) )

    def BTSA(self, pt, **kwargs):
        """Calculate beam-target spin asymmetry or its harmonics."""
        if pt.has_key('phi'):
            return self._BTSA(pt, **kwargs)
        elif pt.has_key('FTn'):
            if pt.FTn < 0:
                res = quadrature.Hquadrature(lambda phi: 
                        self._BTSA(pt, vars={'phi':phi}) * sin(-pt.FTn*phi), 0, 2*pi)
            elif pt.FTn > 0:
                res = quadrature.Hquadrature(lambda phi: 
                        self._BTSA(pt, vars={'phi':phi}) * cos(pt.FTn*phi), 0, 2*pi)
            elif pt.FTn == 0:
                res = quadrature.Hquadrature(lambda phi: 
                        self._BTSA(pt, vars={'phi':phi}), 0, 2*pi)/2.
            else:
                raise ValeError('This should never happen!')
            return  res / pi
        else:
            raise ValueError('[%s] has neither azimuthal angle phi\
 nor harmonic FTn defined!' % pt)


class BM10(BM10ex):
    """According to BM arXiv:1005.5209 [hep-ph]
    
    This is BM10ex, but with Q2-suppressed terms in CCAL coefs. removed
    """

    def CCALDVCSunp(self, pt, im=0, leff=0, reff=0): 
        """ BM10 (2.22), with 1/Q2 suppressed terms removed """

        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        if leff:
            H = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            EE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            tH = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            tE = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            H = complex(self.m.ReH(pt), self.m.ImH(pt))
            EE = complex(self.m.ReE(pt), self.m.ImE(pt))
            tH = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            tE = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        if reff:
            HCC = complex(self.m.ReHeff(pt), -self.m.ImHeff(pt))
            EECC = complex(self.m.ReEeff(pt), -self.m.ImEeff(pt))
            tHCC = complex(self.m.ReHteff(pt), -self.m.ImHteff(pt))
            tECC = complex(self.m.ReEteff(pt), -self.m.ImEteff(pt))
        else:
            HCC = complex(self.m.ReH(pt), -self.m.ImH(pt))
            EECC = complex(self.m.ReE(pt), -self.m.ImE(pt))
            tHCC = complex(self.m.ReHt(pt), -self.m.ImHt(pt))
            tECC = complex(self.m.ReEt(pt), -self.m.ImEt(pt))
        res = (4.*(1.-xB)*(H*HCC+tH*tHCC) 
                - xB**2*(H*EECC+EE*HCC+tH*tECC+tE*tHCC)
                - (xB**2+(2.-xB)**2*t/(4.*Mp2))*EE*EECC
                - xB**2*t/(4.*Mp2)*tE*tECC) / (2.-xB)**2
        if im:
            return res.imag
        else:
            return res.real

    def CCALDVCSLP(self, pt, im=0, leff=0, reff=0): 
        """ BM10 (2.22), with 1/Q2 suppressed terms removed """

        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        if leff:
            H = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            EE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            tH = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            tE = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            H = complex(self.m.ReH(pt), self.m.ImH(pt))
            EE = complex(self.m.ReE(pt), self.m.ImE(pt))
            tH = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            tE = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        if reff:
            HCC = complex(self.m.ReHeff(pt), -self.m.ImHeff(pt))
            EECC = complex(self.m.ReEeff(pt), -self.m.ImEeff(pt))
            tHCC = complex(self.m.ReHteff(pt), -self.m.ImHteff(pt))
            tECC = complex(self.m.ReEteff(pt), -self.m.ImEteff(pt))
        else:
            HCC = complex(self.m.ReH(pt), -self.m.ImH(pt))
            EECC = complex(self.m.ReE(pt), -self.m.ImE(pt))
            tHCC = complex(self.m.ReHt(pt), -self.m.ImHt(pt))
            tECC = complex(self.m.ReEt(pt), -self.m.ImEt(pt))
        res = (4.*(1.-xB)*(H*tHCC+tH*HCC) 
                - xB**2*(H*tECC+tE*HCC+tH*EECC+EE*tHCC)
                - xB*(xB**2/2.+(2.-xB)*t/(4.*Mp2))*(EE*tECC+tE*EECC)
                ) / (2.-xB)**2
        if im:
            return res.imag
        else:
            return res.real

    def CCALINTunp(self, pt, im=0, eff=0):
        """ BM10 Eq. (2.28) with 1/Q2 suppressed terms removed """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
            self.m.F1(t)*CFFH - (t/(4*Mp2))*self.m.F2(t)*CFFE + 
              xB/(2 - xB)*(self.m.F1(t) + self.m.F2(t))*CFFHt
              )
        if im:
            return res.imag
        else:
            return res.real
    
    def CCALINTunpV(self, pt, im=0, eff=0):
        """ BM10 Eq. (2.29) with 1/Q2 suppressed terms removed """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
        xB/(2 - xB)*(self.m.F1(t) + self.m.F2(t)) * (CFFH + CFFE)
              )
        if im:
            return res.imag
        else:
            return res.real
    

    def CCALINTunpA(self, pt, im=0, eff=0):
        """ BM10 ... with 1/Q2 suppressed terms removed """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
    (xB/(2 - xB))*(self.m.F1(t) + self.m.F2(t))*CFFHt
    )
        if im:
            return res.imag
        else:
            return res.real
    

    def CCALINTLP(self, pt, im=0, eff=0):
        """ BM10 ... with 1/Q2 suppressed terms removed """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
          xB/(2 - xB)*(self.m.F1(t) + self.m.F2(t))*(CFFH + (xB/2)*CFFE) 
          + self.m.F1(t)*CFFHt 
          - xB/(2 - xB)*((xB/2)*self.m.F1(t) 
                   + (t/(4*Mp2))*self.m.F2(t))*CFFEt
              )
        if im:
            return res.imag
        else:
            return res.real
    

    def CCALINTLPV(self, pt, im=0, eff=0):
        """ BM10 ... with 1/Q2 suppressed terms removed """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
          xB/(2 - xB)*(self.m.F1(t) + self.m.F2(t))*(CFFH + (xB/2)*CFFE)
              )
        if im:
            return res.imag
        else:
            return res.real
    

    def CCALINTLPA(self, pt, im=0, eff=0):
        """ BM10 ... with 1/Q2 suppressed terms removed """
    
        if eff:
            CFFH = complex(self.m.ReHeff(pt), self.m.ImHeff(pt))
            CFFE = complex(self.m.ReEeff(pt), self.m.ImEeff(pt))
            CFFHt = complex(self.m.ReHteff(pt), self.m.ImHteff(pt))
            CFFEt = complex(self.m.ReEteff(pt), self.m.ImEteff(pt))
        else:
            CFFH = complex(self.m.ReH(pt), self.m.ImH(pt))
            CFFE = complex(self.m.ReE(pt), self.m.ImE(pt))
            CFFHt = complex(self.m.ReHt(pt), self.m.ImHt(pt))
            CFFEt = complex(self.m.ReEt(pt), self.m.ImEt(pt))
        xB, Q2, t, y, eps2  = pt.xB, pt.Q2, pt.t, pt.y, pt.eps2
        res = ( 
         xB/(2 - xB)*(self.m.F1(t) + self.m.F2(t))*(CFFHt + (xB/2)*CFFEt)
              )
        if im:
            return res.imag
        else:
            return res.real
    
