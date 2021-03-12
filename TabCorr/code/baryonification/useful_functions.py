import numpy as np
from scipy.interpolate import splrep, splev
from scipy.integrate import quad

def cvir_fct(mvir):
    """
    Concentrations form Dutton+Maccio (2014)
    c200 (200 times RHOC)
    Assumes PLANCK coismology
    """
    A = 1.025
    B = 0.097
    return 10.0**A*(mvir/1.0e12)**(-B)

def DeltaSigmas_from_density_profile(rbin, rho_r, dens):

    """
    Analytically calculated DS profile from density profiles, for both dark matter only (DMO)
    and dark matter + baryons (DMB). Returns delta sigma in rbin for DMB, DMO, and the ratio between the two.
    """

    dbin = rbin
    max_z = 200 #Mpc/h


    Sig_DMO   = []
    Sig_DMB   = []
    avSig_DMO = []
    avSig_DMB = []


    densDMO_tck = splrep(rho_r,dens['DMO'])
    densDMB_tck = splrep(rho_r,dens['DMB'])

    for i in range(len(dbin)):
        itgDMO   = lambda zz: splev((zz**2.0+dbin[i]**2.0)**0.5,densDMO_tck,ext=0)
        Sig_DMO += [2.0*quad(itgDMO,0,max_z,limit=200)[0]]
        itgDMB   = lambda zz: splev((zz**2.0+dbin[i]**2.0)**0.5,densDMB_tck,ext=0)
        Sig_DMB += [2.0*quad(itgDMB,0,max_z,limit=200)[0]]

    Sig_DMO = np.array(Sig_DMO)
    Sig_DMB = np.array(Sig_DMB)


    cumSigDMO_tck = splrep(dbin, Sig_DMO)
    cumSigDMB_tck = splrep(dbin, Sig_DMB)

    for i in range(len(dbin)):
        itgDMO = lambda dd: dd*splev(dd,cumSigDMO_tck,ext=0)
        avSig_DMO += [quad(itgDMO,0,dbin[i])[0]*2.0/dbin[i]**2.0]
        itgDMB = lambda dd: dd*splev(dd,cumSigDMB_tck,ext=0)
        avSig_DMB += [quad(itgDMB,0,dbin[i])[0]*2.0/dbin[i]**2.0]

    avSig_DMO = np.array(avSig_DMO)
    avSig_DMB = np.array(avSig_DMB)


    deltaSigmaDMO = avSig_DMO-Sig_DMO   #(Msun/h) / Mpc^2
    deltaSigmaDMB = avSig_DMB-Sig_DMB

    return deltaSigmaDMB, deltaSigmaDMO, deltaSigmaDMB / deltaSigmaDMO
