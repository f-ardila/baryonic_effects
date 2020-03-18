-------------------------------------------------------
cmass_deltasigma_0.43_0.7.txt
correlationcoef_matrix_smooth_cut_0.43_0.7.txt
covar_matrix_smooth_cut_0.43_0.7.txt
-------------------------------------------------------

These are the lensing files used in Leauthaud et al. 2017.
http://adsabs.harvard.edu/abs/2017MNRAS.467.3024L

Assumed Cosmology is H0=100, Om=0.31, Ol=0.69

covar_matrix_smooth_cut_0.43_0.7.txt is a file with the elements of the covariance matrix.

The covariance matrix file is a single column of numbers. Let this column be noted c1.

To form the covariance (or correlation matrix), define the matrix C[i,j] and read in the numbers as:

k=0
for i=0,nr-1 do begin
   for j=0,nr-1 do begin
      C[i,j] = c1[k]
      k=k+1
endfor
endfor

Here, nr is the number of radial bins.
nr=13

-------------------------------------------------------
Clustering measurements from Beth Reid
https://arxiv.org/abs/1404.3742
-------------------------------------------------------

Measurements:
wpNSdebiasedboss5003.txt
xi02NSdebiasedboss5003bin2.txt.dummy.reorg

These adopt the same fiducial cosmological model as in Anderson et
al. (2013) with Ωm = 0.274.

icovtotv7corr_b5000000_N200_rebin-bin1fineMU_splits1_1.sys.dummyrow
icovtotv7corr_b5000000_N200_splitswp7_1_19_wp.sys
icovtotv7corr_b5000000_N200_splitswp7_1_19_wp.syswtheory

Inverse covariance martices corresponding to each measurement.
“wp.sys” and wp.syswtheory“ is whether or not it includes covariance matrix from theory part described in the Reid+ paper. 


