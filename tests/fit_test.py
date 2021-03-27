"""Testing code for MINUIT fitting."""

import os
import sys

from pytest import approx, mark

import gepard as g

os.environ["OPENBLAS_MAIN_FREE"] = "1"

sys.path.append('/home/kkumer/g')
sys.path.append('/home/kkumer/g/gepard')


data = g.utils.loaddata('/home/kkumer/gepard/pype/data/gammastarp2gammap',
                        approach=g.theory.BMK)

DVCSpoints = data[36] + data[37] + data[38] + data[39] + \
  data[40] + data[41] + data[42] + data[43] + data[44] + \
  data[45]


def test_gepardfitDVCSnlso3():
    """Test fitting nl-so3 model to HERA DVCS data.

    This is reduced faster version of old test below.
    """
    fit_gpd = g.model.Fit()
    m = g.model.MellinBarnesModel(gpds=fit_gpd)
    th = g.theory.BMK(model=m)
    th.m.parameters.update({'ns': 0.15203911208796006,
                            'al0s': 1.1575060246398083,
                            'alps': 0.15,
                            'ms': 1.,
                            'secs': 0.,
                            'al0g': 1.247316701070471,
                            'alpg': 0.15,
                            'mg': 0.7})
    # To pre-calculate wce for parallel execution:
    th.chisq_single(data[39])
    f = g.fitter.FitterMinuit(data[39], th)
    f.fix_parameters('ALL')
    f.release_parameters('ms')
    f.minuit.migrad()
    assert f.minuit.fval == approx(19.69615, rel=1.e-2)


@mark.slow
def test_gepardfitDVCSnlso3_long():
    """Test fitting nl-so3 model to HERA DVCS data.

    This should give same results as in gepard's
    'fit dvcs dvcs dvcs' or
    smallx-final.nb, section 1-[nlo]-LO.
    """
    fit_gpd = g.model.Fit()
    m = g.model.MellinBarnesModel(gpds=fit_gpd)
    th = g.theory.BMK(model=m)
    th.m.parameters.update({'ns': 0.15203911208796006,
                            'al0s': 1.1575060246398083,
                            'alps': 0.15,
                            'ms': 1.,
                            'secs': 0.,
                            'al0g': 1.247316701070471,
                            'alpg': 0.15,
                            'mg': 0.7})
    # To pre-calculate wce for parallel execution:
    th.chisq_single(DVCSpoints)
    f = g.fitter.FitterMinuit(DVCSpoints, th)
    f.fix_parameters('ALL')
    f.release_parameters('ms', 'secs', 'secg')
    f.minuit.migrad()
    assert th.chisq(f.fitpoints) == approx(95.92, rel=1.e-2)
    assert th.m.parameters['ms'] == approx(0.47839, rel=1e-2)
    assert th.m.parameters['secs'] == approx(-0.15152, rel=1e-2)
    assert th.m.parameters['secg'] == approx(-0.81216, rel=1e-2)
