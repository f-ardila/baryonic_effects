import h5py
import numpy as np
import itertools
from astropy.table import Table, vstack
from halotools.empirical_models import HodModelFactory, model_defaults
from halotools.empirical_models import TrivialPhaseSpace, Zheng07Cens
from halotools.empirical_models import NFWPhaseSpace, Zheng07Sats
from halotools.mock_observables import return_xyz_formatted_array
from halotools.sim_manager import sim_defaults
from halotools.utils import crossmatch
from halotools.utils.table_utils import compute_conditional_percentiles

from halotools.mock_observables.surface_density.surface_density_helpers import annular_area_weighted_midpoints

from scipy.interpolate import splrep, splev
from scipy.integrate import quad

import baryonification as bfc
from baryonification.useful_functions import  *


def print_progress(progress):
    percent = "{0:.1f}".format(100 * progress)
    bar = '=' * int(50 * progress) + '>' + ' ' * int(50 * (1 - progress))
    print('\rProgress: |{0}| {1}%'.format(bar, percent), end='\r')
    if progress == 1.0:
        print()


class TabCorr:

    def __init__(self):
        self.init = False

    @classmethod
    def tabulate(cls, halocat, tpcf, *tpcf_args,
                 mode='auto',
                 Num_ptcl_requirement=sim_defaults.Num_ptcl_requirement,
                 cosmology=sim_defaults.default_cosmology,
                 prim_haloprop_key=model_defaults.prim_haloprop_key,
                 prim_haloprop_bins=100,
                 sec_haloprop_key=model_defaults.sec_haloprop_key,
                 sec_haloprop_percentile_bins=None,
                 sats_per_prim_haloprop=3e-12, downsample=1.0,
                 verbose=False, redshift_space_distortions=True,
                 cens_prof_model=None, sats_prof_model=None, project_xyz=False,
                 **tpcf_kwargs):
        r"""
        Tabulates correlation functions for halos such that galaxy correlation
        functions can be calculated rapidly.

        Parameters
        ----------
        halocat : object
            Either an instance of `halotools.sim_manager.CachedHaloCatalog` or
            `halotools.sim_manager.UserSuppliedHaloCatalog`. This halo catalog
            is used to tabubulate correlation functions.

        tpcf : function
            The halotools correlation function for which values are tabulated.
            Positional arguments should be passed after this function.
            Additional keyword arguments for the correlation function are also
            passed through this function.

        *tpcf_args : tuple, optional
            Positional arguments passed to the ``tpcf`` function.

        mode : string, optional
            String describing whether an auto- ('auto') or a cross-correlation
            ('cross') function is going to be tabulated.

        Num_ptcl_requirement : int, optional
            Requirement on the number of dark matter particles in the halo
            catalog. The column defined by the ``prim_haloprop_key`` string
            will have a cut placed on it: all halos with
            halocat.halo_table[prim_haloprop_key] <
            Num_ptcl_requirement*halocat.particle_mass will be thrown out
            immediately after reading the original halo catalog in memory.
            Default value is set in
            `~halotools.sim_defaults.Num_ptcl_requirement`.

        cosmology : object, optional
            Instance of an astropy `~astropy.cosmology`. Default cosmology is
            set in `~halotools.sim_manager.sim_defaults`. This might be used to
            calculate phase-space distributions and redshift space distortions.

        prim_haloprop_key : string, optional
            String giving the column name of the primary halo property
            governing the occupation statistics of gal_type galaxies. Default
            value is specified in the model_defaults module.

        prim_haloprop_bins : int or list, optional
            Integer determining how many (logarithmic) bins in primary halo
            property will be used. If a list or numpy array is provided, these
            will be used as bins directly.

        sec_haloprop_key : string, optional
            String giving the column name of the secondary halo property
            governing the assembly bias. Must be a key in the table passed to
            the methods of `HeavisideAssembiasComponent`. Default value is
            specified in the `~halotools.empirical_models.model_defaults`
            module.

        sec_haloprop_percentile_bins : int, float, list or None, optional
            If an integer, it determines how many evenly spaced bins in the
            secondary halo property percentiles are going to be used. If a
            float between 0 and 1, it determines the split. Finally, if a list
            or numpy array, it directly describes the bins that are going to be
            used. If None is provided, no binning is applied.

        sats_per_prim_haloprop : float, optional
            Float determing how many satellites sample each halo. For each
            halo, the number is drawn from a Poisson distribution with an
            expectation value of ``sats_per_prim_haloprop`` times the primary
            halo property.

        downsample : float, optional
            Fraction between 0 and 1 used to downsample the total sample used
            to tabulate correlation functions. Values below unity can be used
            to reduce the computation time. It should not result in biases but
            the resulting correlation functions will be less accurate.

        verbose : boolean, optional
            Boolean determing whether the progress should be displayed.

        redshift_space_distortions : boolean, optional
            Boolean determining whether redshift space distortions should be
            applied to halos/galaxies.

        cens_prof_model : object, optional
            Instance of `halotools.empirical_models.MonteCarloGalProf` that
            determines the phase space coordinates of centrals. If none is
            provided, `halotools.empirical_models.TrivialPhaseSpace` will be
            used.

        sats_prof_model : object, optional
            Instance of `halotools.empirical_models.MonteCarloGalProf` that
            determines the phase space coordinates of satellites. If none is
            provided, `halotools.empirical_models.NFWPhaseSpace` will be used.

        project_xyz : bool, optional
            If True, the coordinates will be projected along all three spatial
            axes. By default, only the projection onto the z-axis is used.

        *tpcf_kwargs : dict, optional
                Keyword arguments passed to the ``tpcf`` function.

        Returns
        -------
        halotab : TabCorr
            Object containing all necessary information to calculate
            correlation functions for arbitrary galaxy models.
        """

        if sec_haloprop_percentile_bins is None:
            sec_haloprop_percentile_bins = np.array([0, 1])
        elif isinstance(sec_haloprop_percentile_bins, float):
            sec_haloprop_percentile_bins = np.array(
                [0, sec_haloprop_percentile_bins, 1])

        halotab = cls()

        # First, we tabulate the halo number densities.
        halos = halocat.halo_table
        halos = halos[halos['halo_upid'] == -1]
        halos = halos[halos[prim_haloprop_key] >= Num_ptcl_requirement *
                      halocat.particle_mass]
        halos[sec_haloprop_key + '_percentile'] = (
            compute_conditional_percentiles(
                table=halos, prim_haloprop_key=prim_haloprop_key,
                sec_haloprop_key=sec_haloprop_key))

        halotab.gal_type = Table()

        n_h, log_prim_haloprop_bins, sec_haloprop_percentile_bins = (
            np.histogram2d(
                    np.log10(halos[prim_haloprop_key]),
                    halos[sec_haloprop_key + '_percentile'],
                    bins=[prim_haloprop_bins, sec_haloprop_percentile_bins]))
        halotab.gal_type['n_h'] = n_h.ravel(order='F') / np.prod(halocat.Lbox)

        grid = np.meshgrid(log_prim_haloprop_bins,
                           sec_haloprop_percentile_bins)
        halotab.gal_type['log_prim_haloprop_min'] = grid[0][:-1, :-1].ravel()
        halotab.gal_type['log_prim_haloprop_max'] = grid[0][:-1, 1:].ravel()
        halotab.gal_type['sec_haloprop_percentile_min'] = (
            grid[1][:-1, :-1].ravel())
        halotab.gal_type['sec_haloprop_percentile_max'] = (
            grid[1][1:, :-1].ravel())

        halotab.gal_type = vstack([halotab.gal_type, halotab.gal_type])
        halotab.gal_type['gal_type'] = np.concatenate((
            np.repeat('centrals'.encode('utf8'),
                      len(halotab.gal_type) // 2),
            np.repeat('satellites'.encode('utf8'),
                      len(halotab.gal_type) // 2)))
        halotab.gal_type['prim_haloprop'] = 10**(0.5 * (
            halotab.gal_type['log_prim_haloprop_min'] +
            halotab.gal_type['log_prim_haloprop_max']))
        halotab.gal_type['sec_haloprop_percentile'] = (0.5 * (
            halotab.gal_type['sec_haloprop_percentile_min'] +
            halotab.gal_type['sec_haloprop_percentile_max']))

        # Now, we tabulate the correlation functions.
        cens_occ_model = Zheng07Cens(prim_haloprop_key=prim_haloprop_key)
        if cens_prof_model is None:
            cens_prof_model = TrivialPhaseSpace(redshift=halocat.redshift)
        sats_occ_model = Zheng07Sats(prim_haloprop_key=prim_haloprop_key)
        if sats_prof_model is None:
            sats_prof_model = NFWPhaseSpace(redshift=halocat.redshift)

        model = HodModelFactory(
            centrals_occupation=cens_occ_model,
            centrals_profile=cens_prof_model,
            satellites_occupation=sats_occ_model,
            satellites_profile=sats_prof_model)

        model.param_dict['logMmin'] = 0
        model.param_dict['sigma_logM'] = 0.1
        model.param_dict['alpha'] = 1.0
        model.param_dict['logM0'] = 0
        model.param_dict['logM1'] = - np.log10(sats_per_prim_haloprop)
        model.populate_mock(halocat, Num_ptcl_requirement=Num_ptcl_requirement)
        gals = model.mock.galaxy_table
        gals = gals[np.random.random(len(gals)) < downsample]

        idx_gals, idx_halos = crossmatch(gals['halo_id'], halos['halo_id'])
        assert np.all(gals['halo_id'][idx_gals] == halos['halo_id'][idx_halos])
        gals[sec_haloprop_key + '_percentile'] = np.zeros(len(gals))
        gals[sec_haloprop_key + '_percentile'][idx_gals] = (
            halos[sec_haloprop_key + '_percentile'][idx_halos])

        print("Number of tracer particles: {0}".format(len(gals)))

        for xyz in ['xyz', 'yzx', 'zxy']:
            pos_all = return_xyz_formatted_array(
                x=gals[xyz[0]], y=gals[xyz[1]], z=gals[xyz[2]],
                velocity=gals['v'+xyz[2]] if redshift_space_distortions else 0,
                velocity_distortion_dimension='z', period=halocat.Lbox,
                redshift=halocat.redshift, cosmology=cosmology)

            pos = []
            n_gals = []
            for i in range(len(halotab.gal_type)):

                mask = (
                    (10**(halotab.gal_type['log_prim_haloprop_min'][i]) <
                     gals[prim_haloprop_key]) &
                    (10**(halotab.gal_type['log_prim_haloprop_max'][i]) >=
                     gals[prim_haloprop_key]) &
                    (halotab.gal_type['sec_haloprop_percentile_min'][i] <
                     gals[sec_haloprop_key + '_percentile']) &
                    (halotab.gal_type['sec_haloprop_percentile_max'][i] >=
                     gals[sec_haloprop_key + '_percentile']) &
                    (halotab.gal_type['gal_type'][i] == gals['gal_type']))

                pos.append(pos_all[mask])
                n_gals.append(np.sum(mask))

            n_gals = np.array(n_gals)
            n_done = 0

            if verbose:
                print("Projecting onto {0}-axis...".format(xyz[2]))

            for i in range(len(halotab.gal_type)):

                if mode == 'auto':
                    for k in range(i, len(halotab.gal_type)):
                        if len(pos[i]) * len(pos[k]) > 0:

                            if verbose:
                                n_done += (n_gals[i] * n_gals[k] * (
                                    2 if k != i else 1))
                                print_progress(n_done / np.sum(n_gals)**2)

                            xi = tpcf(
                                pos[i], *tpcf_args,
                                sample2=pos[k] if k != i else None,
                                do_auto=(i == k), do_cross=(not i == k),
                                **tpcf_kwargs)
                            if 'tpcf_matrix' not in locals():
                                tpcf_matrix = np.zeros(
                                    (len(xi.ravel()), len(halotab.gal_type),
                                     len(halotab.gal_type)))
                                tpcf_shape = xi.shape
                            tpcf_matrix[:, i, k] += xi.ravel()
                            tpcf_matrix[:, k, i] += xi.ravel()

                elif mode == 'cross':
                    if len(pos[i]) > 0:

                        if verbose:
                            n_done += n_gals[i]
                            print_progress(n_done / np.sum(n_gals))

                        xi = tpcf(
                            pos[i], *tpcf_args, **tpcf_kwargs)
                        if tpcf.__name__ == 'delta_sigma':
                            xi = xi[1]
                        if 'tpcf_matrix' not in locals():
                            tpcf_matrix = np.zeros(
                                (len(xi.ravel()), len(halotab.gal_type)))
                            tpcf_shape = xi.shape
                        tpcf_matrix[:, i] += xi.ravel()

            if not project_xyz:
                break

        if project_xyz:
            tpcf_matrix /= 3.0

        halotab.attrs = {}
        halotab.attrs['tpcf'] = tpcf.__name__
        halotab.attrs['mode'] = mode
        halotab.attrs['simname'] = halocat.simname
        halotab.attrs['redshift'] = halocat.redshift
        halotab.attrs['Num_ptcl_requirement'] = Num_ptcl_requirement
        halotab.attrs['prim_haloprop_key'] = prim_haloprop_key
        halotab.attrs['sec_haloprop_key'] = sec_haloprop_key

        halotab.tpcf_args = tpcf_args
        halotab.tpcf_kwargs = tpcf_kwargs
        halotab.tpcf_shape = tpcf_shape
        halotab.tpcf_matrix = tpcf_matrix

        halotab.init = True

        return halotab

    @classmethod
    def read(cls, fname):
        r"""
        Reads tabulated correlation functions from the disk.

        Parameters
        ----------
        fname : string
            Name of the file containing the tabulated correlation functions.

        Returns
        -------
        halotab : TabCorr
            Object containing all necessary information to calculate
            correlation functions for arbitrary galaxy models.
        """

        halotab = cls()

        fstream = h5py.File(fname, 'r')
        halotab.attrs = {}
        for key in fstream.attrs.keys():
            halotab.attrs[key] = fstream.attrs[key]

        halotab.tpcf_matrix = fstream['tpcf_matrix'].value
        halotab.tpcf_args = []
        for key in fstream['tpcf_args'].keys():
            halotab.tpcf_args.append(fstream['tpcf_args'][key].value)
        halotab.tpcf_args = tuple(halotab.tpcf_args)
        halotab.tpcf_kwargs = {}
        if 'tpcf_kwargs' in fstream:
            for key in fstream['tpcf_kwargs'].keys():
                halotab.tpcf_kwargs[key] = fstream['tpcf_kwargs'][key].value
        halotab.tpcf_shape = tuple(fstream['tpcf_shape'].value)
        fstream.close()

        halotab.gal_type = Table.read(fname, path='gal_type')

        halotab.init = True

        return halotab

    def write(self, fname, overwrite=False):
        r"""
        Writes tabulated correlation functions to the disk.

        Parameters
        ----------
        fname : string
            Name of the file that is written.

        overwrite : bool, optional
            If True, any existing file will be overwritten.
        """

        fstream = h5py.File(fname, 'w' if overwrite else 'w-')

        keys = ['tpcf', 'mode', 'simname', 'redshift', 'Num_ptcl_requirement',
                'prim_haloprop_key', 'sec_haloprop_key']
        for key in keys:
            fstream.attrs[key] = self.attrs[key]

        fstream['tpcf_matrix'] = self.tpcf_matrix
        for i, arg in enumerate(self.tpcf_args):
            fstream['tpcf_args/arg_%d' % i] = arg
        for key in self.tpcf_kwargs:
            fstream['tpcf_kwargs/' + key] = self.tpcf_kwargs[key]
        fstream['tpcf_shape'] = self.tpcf_shape
        fstream.close()

        self.gal_type.write(fname, path='gal_type', append=True)

    def predict(self, model, separate_gal_type=False):
        r"""
        Predicts the number density and correlation function for a certain
        model.

        Parameters
        ----------
        model : HodModelFactory
            Instance of ``halotools.empirical_models.HodModelFactory``
            describing the model for which predictions are made.

        separate_gal_type : boolean, optional
            If True, the return values are dictionaries divided by each galaxy
            types contribution to the output result.

        Returns
        -------
        ngal : numpy.array or dict
            Array or dictionary of arrays containing the number densities for
            each galaxy type stored in self.gal_type. The total galaxy number
            density is the sum of all elements of this array.

        xi : numpy.array or dict
            Array or dictionary of arrays storing the prediction for the
            correlation function.
        """

        try:
            assert (sorted(model.gal_types) == sorted(
                    ['centrals', 'satellites']))
        except AssertionError:
            raise RuntimeError('The model instance must only have centrals ' +
                               'and satellites as galaxy types. Check the ' +
                               'gal_types attribute of the model instance.')

        try:
            assert (model._input_model_dictionary['centrals_occupation']
                    .prim_haloprop_key == self.attrs['prim_haloprop_key'])
            assert (model._input_model_dictionary['satellites_occupation']
                    .prim_haloprop_key == self.attrs['prim_haloprop_key'])
        except AssertionError:
            raise RuntimeError('Mismatch in the primary halo properties of ' +
                               'the model and the TabCorr instance.')

        try:
            if hasattr(model._input_model_dictionary['centrals_occupation'],
                       'sec_haloprop_key'):
                assert (model._input_model_dictionary['centrals_occupation']
                        .sec_haloprop_key == self.attrs['sec_haloprop_key'])
            if hasattr(model._input_model_dictionary['satellites_occupation'],
                       'sec_haloprop_key'):
                assert (model._input_model_dictionary['satellites_occupation']
                        .sec_haloprop_key == self.attrs['sec_haloprop_key'])
        except AssertionError:
            raise RuntimeError('Mismatch in the secondary halo properties ' +
                               'of the model and the TabCorr instance.')

        try:
            assert np.abs(model.redshift - self.attrs['redshift']) < 0.05
        except AssertionError:
            raise RuntimeError('Mismatch in the redshift of the model and ' +
                               'the TabCorr instance.')

        mean_occupation = np.zeros(len(self.gal_type))

        mask = self.gal_type['gal_type'] == 'centrals'
        mean_occupation[mask] = model.mean_occupation_centrals(
            prim_haloprop=self.gal_type['prim_haloprop'][mask],
            sec_haloprop_percentile=(
                self.gal_type['sec_haloprop_percentile'][mask]))
        mean_occupation[~mask] = model.mean_occupation_satellites(
            prim_haloprop=self.gal_type['prim_haloprop'][~mask],
            sec_haloprop_percentile=(
                self.gal_type['sec_haloprop_percentile'][~mask]))

        ngal = mean_occupation * self.gal_type['n_h'].data

        if self.attrs['mode'] == 'auto':
            xi = self.tpcf_matrix * np.outer(ngal, ngal) / np.sum(ngal)**2
        elif self.attrs['mode'] == 'cross':
            xi = self.tpcf_matrix * ngal / np.sum(ngal)

        if not separate_gal_type:
            ngal = np.sum(ngal)
            if self.attrs['mode'] == 'auto':
                xi = np.sum(xi, axis=(1, 2)).reshape(self.tpcf_shape)
            elif self.attrs['mode'] == 'cross':
                xi = np.sum(xi, axis=1).reshape(self.tpcf_shape)
            return ngal, xi
        else:
            ngal_dict = {}
            xi_dict = {}

            for gal_type in np.unique(self.gal_type['gal_type']):
                mask = self.gal_type['gal_type'] == gal_type
                ngal_dict[gal_type] = np.sum(ngal[mask])

            if self.attrs['mode'] == 'auto':
                grid = np.meshgrid(self.gal_type['gal_type'],
                                   self.gal_type['gal_type'])
                for gal_type_1, gal_type_2 in (
                        itertools.combinations_with_replacement(
                            np.unique(self.gal_type['gal_type']), 2)):
                    mask = (((gal_type_1 == grid[0]) &
                             (gal_type_2 == grid[1])) |
                            ((gal_type_1 == grid[1]) &
                             (gal_type_2 == grid[0])))
                    xi_dict['%s-%s' % (gal_type_1, gal_type_2)] = np.sum(
                        xi * mask, axis=(1, 2)).reshape(self.tpcf_shape)

            elif self.attrs['mode'] == 'cross':
                for gal_type in np.unique(self.gal_type['gal_type']):
                    mask = self.gal_type['gal_type'] == gal_type
                    xi_dict[gal_type] = np.sum(
                        xi * mask, axis=1).reshape(self.tpcf_shape)

            return ngal_dict, xi_dict

    def predict_with_baryons(self, hod_model, baryon_model_params, separate_gal_type=False):
        r"""
        Predicts the number density and correlation function for a certain
        model.

        Parameters
        ----------
        model : HodModelFactory
            Instance of ``halotools.empirical_models.HodModelFactory``
            describing the model for which predictions are made.

        separate_gal_type : boolean, optional
            If True, the return values are dictionaries divided by each galaxy
            types contribution to the output result.

        Returns
        -------
        ngal : numpy.array or dict
            Array or dictionary of arrays containing the number densities for
            each galaxy type stored in self.gal_type. The total galaxy number
            density is the sum of all elements of this array.

        xi : numpy.array or dict
            Array or dictionary of arrays storing the prediction for the
            correlation function.
        """

        try:
            assert (sorted(hod_model.gal_types) == sorted(
                    ['centrals', 'satellites']))
        except AssertionError:
            raise RuntimeError('The model instance must only have centrals ' +
                               'and satellites as galaxy types. Check the ' +
                               'gal_types attribute of the model instance.')

        try:
            assert (hod_model._input_model_dictionary['centrals_occupation']
                    .prim_haloprop_key == self.attrs['prim_haloprop_key'])
            assert (hod_model._input_model_dictionary['satellites_occupation']
                    .prim_haloprop_key == self.attrs['prim_haloprop_key'])
        except AssertionError:
            raise RuntimeError('Mismatch in the primary halo properties of ' +
                               'the model and the TabCorr instance.')

        try:
            if hasattr(hod_model._input_model_dictionary['centrals_occupation'],
                       'sec_haloprop_key'):
                assert (hod_model._input_model_dictionary['centrals_occupation']
                        .sec_haloprop_key == self.attrs['sec_haloprop_key'])
            if hasattr(hod_model._input_model_dictionary['satellites_occupation'],
                       'sec_haloprop_key'):
                assert (hod_model._input_model_dictionary['satellites_occupation']
                        .sec_haloprop_key == self.attrs['sec_haloprop_key'])
        except AssertionError:
            raise RuntimeError('Mismatch in the secondary halo properties ' +
                               'of the model and the TabCorr instance.')

        try:
            assert np.abs(hod_model.redshift - self.attrs['redshift']) < 0.05
        except AssertionError:
            raise RuntimeError('Mismatch in the redshift of the model and ' +
                               'the TabCorr instance.')

        mean_occupation = np.zeros(len(self.gal_type))

        mask = self.gal_type['gal_type'] == 'centrals'
        mean_occupation[mask] = hod_model.mean_occupation_centrals(
            prim_haloprop=self.gal_type['prim_haloprop'][mask],
            sec_haloprop_percentile=(
                self.gal_type['sec_haloprop_percentile'][mask]))
        mean_occupation[~mask] = hod_model.mean_occupation_satellites(
            prim_haloprop=self.gal_type['prim_haloprop'][~mask],
            sec_haloprop_percentile=(
                self.gal_type['sec_haloprop_percentile'][~mask]))

        ngal = mean_occupation * self.gal_type['n_h'].data

        if self.attrs['mode'] == 'auto':
            xi = self.tpcf_matrix * np.outer(ngal, ngal) / np.sum(ngal)**2
        elif self.attrs['mode'] == 'cross':
            xi = self.tpcf_matrix * ngal / np.sum(ngal)

        #################
        #baryonification
        halo_mass = np.array(self.gal_type['prim_haloprop'])
        halo_conc = cvir_fct(halo_mass)

        par = bfc.par()
        par.baryon.eta_tot = 0.32
        par.baryon.eta_cga = 0.6
        par.files.transfct = '/Users/fardila/Documents/GitHub/baryonification/baryonification/files/CDM_PLANCK_tk.dat'

        rbin = annular_area_weighted_midpoints(np.logspace(-1, 1, 20))

        #baryon params
        Mc   = baryon_model_params[0]
        mu   = baryon_model_params[1]
        thej = baryon_model_params[2]
        #2h term
        vc_r, vc_m, vc_bias, vc_corr = bfc.cosmo(par)
        bias_tck = splrep(vc_m, vc_bias, s=0)
        corr_tck = splrep(vc_r, vc_corr, s=0)

        cosmo_bias = splev(halo_mass,bias_tck)
        cosmo_corr = splev(rbin,corr_tck)

        correction_factors = np.array([DeltaSigmas_from_density_profile(rbin,bfc.profiles(rbin,halo_mass[i], halo_conc[i], Mc,mu,thej,cosmo_corr,cosmo_bias[i],par)[1])[2] for i in range(len(halo_mass))])

        #[1] gets density profiles only
        #[2] gets ratios only

        xi = correction_factors.T * xi
        #####################

        if not separate_gal_type:
            ngal = np.sum(ngal)
            if self.attrs['mode'] == 'auto':
                xi = np.sum(xi, axis=(1, 2)).reshape(self.tpcf_shape)
            elif self.attrs['mode'] == 'cross':
                xi = np.sum(xi, axis=1).reshape(self.tpcf_shape)
            return ngal, xi
        else:
            ngal_dict = {}
            xi_dict = {}

            for gal_type in np.unique(self.gal_type['gal_type']):
                mask = self.gal_type['gal_type'] == gal_type
                ngal_dict[gal_type] = np.sum(ngal[mask])

            if self.attrs['mode'] == 'auto':
                grid = np.meshgrid(self.gal_type['gal_type'],
                                   self.gal_type['gal_type'])
                for gal_type_1, gal_type_2 in (
                        itertools.combinations_with_replacement(
                            np.unique(self.gal_type['gal_type']), 2)):
                    mask = (((gal_type_1 == grid[0]) &
                             (gal_type_2 == grid[1])) |
                            ((gal_type_1 == grid[1]) &
                             (gal_type_2 == grid[0])))
                    xi_dict['%s-%s' % (gal_type_1, gal_type_2)] = np.sum(
                        xi * mask, axis=(1, 2)).reshape(self.tpcf_shape)

            elif self.attrs['mode'] == 'cross':
                for gal_type in np.unique(self.gal_type['gal_type']):
                    mask = self.gal_type['gal_type'] == gal_type
                    xi_dict[gal_type] = np.sum(
                        xi * mask, axis=1).reshape(self.tpcf_shape)

            return ngal_dict, xi_dict
