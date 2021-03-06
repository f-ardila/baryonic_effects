import numpy as np
import baryonification as bfc
import time

time1 = time.time()

#initialise parameters
par = bfc.par()

#input-output files
par.files.transfct          = "/Users/fardila/Documents/GitHub/baryonification/baryonification/files/CDM_PLANCK_tk.dat"
# par.files.halofile_in       = "/Users/fardila/Documents/Data/baryonic_effects/input/halo_catalogs/um_smdpl_insitu_exsitu_0.7124_basic_logmp_11.5.npy"
par.files.halofile_in       = "/Users/fardila/Documents/Data/baryonic_effects/input/halo_catalogs/um_smdpl_insitu_exsitu_0.7124_basic_logmp_11.5_cutMpeak13.npy"
par.files.halofile_format = "ROCKSTAR-NPY"
# par.files.partfile_in       = "/Users/fardila/Documents/Data/baryonic_effects/input/particle_catalogs/um_smdpl_particles_0.7124_50m.npy"
par.files.partfile_in       = "/Users/fardila/Documents/Data/baryonic_effects/input/particle_catalogs/um_smdpl_particles_0.7124_10m.npy"
par.files.partfile_format = "huang_npy"
par.files.partfile_out      = "/Users/fardila/Documents/Data/baryonic_effects/output/particles.out"

#on laptop
# par.files.halofile_in       = "sample_data/um_smdpl_insitu_exsitu_0.7124_basic_logmp_11.5.npy"
# par.files.partfile_in       = "sample_data/um_smdpl_particles_0.7124_50m.npy"
# par.files.partfile_out      = "outfiles/particles.out"

#simulation parameters
par.sim.Lbox = 400

#baryonic parameters
par.baryon.Mc   = 1e14
par.baryon.mu   = 0.2
par.baryon.thej = 4.0

#cosmological parameters
par.cosmo.Om = 0.315
par.cosmo.Ob = 0.049
par.cosmo.s8 = 0.8
par.cosmo.z  = 0


#calculate 2-halo term
bfc.cosmo(par)


#do displacement
bfc.displace(par)

print("Running time: {0} seconds".format(time.time() - time1))

##############################################################################
# timing
# all halos (1,557,939 halos) + 50M particles : 6500s (~2hrs) on single core on Chia
# Mpeak>13 halos (45,594 halos) + 10M particles :  291s (<5min) on single core on Chia
