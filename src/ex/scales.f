C     ****h* gepard/scales.f
C  FILE DESCRIPTION
C    calculation of dependance on \mu_f and \mu_r of {\cal H} non-singlet
C    DVCS form factor
C    Produces data files for Table 1. of  KMPKS06b paper
C
C    $Id$
C     *******


C     ****p* scales.f/SCALES
C  NAME
C     SCALES  --  Program producing data for Figure scales
C  DESCRIPTION
C    calculation of dependance on \mu_f and \mu_r of {\cal H} non-singlet
C    DVCS form factor
C    Produces data files for Table 1. of  KMPKS06b
C  OUTPUT
C       scales.dat  --  percent variations of H_S
C
C  IDENTIFIERS
C
C  CHILDREN
C      READPAR, INIT, CFFF, DCARG
C  SYNOPSIS

      PROGRAM SCALES

C  SOURCE
C
      IMPLICIT NONE
      INTEGER PT, NPOINTS, LN, NDEL
      DOUBLE PRECISION DCARG, MP, FACF, FACR
      PARAMETER ( NPOINTS = 5 )
      DOUBLE PRECISION XIS(NPOINTS), POINTS(0:1, 5, NPOINTS)
      DOUBLE COMPLEX CFFD, CFFM, CFFU
*     Proton mass:
      PARAMETER (MP = 0.938272d0 )
      INCLUDE '../header.f'

      DATA XIS / 1.0D-5, 1.0D-3, 0.1D0, 0.25D0, 0.5D0 /

      PROCESS = 'DVCS'
      FFTYPE = 'SINGLET'

      CALL READPAR
    

      INCLUDE 'ansatz.f'
      ANSATZ = 'FITBP'
      NQS = 1


*     File that will hold results

      OPEN (UNIT = 10, FILE = "scales.dat", STATUS = "UNKNOWN")

      WRITE (10, *) '# Output of scales.f. See prolog of that program'

*     Scales 

      Q2 = 4.0d0
      DEL2 = -0.25d0
      QS(1) = Q2

*     Looping over two different ansaetze

      DO 20 NDEL = 0, 1
        IF ( NDEL .EQ.  1 ) THEN
!         'HARD'
           PAR(21) = 0.4d0
           PAR(22) = PAR(12) + 0.05d0
        ELSE
!         'SOFT'
          PAR(21) = 0.3d0
          PAR(22) = PAR(12) - 0.2d0
        END IF
        PAR(11) = (2.0d0/3.0d0) - PAR(21)

      DO 10 PT = 1, NPOINTS
        XI = XIS(PT)

*     Looping over five table rows

      DO 10 LN = 1, 5

*     Recognizing parameters for each line

      IF (LN .EQ. 1) THEN
            P = 0
            SCHEME = 'CSBAR'
            FACF = 2.0
            FACR = 1.0
      ELSEIF (LN .EQ. 2) THEN
            P = 1
            SCHEME = 'MSBND'
            FACF = 2.0
            FACR = 1.0
      ELSEIF (LN .EQ. 3) THEN
            P = 1
            SCHEME = 'CSBAR'
            FACF = 2.0
            FACR = 1.0
      ELSEIF (LN .EQ. 4) THEN
            P = 1
            SCHEME = 'MSBND'
            FACF = 1.0
            FACR = 2.0
      ELSE
            P = 1
            SCHEME = 'CSBAR'
            FACF = 1.0
            FACR = 2.0
      END IF


*     Calculating three CFFs needed for present line and point ...

      RR2 = 1.0d0
      RF2 = 1.0d0
      CALL INIT
      CALL EVOLC(1)
      CALL CFFF 
      CFFM = CFF(P)

      RR2 = 1.0d0 / FACR
      RF2 = 1.0d0 / FACF
      CALL INIT
      CALL EVOLC(1)
      CALL CFFF 
      CFFD = CFF(P)

      RR2 = FACR
      RF2 = FACF
      CALL INIT
      CALL EVOLC(1)
      CALL CFFF 
      CFFU = CFF(P)
      
*     ... and saving them to array

      POINTS(NDEL, LN, PT) = ( ABS(CFFD) - ABS(CFFU) ) / 
     &        ABS(CFFM) * 100.0d0

 10   CONTINUE

*     Printing all the results for this table to file

 20   CONTINUE

      DO 30 LN = 1, 5
         WRITE (UNIT=10,FMT=999) ( POINTS(0,LN,PT),
     &  POINTS(1,LN,PT) , PT=1,NPOINTS )
 30   CONTINUE

999   FORMAT (1X, 5(F5.1, ' [', F5.1, ']', 2X))

      STOP
      END
C     ****
