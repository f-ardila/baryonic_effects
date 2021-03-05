import numpy as np
import baryonification as bfc
import time

time1 = time.time()

Mcs = [2.3e13,6.6e13,1.9e14]
mus = [0.31, 0.21, 0.17]
hydrostatic_mass_biases = [1, 0.833, 0.714] #not sure how to vary hydrostatic mass bias in code
models = ['A', 'B', 'C']

for i in [0,1,2]:

    model = models[i]
    #initialise parameters
    par = bfc.par()

    #input-output files
    data_dir ='/Users/fardila/Documents/Data/baryonic_effects/CMASS/'
    par.files.transfct          = "/Users/fardila/Documents/GitHub/baryonification/baryonification/files/CDM_PLANCK_tk.dat"

    par.files.halofile_in       = data_dir+"halo_catalogs/mdpl2_hlist_0.65650_Mvir11.2.csv"
    # par.files.halofile_in       = data_dir+"halo_catalogs/mdpl2_0.65650_Mvir14.csv"
    # par.files.halofile_in       = data_dir+"halo_catalogs/test.csv"
    par.files.halofile_format = "ROCKSTAR-CSV"

    par.files.partfile_in       = data_dir+"particle_catalogs/mdpl2_particles_0.6565_10m.dat"
    # par.files.partfile_in       = data_dir+"particle_catalogs/test.dat"
    par.files.partfile_format = "ascii"
    par.files.partfile_out      = data_dir+"particle_catalogs/MDPL2_bfc_particles_{0}.out".format(model)



    #MDPL2
    #simulation parameters
    par.sim.Lbox = 1000.
    #cosmological parameters
    par.cosmo.Om = 	0.307115
    par.cosmo.Ob = 0.048206
    par.cosmo.s8 = 0.8228
    par.cosmo.z  = 0.523

    #baryonic parameters
    par.baryon.thej = 4.0

    par.baryon.Mc   = Mcs[i]
    par.baryon.mu   = mus[i]






    #calculate 2-halo term
    bfc.cosmo(par)


    #do displacement
    bfc.displace(par)

    print("Running time: {0} seconds".format(time.time() - time1))
