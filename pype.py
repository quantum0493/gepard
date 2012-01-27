#!/usr/bin/env python

#import pylab
#import matplotlib.pyplot as plt

import shelve, copy, sys, logging

import numpy as np
import scipy.stats

logging.basicConfig(level=logging.DEBUG)

import Model, Approach, Fitter, Data, utils, plots
from constants import Mp, Mp2

from results import *
from math import sqrt

from dispersion import *

class HFilter(logging.Filter):

    def __init__(self, treestring):
        self.tree = treestring.split('.')
        logging.Filter.__init__(self)

    def filter(self, rec):
        head = rec.name.split('.')[:len(self.tree)]
        if head != self.tree: 
            return 0
        #sys.stderr.write(' --- HFilter hit by %s (%s)\n' % (rec.name, rec.levelname))
        return 1

_lg = logging.getLogger('p')

hfil = HFilter('p')
logging._handlerList[0].addFilter(hfil)

#lg = logging.Logger('A')
#lg.addHandler(logging.StreamHandler())
#fil = HFilter('A')
#lg.handlers[0].addFilter(hfil)
#lg.addFilter(hfil)
#lg.setLevel(logging.DEBUG)  #DEBUG, INFO, WARNING, ERROR, CRITICAL

## [1] Load experimental data and theoretical models

data = utils.loaddata('/home/kkumer/pype/data/ep2epgamma', approach=Approach.BMK)  
data.update(utils.loaddata('/home/kkumer/pype/data/gammastarp2gammap', approach=Approach.BMK))
data.update(utils.loaddata('/home/kkumer/pype/data/gammastarp2gammap/EIC', approach=Approach.BMK))
data.update(utils.loaddata('/home/kkumer/pype/data/ep2epgamma/EIC', approach=Approach.BMK))
#db = shelve.open('/home/kkumer/pype/theories.db')
#dell = shelve.open('/home/kkumer/pype/dellB.db')

## [2] Choose subset of datapoints for fitting

#testpoints = data[31][12:14] + data[8][1:3] + data[30][2:4]  # test set
#GLOpoints = data[31][12:] + data[8] + data[29]  # DM's GLO set
#GLO1points = data[31][12:] + data[8] + data[29] + data[30]  # DM's GLO1 set
##HERMESpoints = data[31][12:] +  data[29]
##BSApoints = data[8] + data[29]
##HAD17 = utils.select(data[33], criteria=['Q2 == 1.5', 't == -0.17'])
##HA17 = utils.select(data[34], criteria=['t == -0.17'])
##HA28 = utils.select(data[34], criteria=['t == -0.28'])
##HA33 = utils.select(data[34], criteria=['t == -0.33'])
DVCSpoints = data[36] + data[37] + data[38] + data[39] + \
  data[40] + data[41] + data[42] + data[43] + data[44] + \
  data[45]
#ALTGLOpoints = data[5] + data[25] + data[32][18:]  # KK's CLAS BSA
##ALTGLO1points = data[5] + data[25] + data[32] + HAD17 + HA17
##ALTGLO2points = data[5] + data[25] + data[32][18:] + HAD17[::2] + HA17[::2]
##ALTGLO3points = data[5] + data[25] + data[32][18:] + data[30] + HA17
#ALTGLO4points = data[25] + data[32][18:]
#ALTGLO5points = data[5] + data[8] + data[32][18:]   # DM's CLAS BSA
#Hpoints = data[5] + data[32][18:]
##BSDw2Cpoints = utils.select(data[26], criteria=['Q2 == 2.3'])
##BSDw2CDpoints = utils.select(data[50], criteria=['Q2 == 2.3'])
#BSDwpoints = utils.select(data[50], criteria=['FTn == -1'])
#BSSwpoints = utils.select(data[51], criteria=['FTn>=0', 'FTn <= 1'])
#BSDwDMpoints = utils.select(data[55], criteria=['FTn == -1'])
#BSSwDMpoints = utils.select(data[56], criteria=['FTn>=0', 'FTn <= 1'])
#TSA1points = utils.select(data[52], criteria=['FTn == -1'])
#DMpoints = data[5] + data[32][18:] + data[8] + data[30]
#DMTSApoints = data[5] + data[32][18:] + TSA1points + data[8] + data[30]
#TSApoints = TSA1points + data[54]
BTSApoints = utils.select(data[53], criteria=['FTn==0'])
#UNPpoints = ALTGLOpoints + BSSwpoints + BSDwpoints
#UNP5points = ALTGLO5points + BSSwpoints + BSDwpoints
H1ZEUSpoints = DVCSpoints + data[48]
H1ZEUSindependent = data[45] + data[39] + data[36] + data[46]
H1ZEUSindependentNEW = data[45] + data[39] + data[63] + data[46]
EICtest2 = data[1001]
EICX = data[2002]
for n in range(2003,2024):
    EICX = EICX + data[n]
EICTSA = data[2102]
for n in range(2103,2110) + range(2111,2118) + range(2119,2125):
    EICTSA = EICTSA + data[n]
#EICmockkk = data[1002]


## [3] Create a theory

# Gepard only
m = Model.Gepard(ansatz='EFLEXP')
m.parameters.update(DM12)
#m.parameters['KAPS'] = 0
th = Approach.BMK(m)


## [4] Do the fit
#tGepard.model.fix_parameters('ALL')
#mGepard.parameters.update({'NS':0.1520391, 'AL0S':1.1575060, 'AL0G':1.2473167})
#mGepard.parameters.update({'SECG':-0.8, 'SECS':-0.180, 'M02S':0.1498})
#mGepard.parameters.update({'M02S':0.1})
#mGepard.release_parameters('M02S', 'SECS', 'SECG')
#th = tGepard
#f = Fitter.FitterMinuit(EICmockkk+H1ZEUSindependentNEW, th)

#f.minuit.tol = 80
#f.minuit.maxcalls = 100
#f.minuit.printMode = 1


## [5] Some shortcuts ...

def ld(db):
    utils.listdb(db)

def pc(th):
    exps = ['UNP5points', 'ALTGLO5', 'CLAS', 'CLASDM', 'BSDw', 'BSSw', 'TSA1', 'BTSA']
    ptssets = [UNP5points, ALTGLO5points, data[25], data[8], BSDwpoints, BSSwpoints, TSA1points, BTSApoints]
    for name, pts in zip(exps,ptssets):
        print '%10s: chi/npts = %6.2f/%d' % (name, th.chisq(pts)[0], len(pts))
        #cutpts = utils.select(pts, criteria=['Q2>=1.6'])
        #print '%10s: chi/npts = %6.2f/%d (cut)' % (name, th.chisq(cutpts)[0], len(cutpts))

def pcs(th):
    exps = ['BSAs', 'BCAs']
    ptssets = [Hpoints[:6], Hpoints[18:24]]
    for name, pts in zip(exps,ptssets):
        print '%10s: chi/npts = %6.2f/%d' % (name, th.chisq(pts)[0], len(pts))
        #cutpts = utils.select(pts, criteria=['Q2>=1.6'])
        #print '%10s: chi/npts = %6.2f/%d (cut)' % (name, th.chisq(cutpts)[0], len(cutpts))
    
# fixed target datapoint FIXME: WRONG!
def ptfix(th, Q=1, pol=-1, Ee=160., xB=0.1, Q2=2.2, t=-0.1, phi=3.5, FTn=None):
    ptf = Data.DummyPoint()
    ptf.in1energy = Ee
    ptf.s = 2 * Mp * ptf.in1energy + Mp2
    ptf.in1charge = Q
    ptf.in1polarization = pol
    ptf.xB = xB
    ptf.Q2 = Q2
    ptf.t = t
    ptf.xi = ptf.xB/(2.-ptf.xB)
    ptf.phi = phi
    ptf.frame = 'Trento'
    ptf.units = {'phi': 'radian'}
    utils.fill_kinematics(ptf)
    th.to_conventions(ptf)
    th.prepare(ptf)
    return ptf


# collider datapoint
def ptcol(th, Q=-1, pol=0, Ee=20, Ep=250, xB=5.145e-4, Q2=4.4, t=-0.275, 
        phi=np.pi, varphi=-np.pi/2., FTn=None):
#def ptcol(th, Q=-1, pol=0, Ee=20, Ep=250, xB=0.002, Q2=7.3, t=-0.275, 
#        phi=np.pi, varphi=-np.pi/2., FTn=None):
    ptc = Data.DummyPoint()
    ptc.in1energy = Ee
    ptc.in2energy = Ep
    ptc.s = 2 * ptc.in1energy * (ptc.in2energy + sqrt(
                ptc.in2energy**2 - Mp2)) + Mp2
    ptc.in1charge = Q
    ptc.in1polarization = pol
    ptc.in2polarization = 1 # relevant only for XLP and TSA
    ptc.xB = xB
    ptc.Q2 = Q2
    ptc.t = t
    ptc.xi = ptc.xB/(2.-ptc.xB)
    if phi:
        ptc.phi = phi
        ptc.units = {'phi': 'radian'}
    elif FTn:
        ptc.FTn = FTn
    ptc.varphi = varphi
    ptc.frame = 'Trento'
    utils.fill_kinematics(ptc)
    th.to_conventions(ptc)
    th.prepare(ptc)
    return ptc

#ptc = ptcol(th, Q=1, pol=0, Ee=5, Ep=350, phi=3.14/2., xB=1e-2)

def ccals(th, pt):
    cals = ['DVCSunp', 'INTunp', 'INTunpV', 'INTunpA']
    for c in cals:
        print '%8s =  %10.5f + %10.5f * I ' % (c, getattr(th, 'CCAL'+c)(pt), 
                getattr(th, 'CCAL'+c)(pt, im=1))


def _derpt(th, p, pt, f=False, h=0.05):
    """Compute derivative of f w.r.t. model parameter p at point pt.
    
    Simple difference is used (f(p+h/2)-f(p-h/2))/h.
    f is string representing appropriate method of th, or
    observable will be taken as yaxis of pt

    """
    if f:
        fun = th.__getattribute__(f) 
    else:
        fun = th.__getattribute__(pt.yaxis)
    mem = th.m.parameters[p]
    th.m.parameters[p] = mem+h/2.
    up = fun(pt)
    th.m.parameters[p] = mem-h/2.
    down = fun(pt)
    th.m.parameters[p] = mem
    return (up-down)/h


def der(th, pars, pts, f=False,  h=0.05):
    """Compute average derivative at points for each par in pars."""

    for par in pars:
        ders = np.array([_derpt(th, par, pt, f, h) for pt in pts])
        print '%4s  |  %5.2f' % (par, ders.mean())

ptc = ptcol(th)
ptcb = ptcol(th, varphi=0.5-np.pi)
