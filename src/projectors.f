C     ****h* gepard/projectors.f
C  FILE DESCRIPTION
C    projectors to eigenstates of the LO singlet 
C    anomalous dimensions matrix.
C
C    $Id$
C     *******


C     ****s* projectors.f/PROJECTORSF
C  NAME
C     PROJECTORSF  --   projectors P^+ and P^-
C  DESCRIPTION
C    projectors to eigenstates of the LO singlet 
C    anomalous dimensions matrix.
C  SYNOPSIS
C     SUBROUTINE PROJECTORSF (K, PR)
C
C     INTEGER K
C     DOUBLE COMPLEX PR(2,2,2)
C  INPUTS
C           K -- Mellin-Barnes integration point index
C  OUTPUT
C          PR -- Two projector matrices PR(1,a,b)=P^+
C                and PR(2,a,b)=P^-
C  IDENTIFIERS
C        NGAM -- common block with anomalous dimensions of DIS
C  PARENTS
C      RNNLOF
C  CHILDREN
C      LAMBDAF
C  SOURCE
C

      SUBROUTINE PROJECTORSF (K, PR)

      IMPLICIT NONE
      INTEGER K
      DOUBLE COMPLEX PR(2,2,2)
      DOUBLE COMPLEX LAM(2)
      DOUBLE COMPLEX DEN
      INCLUDE 'header.f'


      CALL LAMBDAF (K, LAM)

      DEN = 1.0d0 / (LAM(1) - LAM(2)) 

*     P(+)

      PR(1,1,1) = DEN * (NGAM(K,0,1,1) - LAM(2)) 
      PR(1,1,2) = DEN *  NGAM(K,0,1,2)
      PR(1,2,1) = DEN *  NGAM(K,0,2,1)
      PR(1,2,2) = DEN * (NGAM(K,0,2,2) - LAM(2)) 

*     Using P(-) = 1 - P(+) 

      PR(2,1,1) = 1.0d0 - PR(1,1,1) 
      PR(2,1,2) = - PR(1,1,2) 
      PR(2,2,1) = - PR(1,2,1) 
      PR(2,2,2) = 1.0d0 - PR(1,2,2) 

      RETURN
      END
C     ****
