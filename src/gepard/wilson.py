"""Wilson coefficients and evolved Wilson coefficients."""

import numpy as np
from scipy.special import loggamma  # type: ignore

from . import adim, c1dvcs, c1dvmp, constants, evolution, qcd, theory


def _fshu(j: np.ndarray) -> np.ndarray:
    """Shuvaev factor."""
    #  = 2^(J+1) Gamma(5/2+J) / Gamma(3/2) / Gamma(3+J) =
    #  = 2^N Gamma(3/2+N) / Gamma(3/2) / Gamma(2+N)
    return (2**(j+1) * np.exp(loggamma(2.5 + j)
                              - loggamma(3 + j) - loggamma(3/2)))


def calc_wc(m: theory.Theory, j: np.ndarray, kk: int, process_class: str):
    """Calculate Wilson coeffs. Added 'kk: int' in the argument

    Args:
        m: instance of the Theory class
        j: MB contour point(s) (overrides m.jpoints)
        process_class: 'DIS', 'DVCS' or 'DVMP'

    Returns:
        wc[k, p, f]: k in range(npts), p in [LO, NLO], f in [Q,G,NSP]

    """
    one = np.ones_like(m.jpoints)
    zero = np.zeros_like(m.jpoints)
    fshu = _fshu(j)
    if process_class in ['DVCS', 'DIS']:
        if process_class == 'DVCS':
            quark_norm = fshu
            gluon_norm = fshu
        else:  # DIS
            quark_norm = one
            gluon_norm = one
        q0, g0, nsp0 = (one, zero, one)   # LO Q, G, NSP
        q1, g1, nsp1 = (zero, zero, zero)  # NLO if only LO is asked for (m.p=0)
        if m.p == 1:
            # don't take NSM part atm:
            q1, g1, nsp1 = c1dvcs.C1(m, j, process_class)[:, :3].transpose()
    elif process_class == 'DVMP':
        # Normalizations. Factor 3 is from normalization of DA, so not NC
        # See p. 37, 39 of "Towards DVMP" paper. Eq. (3.62c)
        quark_norm = 3 * fshu
        gluon_norm = 3 * fshu * 2 / constants.CF / (j + 3)
        # Normalizations are chosen so that LO is normalized to:
        # FIXME: NSP normalizations for DVMP not checked yet
        q0, g0, nsp0 = (one/m.nf, one, one)   # LO Q, G, NSP
        q1, g1, nsp1 = (zero, zero, zero)      # NLO if only LO is asked for (m.p=0)
        if m.p == 1:
            qp1, ps1, g1 = c1dvmp.c1dvmp(m, 1, j, kk)   # 0 replaced with kk
            q1 = qp1/m.nf + ps1
            nsp1 = qp1
    else:
        raise Exception(
                'process_class {} is not DIS, DVCS or DVMP!'.format(process_class))
    c_quark = quark_norm * np.stack([q0, q1])
    c_gluon = gluon_norm * np.stack([g0, g1])
    c_nsp = quark_norm * np.stack([nsp0, nsp1])
    return np.stack((c_quark, c_gluon, c_nsp)).transpose()


def calc_wce(m: theory.Theory, Q2: float, process_class: str, kk: int):
    """Calculate evolved Wilson coeffs for given Q2, for all PWs. Added 'kk: int' in the argument

    Args:
        Q2: final evolution scale
        m: instance of the Theory
        process_class: 'DIS', 'DVCS' or 'DVMP'

    Returns:
        wce[s,k,j]: s in range(npwmax), k in range(npts), j in [Q,G,NSP]

    """
    wce = []
    for pw_shift in [0, 2, 4]:
        j = m.jpoints + pw_shift
        wc = calc_wc(m, j, kk, process_class) # added kk 
        # evolution operators
        evola_si = evolution.evolop(m, j, Q2, process_class)     # 2x2
        evola_ns = evolution.evolopns(m, j, Q2, process_class)   # 1x1, NSP
        zero_right = np.zeros((evola_ns.shape[0], 2, 2, 1))
        zero_down = np.zeros((evola_ns.shape[0], 2, 1, 2))
        evola_ns = evola_ns.reshape((evola_ns.shape[0], 2, 1, 1))
        evola = np.block([[evola_si, zero_right],               # 3x3
                          [zero_down, evola_ns]])
        # p_mat: matrix that combines (LO, NLO) evolution operator and Wilson coeffs
        # while canceling NNLO term NLO*NLO:
        asmur2 = qcd.as2pf(m.p, m.nf, Q2/m.rr2, m.asp[m.p], m.r20)
        asmuf2 = qcd.as2pf(m.p, m.nf, Q2/m.rf2, m.asp[m.p], m.r20)
        # below section implimentation is for LO evolution in DA (E1 evolution)
        if kk==0:
            evol_DA = 1
        elif kk==2:     
            evol_DA =  (asmuf2/m.asp[m.p])**(2*adim.non_singlet_LO(kk+1,m.nf)/(-qcd.beta(m.p,m.nf)))
        else: print('Higher DA moments not incorporated yet ') 

        #print(asmuf2,m.asp[m.p],evol_DA,2*adim.non_singlet_LO(kk+1,m.nf),(-qcd.beta(m.p,m.nf)))
        p_mat = np.array([[1, asmuf2], [asmur2, 0]])
        # 3. evolved Wilson coeff.
        wce.append(np.einsum('kpi,pq,kqij->kj', wc, p_mat, evola)*evol_DA)
    return np.stack(wce, axis=0)  # stack PWs


def calc_j2x(m: theory.Theory, x: float, eta: float, Q2: float):
    """Calculate j2x coeffs, combined with evolution operator.

    Args:
        m: instance of the Theory
        x: long. momentum fraction argument of GPD
        eta: skewness
        Q2: final evolution scale

    Returns:
        wce[s,k,i,j]: s in range(npwmax); k in range(npts); i,j in [Q,G,NSP]

    Todo:
        Implement general (eta != x) j to x transform.

    """
    wce = []
    for pw_shift in [0, 2, 4]:
        j = m.jpoints + pw_shift
        one = np.ones_like(j)
        zero = np.zeros_like(j)
        fshu = _fshu(j)
        if eta < 1e-8:
            # forward limit, PDF-like
            # NSP is set to zero before normalization can be checked
            wc_lo = np.stack((one, x*one, zero)).transpose()
            wc_nlo = np.stack((zero, zero, zero)).transpose()
            wc = np.stack((wc_lo, wc_nlo), axis=1)
            # evolution operators
            # DIS is specified now just so that msbar evolution works properly
            evola_si = evolution.evolop(m, j, Q2, 'DIS')     # 2x2
            evola_ns = evolution.evolopns(m, j, Q2, 'DIS')   # 1x1, NSP
        elif abs(eta-x) < 1e-8:
            # cross-over, border eta=x limit
            wc_lo = np.stack((fshu, fshu*2*x/(3+j), zero)).transpose()
            wc_nlo = np.stack((zero, zero, zero)).transpose()
            wc = np.stack((wc_lo, wc_nlo), axis=1)
            # evolution operators
            # DVCS is specified now just so that msbar evolution works properly
            evola_si = evolution.evolop(m, j, Q2, 'DVCS')     # 2x2
            evola_ns = evolution.evolopns(m, j, Q2, 'DVCS')   # 1x1, NSP
        else:
            raise Exception('eta has to be either 0 or equal to x')
        zero_right = np.zeros((evola_ns.shape[0], 2, 2, 1))
        zero_down = np.zeros((evola_ns.shape[0], 2, 1, 2))
        evola_ns = evola_ns.reshape((evola_ns.shape[0], 2, 1, 1))
        evola = np.block([[evola_si, zero_right],               # 3x3
                          [zero_down, evola_ns]])
        # p_mat: matrix that combines (LO, NLO) evolution operator and Wilson coeffs
        # while canceling NNLO term NLO*NLO:
        # Since wc_NLO = 0, asmur2 is redundant here. I keep it for cleaner code.
        asmur2 = qcd.as2pf(m.p, m.nf, Q2/m.rr2, m.asp[m.p], m.r20)
        asmuf2 = qcd.as2pf(m.p, m.nf, Q2/m.rf2, m.asp[m.p], m.r20)
        p_mat = np.array([[1, asmuf2], [asmur2, 0]])
        # 3. evolved Wilson coeff.
        # Note the difference w.r.t. usual wce, where we have inner product of
        # wc and evola, while here we have element-wise product, so that we
        # are in gpd.py able to get separately quark and gluon GPDs in x-space
        wce.append(np.einsum('kpi,pq,kqij->kij', wc, p_mat, evola))
    return np.stack(wce, axis=0)  # stack PWs
