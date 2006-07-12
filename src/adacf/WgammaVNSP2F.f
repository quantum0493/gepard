*    
       SUBROUTINE WgammaVNSP2F (NF, n, res)
*
       IMPLICIT none
       DOUBLE COMPLEX n, res
       DOUBLE COMPLEX S1, S2, S3, S4
       DOUBLE COMPLEX HS1, HS2, HS3, HS4
       DOUBLE COMPLEX PSI, DPSI
       DOUBLE PRECISION NF, CF, CG, TF
       DOUBLE PRECISION EMC, ZETA2, ZETA3, ZETA4, LOG2
       PARAMETER ( EMC  = 0.57721 56649D0, ZETA2 = 1.64493 40668D0,
     ,            ZETA3 = 1.20205 69032D0, ZETA4 = 1.08232 32337D0,
     ,            LOG2 = 0.69314 71806D0 )
       PARAMETER ( CF=4./3.d0, CG=3.d0, TF=0.5d0 )
*
*      ... Harmonic sum initialization ...
*
      COMMON /HARMONIC/ S1, S2, S3, S4
*
*     ... Function itself spliced in by Mathematica ...
               res=2.5d-1*(-1.2953839999999999d3-3.7925925925925923d1/n
     &  **5+1.777777777777778d2/n**4-5.898d2/n**3+1.258d3/n**2-1
     &  .6410999999999998d3/n+3.135d3/(1.d0+n)-2.436d2/(2.d0+n)+
     &  5.221d2/(3.d0+n)+(7.141000000000001d2*S1)/n+1.174898d3*(
     &  -(1/n)+S1)-NF*(-1.7392699999999999d2+1.4222222222222223d
     &  1/n**4-6.439506172839506d1/n**3+1.5259999999999998d2/n**
     &  2-1.9700000000000002d2/n+8.982d0/(1.d0+n)**4+3.811000000
     &  0000004d2/(1.d0+n)+7.294d1/(2.d0+n)+4.478999999999999d1/
     &  (3.d0+n)+(6.320987654320987d1*S1)/n+1.83187d2*(-(1/n)+S1
     &  )-5.666d1*(S1/n**2+(S2-ZETA2)/n))-5.638999999999999d2*(S
     &  1/n**2+(S2-ZETA2)/n)-(5.136000000000001d2*(-(S1/n**2)-S2
     &  /n-S3+ZETA2/n+ZETA3))/n-(-2.518518518518519d0+1.18518518
     &  51851851d0/n**3-4.345679012345679d0/n**2+5.5308641975308
     &  64d0/n-1.1851851851851851d0/(1.d0+n)**3+4.34567901234567
     &  9d0/(1.d0+n)**2-4.7407407407407405d0/(1.d0+n)+7.90123456
     &  7901234d-1*(-(1/n)+S1)+3.950617283950617d0*(S2-ZETA2)+3.
     &  950617283950617d0*ZETA2-2.3703703703703702d0*(S3-ZETA3)-
     &  2.3703703703703702d0*ZETA3)*(NF*NF))
*
       RETURN
       END
