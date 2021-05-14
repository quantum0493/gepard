"""Classes for representing experimental data.

DummyPoint -- class for points which have just few relevant attributes
DataPoint -- class for points representing experimental measurements
DataSet   -- container for DataPoint instances

"""

import copy
import math
import os
import re
import sys

import gepard as g  # noqa: F401
from gepard.constants import Mp, Mp2


class KinematicsError(Exception):
    """Exception throwsn when kinematics is unphysical."""
    pass


class DummyPoint(dict):
    """This is only used for creating simple DataPoint-like objects.

    Todo:
        DummyPoint has now become more like base class for DataPoint.
        DummyPoint and DataPoint should be merged into one class.

    """

    def __init__(self, init=None):
        """Simple "dummy" data point.

        Args:
            init (dict): initial attributes.

        Examples:
            >>> pt = g.DummyPoint({'xB': 0.1, 't': -0.2, 'Q2': 4.0})

        """
        # Just list allowed attributes to help mypy:
        # -- Kinematics --
        self.xB = None
        self.xi = None
        self.j = None
        self.t = None
        self.Q2 = None
        # -- Process type --
        self.pid = None   # FIXME: this looks superfluous
        # from https://stackoverflow.com/questions/4984647/
        super(DummyPoint, self).__init__()
        self.__dict__ = self
        if init:
            self.update(init)


    def prepare(self, approach):
        """Pre-calculate some kinematics."""
        approach.prepare(self)
        return

    def copy(self):
        """Copy the DataPoint object."""
        # Do we need copy.deepcopy?
        new = copy.copy(self)
        new.__dict__ = new
        return new


class DataPoint(DummyPoint):
    """Experimental measurement point.

    All necessary information about kinematics, is contained in attributes. E.g.

    `xB` -- x_Bjorken
    `Q2` -- squared momentum of virtual photon
    `val` -- measurement value
    `errstat` -- statistical error of `val`
    `errsyst` -- systematic error of `val`
    `errnorm` -- normalization error of `val` (included also in errsyst)
    `err` --  `stat` and `syst` added in quadrature
    `errplus` --  total positive error
    `errplus` --  total negative error

    Information that is common to all data of a given dataset (i.e.
    which is contained in a preamble of datafile is accessible
    via `dataset` attribute:

    `dataset.yaxis` -- name of observable measured
    `dataset.xaxes` -- names of kinematical x-axes of data
    `dataset.collaboration` -- name of experimenatal collaboration
    `dataset.units` -- dictionary with pysical units of variables
    `dataset.newunits` -- dictionary with internal pysical units of variables

    For user's and programmer's convenience, these `dataset` attributes
    are also inherited by `DataPoint` objects, so `point.dataset.yaxis == point.yaxis`
    (Is this type of inheritance, know also as "aquisition", good idea?)
    """

    def __init__(self, gridline, dataset):
        """Take data gridline, construct `DataPoint` object and append it to dataset.

        `gridline` is a list constructed from one row of data grid in data file.
        It is assumed that data gridline is of the form:

              x1  x2 ....   y1  y1stat y1syst

        where y1syst need not be present, or can have one or two values, syst+ and syst-

        (Further elements are ignored.)
        `dataset` is container `DataSet` that is to contain this `DataPoint`
        FIXME: this passing of higher-level DataSet as argument sounds wrong!
        (See comment about aquisition in class docstring.)
        """
        # from https://stackoverflow.com/questions/4984647/
        # we want accessibility via both attributes and dict keys
        super(DataPoint, self).__init__()
        self.__dict__ = self
        self.errtypes = ['err', 'errminus', 'errplus', 'errstat', 'errsyst', 'errnorm']
        # 1. Put reference to container into attribute
        self.dataset = dataset
        # 2. Put data into attributes
        # 2a. first acquire also attributes of parent DataSet
        self.update(dataset.__dict__)
        # 2b. x-axes
        for name in self.xnames:
            nameindex = int(name[1:].split('name')[0])  # = 1, 0, 2, ...
            xname = getattr(self, name)  # = 't', 'xB', ...
            xval = getattr(self, 'x' + str(nameindex) + 'value')  # =  0.1
            if isinstance(xval, float) or isinstance(xval, int): 
                # we have global instead of grid value
                setattr(self, xname, xval)    # pt.xB = 0.1, pt.FTn = 1, ...
            else: 
                # take value from the grid 
                columnindex = int(xval.split('column')[1])-1  # = 1, 0, 2, ...
                setattr(self, xname, gridline[columnindex])  # pt.xB = gridline[1]
        # 2c. y-axis 
        self.val = gridline[int(self.y1value.split('column')[1])-1]
        # 2d. y-axis errors
        if 'y1error' in self:  # we are given total error already
            self.err = gridline[int(self.y1error.split('column')[1])-1]
            self.errplus = self.err
            self.errminus = self.err
        else:
            # we have to add various contributions. We do addition of variances:
            # stat = statsym + max(stat+,stat-)
            # syst_uncorr = systsym + max(syst+,syst-)
            # syst = syst_uncorr + norm
            # err = stat + syst   # This is used for fitting chisq
            # Following two are used for pulls:
            # err+ = statsym + stat+ + systsym + syst+ + norm
            # err- = statsym + stat- + systsym + syst- + norm
            varstat = 0
            varsyst = 0  # uncorrelated syst err
            varsym = 0
            varplus = 0
            varminus = 0
            varnorm = 0
            # 1. statistical error
            if 'y1errorstatistic' in self:
                es = gridline[int(self.y1errorstatistic.split('column')[1])-1]**2
                varstat += es
                varsym  += es
            if 'y1errorstatisticplus' in self:
                ep = gridline[int(self.y1errorstatisticplus.split('column')[1])-1]**2
                em = gridline[int(self.y1errorstatisticminus.split('column')[1])-1]**2
                varstat += max(ep, em)
                varplus  += ep
                varminus += em
            # 2. systematic error
            if 'y1errorsystematic' in self:
                es = gridline[int(self.y1errorsystematic.split('column')[1])-1]**2
                varsyst += es
                varsym  += es
            if 'y1errorsystematicplus' in self:
                ep = gridline[int(self.y1errorsystematicplus.split('column')[1])-1]**2
                em = gridline[int(self.y1errorsystematicminus.split('column')[1])-1]**2
                varsyst += max(ep, em)
                varplus  += ep
                varminus += em
        # 3. normalization error (specified as percentage)
            if 'y1errornormalization' in self:
                varnorm += (self.y1errornormalization * self.val)**2
            # 4. TOTAL errors
            self.errplus = math.sqrt(varsym + varplus + varnorm)
            self.errminus = math.sqrt(varsym + varminus + varnorm)
            self.errstat = math.sqrt(varstat)
            self.errsyst = math.sqrt(varsyst + varnorm)
            self.errnorm = math.sqrt(varnorm)
            # FIXME: One needs to make a choice here and we go conservative
            self.err = math.sqrt(varstat + varsyst + varnorm)
            # alternative:
            # self.err = (self.errplus+self.errminus)/2.
        # 2e. calculate standard kinematical variables
        DataPoint.fill_kinematics(self)
        # 2f. polarizations
        # Unpolarized in1 particle
        if 'in1polarization' not in self:
            self.in1polarization = 0
        # For transversaly polarized target set, if needed and
        # if not already set, by default take dominant sine-varphi harmonic
        if ('in2polarizationvector' in self and self.in2polarizationvector == 'T' and 
                'varFTn' not in self):
            self.varFTn = -1
        return

    def __repr__(self):
        return "DataPoint: " + self.yaxis + " = " + str(self.val)

    @staticmethod
    def _complete_xBWQ2(kin):
        """Make trio {xB, W, Q2} complete if two of them are given in 'kin'."""
        if 'W' in kin and 'Q2' in kin and 'xB' not in kin:
            kin.xB = kin.Q2 / (kin.W**2 + kin.Q2 - Mp2)
        elif 'xB' in kin and 'Q2' in kin and 'W' not in kin:
            kin.W = math.sqrt(kin.Q2 / kin.xB - kin.Q2 + Mp2)
        elif 'xB' in kin and 'W' in kin and 'Q2' not in kin:
            kin.Q2 = kin.xB * (kin.W**2 - Mp2) / (1. - kin.xB)
        else:
            raise KinematicsError('Exactly two of {xB, W, Q2} should be given.')
        return

    @staticmethod
    def _complete_tmt(kin):
        """Make duo {t, tm} complete if one of them is given in 'kin'."""
        if 't' in kin and 'tm' not in kin:
            assert kin.t <= 0
            kin.tm = - kin.t
        elif 'tm' in kin and 't' not in kin:
            assert kin.tm >= 0
            kin.t = - kin.tm
        else:
            raise KinematicsError('Exactly one of {t, tm} should be given.')
        return

    @staticmethod
    def fill_kinematics(kin, old={}):
        """Return complete up-to-date kinematical dictionary.

        Complete set of kinematical variables is {xB, t, Q2, W, s, xi, tm, phi}.
        Using standard identities, missing values are calculated, if possible, first
        solely from values given in 'kin', and then, second, using values in 'old',
        if provided.

        """
        kkeys = set(kin.keys())
        trio = set(['xB', 'W', 'Q2'])
        if len(trio.intersection(kkeys)) == 3:
            raise KinematicsError('Overdetermined set {xB, W, Q2} given.')
        elif len(trio.intersection(kkeys)) == 2:
            DataPoint._complete_xBWQ2(kin)
        elif len(trio.intersection(kkeys)) == 1 and old:
            given = trio.intersection(kkeys).pop()  # one variable given in 'kin'
            # We treat only the case when one of {xB, Q2} is given and second is
            # then taken from 'old'
            if given == 'xB':
                kin.Q2 = old.Q2
            elif given == 'Q2':
                kin.xB = old.xB
            DataPoint._complete_xBWQ2(kin)
        else:
            # We have zero givens, so take all three from 'old'
            if old:
                for key in trio:
                    kin.__setattr__(key, old.__getattribute__(key))
        # FIXME: xi is just fixed by xB - it cannot be given by user
        # There are t/Q2 corrections, cf. BMK Eq. (4), but they are 
        # formally higher twist and it is maybe sensible to DEFINE xi, 
        # the argument of CFF, as follows:
        kin.xi = kin.xB / (2. - kin.xB)
        duo = set(['t', 'tm'])
        if len(duo.intersection(kkeys)) == 2:
            raise KinematicsError('Overdetermined set {t, tm=-t} given.')
        elif len(duo.intersection(kkeys)) == 1:
            DataPoint._complete_tmt(kin)
        else:
            # We have zero givens, so take both from 'old'
            if old:
                for key in duo:
                    kin.__setattr__(key, old.__getattribute__(key))
        # s is just copied from old, if there is one
        if old and 's' in old:
            kin.s = old.s
        # phi and varphi are copied from old, if possible and necessary
        if 'phi' not in kin and 'phi' in old:
            kin.phi = old.phi
        if 'varphi' not in kin and 'varphi' in old:
            kin.varphi = old.varphi
        return kin

    def to_conventions(self):
        """Transform datapoint into gepard's conventions."""
        self.origval = self.val  # to remember it for later convenience
        for errtype in self.errtypes:
            if hasattr(self, errtype):
                setattr(self, 'orig'+errtype, getattr(self, errtype))
        # C1. azimutal angle phi should be in radians.
        if 'phi' in self and hasattr(self, 'units') and self.units['phi'][:3] == 'deg':
            self.phi = self.phi * math.pi / 180.
            self.newunits['phi'] = 'rad'
        # C2. phi_{Trento} -> (pi - phi_{BKM})
        if 'frame' in self and self.frame == 'Trento':
            if 'phi' in self:
                self.phi = math.pi - self.phi
            elif 'FTn' in self:
                if self.FTn == 1 or self.FTn == 3 or self.FTn == -2:
                    self.val = - self.val
        # C3. varphi_{Trento} -> (varphi_{BKM} + pi)
            if 'varphi' in self:
                self.varphi = self.varphi - math.pi
            elif 'varFTn' in self:
                if self.varFTn == 1 or self.varFTn == -1:
                    self.val = - self.val
                else:
                    raise ValueError('varFTn = {} not allowed. Only +/-1!'.format(
                                     self.varFTn))
            self.newframe = 'BMK'
        # C4. cross-sections should be in nb
        if hasattr(self, 'units') and self.units[self.y1name] == 'pb/GeV^4':
            self.val = self.val/1000
            for errtype in self.errtypes:
                if hasattr(self, errtype):
                    err = getattr(self, errtype)
                    setattr(self, errtype, err/1000)
            self.newunits[self.y1name] = 'nb/GeV^4'

#    to_conventions = staticmethod(to_conventions)

    def from_conventions(self):
        """Transform stuff from Approach's conventions into original data's."""
        # C4. cross-sections should be in nb
        if hasattr(self, 'units') and self.units[self.y1name] == 'pb/GeV^4':
            self.val = self.val*1000
            for errtype in self.errtypes:
                if hasattr(self, errtype):
                    err = getattr(self, errtype)
                    setattr(self, errtype, err*1000)
        # C2. phi_{BKM} -> (pi - phi_{Trento})
        if 'frame' in self and self.frame == 'Trento':
            if 'phi' in self:
                self.phi = math.pi - self.phi
            elif 'FTn' in self:
                if self.FTn == 1 or self.FTn == 3:
                    self.val = - self.val
        # C3. varphi_{Trento} -> (varphi_{BKM} + pi)
            if 'varphi' in self:
                self.varphi = self.varphi + math.pi
            elif 'varFTn' in self:
                if self.varFTn == 1 or self.varFTn == -1:
                    self.val = - self.val
            self.newframe = 'Trento'
        # C1. azimutal angle phi back to degrees
        if 'phi' in self and hasattr(self, 'units') and self.units['phi'][:3] == 'deg':
            self.phi = self.phi / math.pi * 180.

#     from_conventions = staticmethod(from_conventions)

#     def orig_conventions(self, val):
#         """Like from_conventions, but for the prediction val."""
#         # This doesn't touches self
#         # C4. cross-sections nb --> pb
#         if hasattr(self, 'units') and self.units[self.y1name] == 'pb/GeV^4':
#             val = val*1000
#         # C2. phi_{BKM} --> (pi - phi_{Trento})
#         if 'frame' in self and self.frame == 'Trento' and 'FTn' in self:
#             if self.FTn == 1 or self.FTn == 3 or self.FTn == -2:
#                 val = - val
#         if 'frame' in self and self.frame == 'Trento' and 'varFTn' in self:
#             if self.varFTn == 1 or self.varFTn == -1:
#                 val = - val
#         return val
#     orig_conventions = staticmethod(orig_conventions)


class DataSet(list):
    """A container for `DataPoint` instances.

    Information that is common to all data of a given dataset (i.e.
    which is contained in a preamble of datafile is accessible
    via attributes:

    `yaxis` -- name of observable measured
    `xaxes` -- names of kinematical x-axes of data
    `collaboration` -- name of experimenatal collaboration
    `units` -- dictionary with pysical units of variables
    `newunits` -- dictionary with internal pysical units of variables

    """
    def __init__(self, datapoints=None, datafile=None):
        """Either take explicit list of DataPoints or get them by parsing datafile."""
        if datapoints:
            list.__init__(self, datapoints)
        else:
            # we have datafile
            list.__init__(self)
            preamble, data = self.parse(datafile)

            # Create needed attributes before creating `DataPoint`s
            # Preamble stuff goes into attributes
            for key in preamble:
                try: # try to convert to number everything that is number
                    setattr(self, key, DataSet._str2num(preamble[key]))
                except ValueError: # rest stays as is
                    setattr(self, key, preamble[key])

            #  Extracting names of x-axes variables 
            #  xnames = ['x1name', 'x2name', ...], not necessarily sorted!
            #  xaxes = ['t', 'xB', ...]
            self.xnames = [key for key in preamble if re.match('^x\dname$', key)]
            self.xaxes = [preamble[key] for key in self.xnames]

            # Good to have:
            self.yaxis = preamble['y1name']
            self.filename = os.path.split(datafile)[-1]
            # Following dictionary will contain units for everything
            # i.e.  {'phi' : 'degrees', 't' : 'GeV^2', ...}
            self.units = dict((preamble[key], preamble[key[:2]+'unit']) for key in self.xnames)
            self.units[self.yaxis] = preamble['y1unit']
            # Following dictionary will have units which are changed so that match
            # units used for internal theoretical formulas
            self.newunits = {}
            # charge of first particle FIXME: just electron treated
            if self.in1particle == 'e+' or self.in1particle == 'ep':    # positron
                self.in1charge = +1
            elif self.in1particle == 'e' or self.in1particle == 'e-' or self.in1particle == 'em':
                self.in1charge = -1
            # Mandelstam s, if specified
            try:
                if self.process in ['ep2epgamma', 'en2engamma']:
                    if self.exptype == 'fixed target':
                        self.s = 2 * Mp * self.in1energy + Mp2
                    elif self.exptype == 'collider':
                        self.s = 2 * self.in1energy * (self.in2energy + math.sqrt(
                            self.in2energy**2 - Mp2)) + Mp2
                    else:
                        pass # FIXME: raise error
            except AttributeError:
                pass
                # _lg.debug('Variable beam energy dataset in {}'.format(datafile))

            for gridline in data:
                self.append(DataPoint(gridline, self))
    
    def __add__(self, rhs):
        """http://stackoverflow.com/questions/8180014/how-to-subclass-python-list-without-type-problems"""
        return DataSet(datapoints=list.__add__(self,rhs))

    def __repr__(self):
        return 'DataSet with {} points'.format(len(self))

    def __getitem__(self, key):
        # From https://stackoverflow.com/questions/2936863/
        if isinstance(key, slice):
            lst = [self[k] for k in range(*key.indices(len(self)))]
            tmp = DataSet(lst)
            tmp.__dict__ = self.__dict__.copy() # transfer the attributes
            return tmp
        elif isinstance(key, int):
            return list.__getitem__(self, key)
        else:
            raise TypeError("Invalid argument type.")

    def __getslice__(self, start, end):
        # This is called by [:], while [::] calls __getitem__()
        if start >= len(self):
            raise IndexError("""%s has only %d items and your slice 
                starts at %d""" % (self, len(self), start))
        return DataSet(self[start:end:None])

    def parse(self, datafile):
        """Parse `datafile` and return tuple (preamble, data).

        `preamble` is dictionary obtained by converting datafile preamble
        items into dictionary items like this:

            y1 = BCA from datafile goes into   {'y1' : 'BCA', ...}

        `data` is actual numerical grid of experimental data converted 
        into list of lists

        """
        # [First] parsing the formatted ASCII file
        desc = {}   # description preamble (reference, kinematics, ...)
        data = []   # actual data grid  x1 x2  ... y1 dy1_stat dy1_syst ...
        dataFile = open(datafile, 'r')
        dataFileLine = dataFile.readline()
        while dataFileLine:
            # remove comments
            dataFileLine = dataFileLine.split('#')[0]
            # only lines with '=' (premble) or with numbers only (data grid) are parsed
            if re.search(r'=', dataFileLine):
                # converting preamble line into dictionary item
                desctpl = tuple([s.strip() for s in dataFileLine.split("=")])
                desc[desctpl[0]] = desctpl[1]
            if re.match(r'([ \t]*[-\.\d]+[ \t\r]+)+', dataFileLine):
                # FIXME: TAB-delimited columns are not handled! Only spaces are OK.
                snumbers = re.findall(r'[-\.\d]+', dataFileLine)
                numbers = []
                for s in snumbers:
                    f = float(s)
                    if (f - int(f)) == 0:  # we have integer
                        numbers.append(int(f))
                    else:
                        numbers.append(f)
                data.append(list(map(float, numbers)))
            dataFileLine = dataFile.readline()

        return desc, data

    @staticmethod
    def _str2num(s):
        """Convert string to number, taking care if it should be int or float.
        
        http://mail.python.org/pipermail/tutor/2003-November/026136.html
        """

        if "." in s:
            return float(s) 
        else:
            return int(s)


    @staticmethod
    def loaddata(datadir='./data'):
        """Return dictionary {id : DataSet, ...}  out of files in datadir."""
        data = {}
        for file in os.listdir(datadir):
            if os.path.splitext(file)[1] == ".dat":
                dataset = DataSet(datafile=os.path.join(datadir, file))
                for pt in dataset:
                    pt.to_conventions()
                data[dataset.id] = dataset
        return data

#    loaddata = staticmethod(loaddata)


# FIXME: This is not a proper approach for package, see
# https://stackoverflow.com/questions/779495/access-data-in-package-subdirectory
this_dir, this_filename = os.path.split(__file__)
dset = DataSet.loaddata(datadir=os.path.join(this_dir, 'data', 'ep2epgamma'))
dset.update(DataSet.loaddata(datadir=os.path.join(this_dir, 'data', 'gammastarp2Mp')))
dset.update(DataSet.loaddata(datadir=os.path.join(this_dir, 'data', 'gammastarp2gammap')))
dset.update(DataSet.loaddata(datadir=os.path.join(this_dir, 'data', 'en2engamma')))
dset.update(DataSet.loaddata(datadir=os.path.join(this_dir, 'data', 'DIS')))
