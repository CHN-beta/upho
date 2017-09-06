#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import h5py
import numpy as np
from scipy.optimize import curve_fit
from upho.analysis.functions import FittingFunctionFactory
from upho.irreps.irreps import extract_degeneracy_from_ir_label

__author__ = 'Yuji Ikeda'


class SFFitter(object):
    def __init__(self, filename='sf.hdf5', name='gaussian'):
        self._name = name

        with h5py.File(filename, 'r') as f:
            self._band_data = f
            self._run()

    def _run(self):
        band_data = self._band_data

        npaths, npoints = band_data['paths'].shape[:2]
        frequencies = band_data['frequencies']
        frequencies = np.array(frequencies)
        self._is_squared = np.array(band_data['is_squared'])

        filename_sf = 'sf_fit.hdf5'
        with h5py.File(filename_sf, 'w') as f:
            self.print_header(f)
            for ipath in range(npaths):
                for ip in range(npoints):
                    print(ipath, ip)
                    group = '{}/{}/'.format(ipath, ip)

                    peak_positions, widths, norms = (
                        self._fit_spectral_functions(
                            frequencies,
                            point_data=band_data[group],
                        )
                    )

                    self._write(f, group, peak_positions, widths, norms)

    def _fit_spectral_functions(self, frequencies, point_data, prec=1e-6):
        partial_sf_s = point_data['partial_sf_s']
        num_irreps = np.array(point_data['num_irreps'])

        function = FittingFunctionFactory(
            name=self._name,
            is_normalized=False).create()

        peak_positions = []
        widths         = []
        norms          = []
        for i in range(num_irreps):
            sf = partial_sf_s[:, i]
            if np.sum(sf) < prec:
                peak_position = np.nan
                width         = np.nan
                norm          = np.nan
            else:
                peak_position = self._create_initial_peak_position(frequencies, sf)
                width         = self._create_initial_width()
                if self._is_squared:
                    norm = self._create_initial_norm(frequencies, sf)
                    p0 = [peak_position, width, norm]
                    maxfev = create_maxfev(p0)
                    fit_params, pcov = curve_fit(
                        function, frequencies, sf, p0=p0, maxfev=maxfev)
                    peak_position = fit_params[0]
                    width         = fit_params[1]
                    norm          = fit_params[2]
                else:
                    ir_label = str(point_data['ir_labels'][i], encoding='ascii')
                    norm = float(extract_degeneracy_from_ir_label(ir_label))

                    def function_normalized(x, p, w):
                        return function(x, p, w, norm)

                    p0 = [peak_position, width]
                    maxfev = create_maxfev(p0)
                    fit_params, pcov = curve_fit(
                        function_normalized, frequencies, sf, p0=p0, maxfev=maxfev)
                    peak_position = fit_params[0]
                    width         = fit_params[1]

            peak_positions.append(peak_position)
            widths        .append(width        )
            norms         .append(norm         )

        peak_positions = np.array(peak_positions)
        widths         = np.array(widths)
        norms          = np.array(norms)

        return peak_positions, widths, norms

    def _create_initial_peak_position(self, frequencies, sf, prec=1e-12):
        position = frequencies[np.argmax(sf)]
        # "curve_fit" does not work well for extremely small initial guess.
        # To avoid this problem, "position" is rounded.
        # See also "http://stackoverflow.com/questions/15624070"
        if abs(position) < prec:
            position = 0.0
        return position

    def _create_initial_width(self):
        width = 0.1
        return width

    def _create_initial_norm(self, frequencies, sf):
        dfreq = frequencies[1] - frequencies[0]
        norm = np.sum(sf) * dfreq
        return norm

    def print_header(self, file_output):
        file_output.create_dataset('function'  , data=self._name)
        file_output.create_dataset('is_squared', data=self._is_squared)
        file_output.create_dataset('paths'     , data=self._band_data['paths'])

    def _write(self, file_out, group, peak_positions_s, widths_s, norms_s):

        keys = [
            'natoms_primitive',
            'elements',
            'distance',
            'pointgroup_symbol',
            'num_irreps',
            'ir_labels',
        ]

        for k in keys:
            file_out.create_dataset(
                group + k, data=np.array(self._band_data[group + k])
            )
        file_out.create_dataset(group + 'peaks_s' , data=peak_positions_s)
        file_out.create_dataset(group + 'widths_s', data=widths_s        )
        file_out.create_dataset(group + 'norms_s' , data=norms_s         )


def create_maxfev(p0):
    maxfev = 20000 * (len(p0) + 1)
    return maxfev