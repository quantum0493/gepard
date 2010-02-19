#!/usr/bin/env python

import sys, os
import matplotlib

if os.sys.platform == 'win32':
    from minuit import *
    matplotlib.use('WxAgg')
else: #linux
    try:
        from minuit2 import Minuit2 as Minuit
    except:
        from minuit import *
    matplotlib.use('TkAgg')

from scipy.special import gammainc


import utils 
import models
import Approach
from constants import *
from plots import *
from fits import *

# [1] Load data

data = utils.loaddata()   # dictionary {1 : DataSet instance, ...}

# [2] Choose datapoints for fitting

#fitpoints = data[1] + data[8] + data[29]  # DM's GLO set
#fitpoints = data[1] + data[5] + data[25]  # KK's set
#fitpoints = data[4][:3] + data[8][:3]  # test set
fitpoints = data[1] + data[8] + data[29] + data[30]  # DM's GLO1 set
#fitpoints = data[2] + data[5] + data[25] + data[26] + data[27] + data[28]  # KK's global set
#fitpoints = data[1] + data[2] + data[8] + data[22] + data[29] + data[30] 


# [3] Choose theoretical approach

ff = models.FormFactors()
#bmk = Approach.BMK()
bnoopt = Approach.hotfixedBMK(ff, optimization = False)
bopt = Approach.hotfixedBMK(ff, optimization = True)
b = bopt

# Transform data into conventions of approach used, and 
# pre-calculate what can be pre-calculated

## Prepare just fitpoints ...
# [pt.prepare(b) for pt in fitpoints]
## ... or prepare ALL available datapoints
[[pt.prepare(b) for pt in set] for set in data.values()]

# [4] Define function to be minimized i.e. chi-square

# Simple function with implicit args; no parameter range limits possible
varpars = ['NS', 'alS']
def fcnSimple(*args):
    pars = {varpars[0]: args[0], varpars[1]:args[1]}
    chisq = 0.
    for pt in fitpoints:
        chisq = chisq + (
                (getattr(b, pt.yaxis)(pt, pars) - pt.val)**2 / pt.err**2 )
    return chisq

# Function with all explicit args
def fcn(NS, alS, alpS, MS, rS, bS, Nv, alv, alpv, Mv, rv, bv, C, MC, tNv, tMv, trv, tbv):
   pars = {'NS': NS, 'alS': alS, 'alpS': alpS, 'MS': MS, 'rS': rS, 'bS': bS, 
           'Nv': Nv, 'alv': alv, 'alpv': alpv, 'Mv': Mv, 'rv': rv, 'bv': bv, 
           'C': C, 'MC': MC, 'tNv': tNv, 'tMv': tMv, 'trv': trv, 'tbv': tbv}
   chisq = 0.
   for pt in fitpoints:
       chisq = chisq + (
               (getattr(b, pt.yaxis)(pt, pars) - pt.val)**2 / pt.err**2 )
   return chisq


# [5] Define Minuit object


# Version with fcnSimple

## # Constructing function with variable number of parameters by
## # string manipulation.
## sargs = ", ".join(varpars)
## m = Minuit(eval("lambda %s: fcnSimple(%s)" % (sargs, sargs)))
## 
## # Parameters initialization
## for par in varpars:
##     m.values[par] = ff.H[par]

# Version with fcn


# DMGLO1
m = Minuit(fcn,
  NS = 1.5,         fix_NS = True,
 alS = 1.13,       fix_alS = True,
alpS = 0.15,      fix_alpS = True, 
  MS = 0.707107,   fix_MS = True,     
  rS = 1.0,         fix_rS = True,
  bS = 2.00203,     fix_bS = False,      limit_bS = (1.5, 2.5),
  Nv = 1.35,        fix_Nv = True,
 alv = 0.43,       fix_alv = True,
alpv = 0.85,      fix_alpv = True, 
  Mv = 1.01097,     fix_Mv = False,    limit_Mv = (0.2, 5.),
  rv = 0.496383,      fix_rv = False,    limit_rv = (0.3, 0.7),
  bv = 2.15682,       fix_bv = False,    limit_bv = (1.2, 2.8),
   C = 6.90484,        fix_C = False,    limit_C = (6., 8.),
  MC = 1.33924,   fix_MC = False,    limit_MC = (0., 15.),
 tNv = 0.6,          fix_tNv = True,
 tMv = 2.69667,    fix_tMv = False,    limit_tMv = (4., 9.),
 trv = 5.97923,      fix_trv = False,    limit_trv = (5., 7.),
 tbv = 3.25607,      fix_tbv = False,    limit_tbv = (2., 4.)
)


# DMGLO
## m = Minuit(fcn,
##   NS = 1.5,         fix_NS = True,
##  alS = 1.13,       fix_alS = True,
## alpS = 0.15,      fix_alpS = True, 
##   MS = 0.707107,    fix_MS = True,     
##   rS = 1.0,         fix_rS = True,
##   bS = 2.25,        fix_bS = False,      limit_bS = (3.1, 3.3),
##   Nv = 1.35,        fix_Nv = True,
##  alv = 0.43,       fix_alv = True,
## alpv = 0.85,      fix_alpv = True, 
##   Mv = 0.683,         fix_Mv = False,    limit_Mv = (0.9, 1.1),
##   rv = 0.684,          fix_rv = True,    limit_rv = (0.6, 0.8),
##   bv = 0.5,           fix_bv = True,    limit_bv = (0.4, 0.6),
##    C = 1.12,           fix_C = False,    limit_C = (1.4, 1.5),
##   MC = 1.22,          fix_MC = False,    limit_MC = (1.1, 1.3),
##  tNv = 0.0,          fix_tNv = True,
##  tMv = 2.69667,      fix_tMv = True,    limit_tMv = (4., 9.),
##  trv = 5.97923,      fix_trv = True,    limit_trv = (5., 7.),
##  tbv = 3.25607,      fix_tbv = True,    limit_tbv = (2., 4.)
## )


# [6] Perform minimization

def printres(pars=m.values, nfreepars=utils.npars(m), printsigmas=0):
    """Print out the fitting result (chi-squares)."""

    dof = len(fitpoints) - nfreepars
    sigmas = [(getattr(b, pt.yaxis)(pt, pars) - pt.val) / pt.err for
                pt in fitpoints]
    chi = sum(s*s for s in sigmas)  # equal to m.fval if minuit fit is done
    fitprob = (1.-gammainc(dof/2., chi/2.)) # probability of this chi-sq
    fitres = (chi, dof, fitprob)
    print 'P(chi-square, d.o.f) = P(%1.2f, %2d) = %5.4f' % fitres
    if printsigmas:
        print sigmas
        utils.prettyprint(sigmas)


#m.tol = 20.0
#m.strategy = 2
m.printMode = 0
m.maxcalls = 4000

#m.migrad()
#print "ncalls = ", m.ncalls


# [7] Print results

printres()

pt0 = Data.DummyPoint()
pt0.exptype = 'fixed target'
pt0.in1energy = 160.
pt0.xB = 0.05
pt0.t = -0.2
pt0.Q2 = 2.

ptf = fitpoints[0]
ptf.phi = 0.
