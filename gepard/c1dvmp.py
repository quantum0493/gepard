"""NLO DVMP hard scattering coefficients."""

import math
from typing import Tuple

import gepard as g

S1 = g.special.S1
S2 = g.special.S2
S3 = g.special.S3
SB3 = g.special.SB3


def c1dvmp(m, sgntr: int, j: complex, k: int) -> Tuple[complex, complex, complex]:
    """NLO DVMP hard scattering coefficients."""
    LRGPDF2 = math.log(m.rgpdf2)
    LRDAF2 = math.log(m.rdaf2)
    LRR2 = math.log(m.rr2)
    b0 = g.qcd.beta(0, m.nf)

    ptyk = g.special.parity(k)

    # Spliced from Mathematica:

    #  ... quark part

    MCQ1CF = -7.666666666666667+(0.5*(1.+3.*(1.+j)*(2.+j)))/((1
           + j)**2*(2.+j)**2)+(0.5*(1.+3.*(1.+k)*(2.+k)))/((1.+k)**2
           *(2.+k)**2)+0.5*(-3.-2./((1.+j)*(2.+j))+4.*S1(1.+j))*((-
           0.5*(1.+(1.+j)*(2.+j)))/((1.+j)*(2.+j))-(0.5*(1.+(1.+k)*(
           2.+k)))/((1.+k)*(2.+k))-LRGPDF2+S1(1.+j)+S1(1.+k))+0.5 * \
           ((-0.5*(1.+(1.+j)*(2.+j)))/((1.+j)*(2.+j))-(0.5*(1.+(1.+k
           )*(2.+k)))/((1.+k)*(2.+k))-LRDAF2+S1(1.+j)+S1(1.+k))*(-
           3.-2./((1.+k)*(2.+k))+4.*S1(1.+k))

    MCQ1BET0 = -0.8333333333333334+0.5/((1.+j)*(2.+j))+0.5/((1.
               + k)*(2.+k))+0.5*LRR2-S1(1.+j)-S1(1.+k)

    SUMA = 0j
    SUMB = 0j

    for LI in range(0, k+1):
        SUMANDB = (0.125*(1.+2.*LI)*(S2(0.5*(1.+j))-S2(-0.5+0.5*(
           1.+j))+S2(-0.5+0.5*LI)-S2(0.5*LI)))/((0.5*(1.+j)-0.5*LI)*(2.+j+LI))
        SUMB += SUMANDB
        SUMA += g.special.parity(LI)*SUMANDB

    DELc1aGJK = (-2.*ptyk)/((1.+j)*(2.+j)*(1.+k)*(2.+k))+(0.5
       *(-1.+(1.+j)*(2.+j))*(-2.+(1.+k)*(2.+k)*(S2(0.5*(1.+k)) -
       S2(-0.5+0.5*(1.+k))))*ptyk)/((1.+j)*(2.+j))+(1.+k)*(2.
       +k)*(2.+0.5*(1.+k)*(2.+k))*((0.25*k*(2.+(1.+k)**2)*(S2(
       0.5*(1.+j))-S2(-0.5+0.5*(1.+j))+S2(-0.5+0.5*k)-S2(0.5*k
       )))/((0.5*(1.+j)-0.5*k)*(2.+j+k)*(3.+2.*k)*(4.+(1.+k)*(2.
       +k)))-(0.25*(S2(0.5*(1.+j))-S2(-0.5+0.5*(1.+j))-S2(0.5
       *(1.+k))+S2(-0.5+0.5*(1.+k))))/((0.5*(1.+j)+0.5*(-1.-k))
       *(3.+j+k))+(0.25*(3.+k)*(2.+(2.+k)**2)*(S2(0.5*(1.+j)) -
       S2(-0.5+0.5*(1.+j))-S2(0.5*(2.+k))+S2(-0.5+0.5*(2.+k)))
       )/((0.5*(1.+j)+0.5*(-2.-k))*(4.+j+k)*(3.+2.*k)*(4.+(1.+k)
       *(2.+k))))*ptyk+2.*(j-k)*(3.+j+k)*(-SUMA-g.constants.ZETA3+S3(1.+j
       )+(0.125*(1.+k)*(S2(0.5*(1.+j))-S2(-0.5+0.5*(1.+j))-S2
       (0.5*(1.+k))+S2(-0.5+0.5*(1.+k)))*ptyk)/((0.5*(1.+j)+0.5
       *(-1.-k))*(3.+j+k)))

    DELc1bGKJ = 1/((1.+k)*(2.+k))+0.5*(-2.-(1.+k)**2-((1.+j)*(2
       +j))/((1.+k)*(2.+k)))*(S2(0.5*(1.+j))-S2(-0.5+0.5*(1. +
       j)))-0.5*(1.+k)*(S2(0.5*(1.+k))-S2(-0.5+0.5*(1.+k)))-(0.125
       *(1.+k)*(2.+k)*(4.+(1.+k)*(2.+k))*(S2(0.5*(1.+j)) -
       S2(-0.5+0.5*(1.+j))-S2(0.5*(1.+k))+S2(-0.5+0.5*(1.+k)))) \
       / ((0.5*(1.+j)+0.5*(-1.-k))*(3.+j+k))-(0.5*(1.+k)*(2.+k)*(
          (0.25*k*(2.+(1.+k)**2)*(S2(0.5*(1.+j))-S2(-0.5+0.5*(1. +
       j))+S2(-0.5+0.5*k)-S2(0.5*k)))/((0.5*(1.+j)-0.5*k)*(2. +
       j+k))+(0.25*(3.+k)*(2.+(2.+k)**2)*(S2(0.5*(1.+j))-S2(-0.5
       +0.5*(1.+j))-S2(0.5*(2.+k))+S2(-0.5+0.5*(2.+k))))/((0.5
       *(1.+j)+0.5*(-2.-k))*(4.+j+k))))/(3.+2.*k)+2.*(-j+k)*(3
       +j+k)*(-SUMB-0.5*S1(1.+k)*(S2(0.5*(1.+j))-S2(-0.5+0.5
       *(1.+j)))+SB3(1+j))

    MCQ1CG = 0.9565348003631189+DELc1aGJK-(2.*(1.+(1.+j)*(2.+j)
       )*(1.-sgntr))/((1.+j)**2*(2.+j)**2)-DELc1bGKJ*sgntr+(-(1 /
       ((1.+k)*(2.+k)))+2.*S1(1.+k))*(1.-sgntr+0.5*(1.+j)*(2.+j
       )*sgntr*(-S2(0.5*j)+S2(0.5*(1.+j)))) + (2.*sgntr*ptyk)/(
               (1.+j)*(2.+j)*(1.+k)*(2.+k))-(
               2.*(1.+(1.+k)*(2.+k))*(1.+
       ptyk))/((1.+k)**2*(2.+k)**2)+(-(1/((1.+j)*(2.+j))) +
       2*S1(1.+j))*(1.+ptyk-0.5*(1.+k)*(2.+k)*(-S2(0.5*k) +
       S2(0.5*(1.+k)))*ptyk)+2.*(1.+j)*(2.+j)*((-0.5*(-1.+(1.+j)*(
       2.+j)))/((1.+j)**2*(2.+j)**2)+g.constants.ZETA3-(0.5*sgntr*(-S2(0.5 *
       j)+S2(0.5*(1.+j))))/((1.+j)*(2.+j))-S3(1.+j)-sgntr*SB3(
       1+j))+2.*(1.+k)*(2.+k)*((-0.5*(-1.+(1.+k)*(2.+k)))/((1. +
       k)**2*(2.+k)**2)+g.constants.ZETA3-S3(1.+k)+(0.5*(-S2(0.5*k) +
           S2(0.5*(1.+k)))*ptyk)/((1.+k)*(2.+k))+ptyk*SB3(1+k))

    MCQ1 = g.constants.CF * MCQ1CF + g.constants.CG * MCQ1CG + b0 * MCQ1BET0



    #  ... pure singlet quark part starting at NLO

    MCPS1 = (-2.*(0.5+1/((1.+j)*(2.+j))+1/((1.+k)*(2.+k))))/((1
       +j)*(2.+j))-(2.*(2.+(1.+j)*(2.+j))*(-1.-LRGPDF2+2.*S1(1
       +j)+2.*S1(1.+k)))/(j*(1.+j)*(2.+j)*(3.+j))+(0.5*k*(1.+k
       )*(2.+k)*(3.+k)*((0.25*(S2(0.5*(1.+j))-S2(-0.5+0.5*(1. +
       j))+S2(-0.5+0.5*k)-S2(0.5*k)))/((0.5*(1.+j)-0.5*k)*(2. +
       j+k))-(0.25*(S2(0.5*(1.+j))-S2(-0.5+0.5*(1.+j))-S2(0.5
       *(2.+k))+S2(-0.5+0.5*(2.+k))))/((0.5*(1.+j)+0.5*(-2.-k))
       *(4.+j+k))))/(3.+2.*k)


    #  ... gluon part

    MCG1CF = (-0.5*(2.+(1.+k)*(2.+k)))/((1.+j)*(2.+j)*(1.+k)*(2
       +k))+S1(1.+j)/((1.+j)*(2.+j))-(-1.5-3./((1.+j)*(2.+j)) +
       0.5/((1.+k)*(2.+k))+S1(1.+j))/((1.+k)*(2.+k))-(0.5*(2.+(
       1.+j)*(2.+j))*(-1.5-1/((1.+j)*(2.+j))+2./((1.+k)*(2.+k)) -
       LRGPDF2+3.*S1(1.+j)))/((1.+j)*(2.+j))+0.5*(-0.75-1/((1. +
       j)*(2.+j))-0.5/((1.+k)*(2.+k))-LRDAF2+S1(1.+j)+S1(1.+k)
       )*(-3.-2./((1.+k)*(2.+k))+4.*S1(1.+k))+0.125*(-39.+(2.+(
       1.+k)*(2.+k))*(-S2(0.5*k)+S2(0.5*(1.+k))))+0.25*(1.+k) * \
       (2.+k)*(2.+(1.+k)*(2.+k))*((0.5*(-S2(0.5*j)+S2(0.5*(1. +
       j))))/((1.+k)*(2.+k))-(0.5*((0.25*(-1.+k)*k*(S2(0.5*(1. +
       j))-S2(-0.5+0.5*(1.+j))+S2(-0.5+0.5*k)-S2(0.5*k)))/((0.5
       *(1.+j)-0.5*k)*(2.+j+k))-(0.25*(3.+k)*(4.+k)*(S2(0.5*(
       1.+j))-S2(-0.5+0.5*(1.+j))-S2(0.5*(2.+k))+S2(-0.5+0.5 *
       (2.+k))))/((0.5*(1.+j)+0.5*(-2.-k))*(4.+j+k))))/(3.+2.*k)
       )

    MCG1CA = 1.572467033424113-(4.+10.*(1.+j)*(2.+j))/((1.+j) **
       2*(2.+j)**2)-(3.*(-6.+2.*S1(1.+j)+S1(1.+k)))/(j*(3.+j)) \
       +0.5*(4./((1.+j)*(2.+j))-12./(j*(3.+j))+4.*S1(1.+j))*((0.5
       *(2.+(1.+j)*(2.+j)))/((1.+j)*(2.+j))-LRGPDF2+S1(1.+j) +
       1.5*S1(1.+k))+(-2.+(1.+k)*(2.+k)*S1(1.+k))/((1.+j)*(2. +
       j)*(1.+k)*(2.+k))+0.5*(S2(0.5*j)-S2(0.5*(1.+j)))+0.125 * \
       (2.-(1.+k)*(2.+k)*(-S2(0.5*k)+S2(0.5*(1.+k))))+0.25*k*(
       1.+k)*(2.+k)*(3.+k)*((-0.5*(-S2(0.5*j)+S2(0.5*(1.+j))))
       /((1.+k)*(2.+k))-((0.25*(-1.+k)*(S2(0.5*(1.+j))-S2(-0.5
       +0.5*(1.+j))+S2(-0.5+0.5*k)-S2(0.5*k)))/((0.5*(1.+j)-0.5
       *k)*(2.+j+k))+(0.25*(4.+k)*(S2(0.5*(1.+j))-S2(-0.5+0.5
       *(1.+j))-S2(0.5*(2.+k))+S2(-0.5+0.5*(2.+k))))/((0.5*(1.
       +j)+0.5*(-2.-k))*(4.+j+k)))/(3.+2.*k))

    MCG1BET0 = -0.5*LRGPDF2+0.5*LRR2

    MCG1 = g.constants.CF * MCG1CF + g.constants.CA * MCG1CA + b0 * MCG1BET0

    return (MCQ1, MCPS1, MCG1)
