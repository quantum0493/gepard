"""Gepard --- Python package for analysis of generalized parton distributions."""

from importlib.metadata import version
__version__ = version(__name__)

# Some things are brought to gepard top namespace
# for user's convenience, and easier preservation of
# backward compatibility

from .cff import (CFF, MellinBarnesCFF, DispersionCFF, PionPole,
        DispersionFixedPoleCFF, DispersionFreePoleCFF,
        HybridFixedPoleCFF, HybridFreePoleCFF, GoloskokovKrollCFF)
from .data import DataPoint, DataSet, dset, loaddata, select, list_data, describe_data  # noqa: F401
from .dis import DIS
from .dvcs import DVCS, BM10, BMK, BM10ex, BM10tw2, hotfixedBMK
from .dvmp import DVMP, MellinBarnesTFF
from .eff import ZeroEFF, DipoleEFF, KellyEFF
from .fitter import MinuitFitter
from .gpd import GPD, ConformalSpaceGPD, TestGPD, PWNormGPD
from .kinematics import tmin, tmax, weight_BH, prepare
from .qcd import beta, as2pf
from .theory import Theory
