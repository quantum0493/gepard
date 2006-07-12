C     ****h* gepard/parwav.f
C  FILE DESCRIPTION
C    calculates J-th conformal partial wave for DVCS
C
C    $Id$
C     *******

C     ****s* parwav.f/PARWAVF
C  NAME
C     PARWAVF  --  J-th conformal partial wave for DVCS
C  DESCRIPTION
C    calculates J-th conformal partial wave FPW i.e. 
C    |latex $\vec{C}_j \cdot \vec{H}_j$
C    |html  &nbsp; &nbsp;&nbsp;&nbsp;&nbsp; <b><i>C</i></b><sub>j</sub> <b>. <i>H</i></b><sub>j</sub>
C    (together with evolution), but without prefactors of C, 
C    i.e. C is normalized to (1,0).  
C    These prefactors are added by FREAL, FIMAG and CFF.
C  SYNOPSIS
C     SUBROUTINE PARWAVF (J, XI, DEL2, Q2, Q02, P, SCH, ANSATZ, FPW)
C
C     INTEGER P
C     DOUBLE PRECISION XI, DEL2, Q2, Q02
C     CHARACTER SCH*5, ANSATZ*6
C     DOUBLE COMPLEX J, FPW
C  INPUTS
C           J -- complex conformal moment
C          XI -- DVCS scaling parameter
C        DEL2 -- DVCS asymmetry parameter (P2-P1)^2
C          Q2 -- photon virtuality squared
C         Q02 -- initial scale squared
C           P -- approximation order (0,1,2 is LO, NLO, NNLO)
C         SCH -- scheme
C      ANSATZ -- label for ansatz for GPDs on input scale
C  OUTPUT
C         FPW -- partial wave
C  PARENTS
C      FREAL, FIMAG
C  CHILDREN
C      COMMONF, AS2PF, EVOLF, CDVCSF, MSBARF, HJ
C  SOURCE
C

      SUBROUTINE PARWAVF (K, FPW, PROCESS)

      IMPLICIT NONE
      INTEGER K
      DOUBLE COMPLEX FPW
      CHARACTER PROCESS*4
      INTEGER SPEED, P, NF
      DOUBLE PRECISION AS0, RF2, RR2
      DOUBLE PRECISION XI, DEL2, Q2, Q02
      INTEGER L, NPTSMAX, K1
      DOUBLE PRECISION MU20, R, ASQ2, ASQ02
      DOUBLE COMPLEX BIGC0(2), BIGC1(2), BIGC2(2), CDVCS(0:2,2)
      DOUBLE COMPLEX BIGC(3,2), EVOLA(3,2,2), FCM(2)
      PARAMETER (NPTSMAX = 64)
      DOUBLE COMPLEX J, N(NPTSMAX)
      DOUBLE COMPLEX BIGCDVCS(NPTSMAX,0:2,2), BIGCF2(NPTSMAX,0:2,2)

      PARAMETER (MU20=2.5d0)

      COMMON / PARINT /  SPEED, P, NF
      COMMON / PARFLT /  AS0, RF2, RR2

      COMMON / KINEMATICS /  XI, DEL2, Q2, Q02
      COMMON / NPOINTS    /  N
      COMMON / BIGC       /  BIGCDVCS
      COMMON / BIGCF2     /  BIGCF2

      J = N(K) - 1
      CALL AS2PF (ASQ2, Q2, AS0, MU20, NF, P)
      CALL AS2PF (ASQ02, Q02, AS0, MU20, NF, P)
      R = ASQ2/ASQ02
      CALL EVOLF (K, R, EVOLA)
      CALL HJ(J, FCM)

      DO 5 K1 = 0, P
      DO 5 L = 1, 2
  5   CDVCS(K1, L) = (0.0d0, 0.0d0)

      IF ( PROCESS .EQ. 'DVCS' ) THEN
      DO 7 K1=1,2
      BIGC(1,K1) = BIGCDVCS(K, 0, K1)
      BIGC(2,K1) = BIGCDVCS(K, 1, K1)
  7   BIGC(3,K1) = BIGCDVCS(K, 2, K1)
      ELSE
      DO 9 K1=1,2
      BIGC(1,K1) = BIGCF2(K, 0, K1)
      BIGC(2,K1) = BIGCF2(K, 1, K1)
  9   BIGC(3,K1) = BIGCF2(K, 2, K1)
      END IF

      DO 20 L=0, P
      DO 20 K1=0, L
        CDVCS(L, 1) = CDVCS(L, 1) + BIGC(L-K1+1, 1) * EVOLA(K1+1,1,1) + 
     &      BIGC(L-K1+1,2) * EVOLA(K1+1,2,1)
 20     CDVCS(L, 2) = CDVCS(L, 2) + BIGC(L-K1+1, 1) * EVOLA(K1+1,1,2) + 
     &      BIGC(L-K1+1,2) * EVOLA(K1+1,2,2)

      FPW = (0.0d0, 0.0d0)
      DO 30 K1=0, P
 30   FPW = FPW + ASQ2**K1 * (CDVCS(K1,1)*FCM(1) + CDVCS(K1,2)*FCM(2))

      RETURN
      END
C     *****


C     ****s* parwav.f/HJ
C  NAME
C     HJ  --  conformal moment of input-scale singlet GPD  H_{J}
C  DESCRIPTION
C     returns H_{J} for various ansaetze
C  SYNOPSIS
C     SUBROUTINE HJ(J, XI, DEL2, Q2, ANSATZ, FCM)
C
C     DOUBLE PRECISION XI, DEL2, Q2
C     DOUBLE COMPLEX J, FCM(2) 
C     CHARACTER ANSATZ*6
C  INPUTS
C           J -- conformal moment
C
C    (Following parameters are inputs only for ANSATZ='FIT')
C
C     ALPHA0SEA, ALPHA0G -- intercepts of Regge trajectories for
C                           "sea" quark and gluon GPDs/PDFs
C               NSEA, NG -- normalization factors
C             MSEA2, MG2 -- positions of DEL2 triple poles
C  OUTPUT
C         FCM -- input scale singlet GPD H_{J}
C  PARENTS
C     PARWAVF
C  CHILDREN
C     CLNGAMMA, CBETA, POCHHAMMER
C  SOURCE
C

      SUBROUTINE HJ(J, FCM)

      IMPLICIT NONE
      DOUBLE COMPLEX J, FCM(2) 
      CHARACTER SCHEME*5, ANSATZ*6
      DOUBLE PRECISION XI, DEL2, Q2, Q02
      DOUBLE COMPLEX CLNGAMMA, CBETA, POCHSEA, POCHG, POCHHAMMER
      DOUBLE COMPLEX NUM, DENN
      DOUBLE PRECISION NG, NSEA, MG, MSEA, ALPHA0G, ALPHA0SEA
      DOUBLE PRECISION ALPHAPR

*   Input common-blocks 

      COMMON / PARCHR /  SCHEME, ANSATZ

      COMMON / KINEMATICS /  XI, DEL2, Q2, Q02
      COMMON / GPD        /  NG, NSEA, MG, MSEA, ALPHA0G, ALPHA0SEA

      IF (ANSATZ .EQ. 'TOY') THEN
            FCM(1) = 454760.7514415856 * EXP(CLNGAMMA(0.5d0 + J)) /
     &            EXP(CLNGAMMA(10.6d0 + J))
            FCM(2) = 17.837861981813603 * EXP(CLNGAMMA(-0.1d0 + J)) /
     &            EXP(CLNGAMMA(4.7d0 + J))
      ELSE IF ((ANSATZ .EQ. 'HARD') .OR. (ANSATZ .EQ. 'SOFT')) THEN
            ALPHA0SEA = 1.1d0
            ALPHAPR = 0.25d0
            POCHSEA = (8.0d0, 0.0d0)
            POCHG = (6.0d0, 0.0d0)
            IF (ANSATZ .EQ. 'HARD') THEN
                  NG = 0.4d0
                  ALPHA0G = ALPHA0SEA + 0.1d0
            ELSE IF (ANSATZ .EQ. 'SOFT') THEN
                  NG = 0.3d0
                  ALPHA0G = ALPHA0SEA
            END IF
            NSEA = (2.0d0/3.0d0) - NG
            FCM(1) = NSEA * CBETA(COMPLEX(1.0d0 - ALPHA0SEA - 
     &            ALPHAPR*DEL2, 0.0d0) + J, POCHSEA) / CBETA(
     &            COMPLEX(2.0d0 - ALPHA0SEA, 0.0d0), POCHSEA)
            FCM(2) = NG * CBETA(COMPLEX(1.0d0 - ALPHA0G - ALPHAPR*DEL2,
     &        0.0d0) + J, POCHG) / CBETA(COMPLEX(2.0d0 - ALPHA0G,
     &        0.0d0), POCHG)
!      ELSE IF (ANSATZ .EQ. 'FIT') THEN
!            ALPHAPR = 0.25d0
!            POCHSEA = (8.0d0, 0.0d0)
!            POCHG = (6.0d0, 0.0d0)
!            FCM(1) = NSEA / (1 - DEL2/MSEA**2)**3 * CBETA(
!     &            COMPLEX(1.0d0 - ALPHA0SEA - 
!     &            ALPHAPR*DEL2, 0.0d0) + J, POCHSEA) / CBETA(
!     &            COMPLEX(2.0d0 - ALPHA0SEA, 0.0d0), POCHSEA)
!            FCM(2) = NG / (1 - DEL2/MG**2)**3 * CBETA(
!     &            COMPLEX(1.0d0 - ALPHA0G - ALPHAPR*DEL2,
!     &        0.0d0) + J, POCHG) / CBETA(COMPLEX(2.0d0 - ALPHA0G,
!     &        0.0d0), POCHG)
      ELSE IF (ANSATZ .EQ. 'FIT') THEN
            ALPHAPR = 0.25d0
            FCM(1) = NSEA / (1 - DEL2/MSEA**2)**3 / POCHHAMMER(
     &            COMPLEX(1.0d0 - ALPHA0SEA - 
     &            ALPHAPR*DEL2, 0.0d0) + J, 8) * POCHHAMMER(
     &            COMPLEX(2.0d0 - ALPHA0SEA, 0.0d0), 8)
            FCM(2) = NG / (1 - DEL2/MG**2)**3 / POCHHAMMER(
     &            COMPLEX(1.0d0 - ALPHA0G - ALPHAPR*DEL2,
     &        0.0d0) + J, 6) * POCHHAMMER(COMPLEX(2.0d0 - ALPHA0G,
     &        0.0d0), 6)
      END IF

      RETURN
      END
C     ****

