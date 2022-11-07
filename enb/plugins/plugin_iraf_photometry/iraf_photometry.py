#!/usr/bin/env python3
"""Plugin to extract photometry information from a file using IRAF.
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2022/11/07"

import os
import tempfile
import contextlib
import pandas as pd
import enb
import shutil
import enb.icompression

default_iraf_folder = "/usr/local/bin/cl"
custom_iraf_folder = "/usr/lib/iraf"
iraf_folder = default_iraf_folder

if "iraf" not in os.environ or not os.path.isdir(os.environ["iraf"]):
    if not os.path.isdir(default_iraf_folder):
        if not os.path.isdir(custom_iraf_folder):
            raise RuntimeError(f"Cannot find iraf in either the default ({default_iraf_folder}) "
                               f"nor the custom folders ({custom_iraf_folder}). "
                               f"Please modify custom_iraf_folder in {os.path.abspath(__file__)} "
                               f"to match your installation")
        iraf_folder = custom_iraf_folder
    os.environ["iraf"] = iraf_folder
else:
    iraf_folder = os.environ["iraf"]

from astropy.io import fits
from pyraf import iraf


def raw_to_fits(raw_path, fits_path):
    # Load image indexed by [x,y,z]
    img = enb.isets.load_array_bsq(raw_path)
    # Reindex image to [z,y,x] and save 
    fits.PrimaryHDU(img.swapaxes(0, 2)).writeto(fits_path)


def raw_to_photometry_df(
        raw_path,
        extension=0, fwhm=3.5, sigma=6, threshold=8.0,
        min_value=3_000_000, max_value=50_000_000,
        annulus=10.0, dannulus=10.0, aperture=4.0,
        sigma_phot=0.0):
    """Apply IRAF to the FITS file in `fits_path`.
    :return: a pandas DataFrame with the `x`, `y`, `magnitude` and `magnitude_error` columns of all identified objects.
    """
    with tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir,
                                     suffix=".fits") as fits_file, \
            tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir) as daofind_file, \
            tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir) as phot_file, \
            tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir) as daofind_params_file, \
            tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir) as phot_params_file, \
            tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir) as filtered_phot_file, \
            tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir) as photometry_csv_path:
        for tmp_file in (fits_file, daofind_file, phot_file, daofind_params_file,
                         phot_params_file, filtered_phot_file, photometry_csv_path):
            os.remove(tmp_file.name)

        # Convert raw back to FITS
        fits_path = fits_file.name
        raw_to_fits(raw_path=raw_path, fits_path=fits_path)

        # Find objects in the FITS file
        iraf.noao.digiphot(_doprint=0)
        iraf.noao.digiphot.phot(_doprint=0)
        iraf.noao.digiphot.daophot(_doprint=0)
        iraf.digiphot.ptools(_doprint=0)
        iraf.datapars.datamin = min_value
        iraf.datapars.datamax = max_value
        iraf.findpars.threshold = threshold
        iraf.findpars.nsigma = sigma
        iraf.datapars.fwhmpsf = fwhm
        iraf.datapars.sigma = sigma
        iraf.daofind.setParam('fwhmpsf', fwhm)
        iraf.daofind.setParam('output', daofind_file.name)
        iraf.daofind.setParam('sigma', sigma)
        iraf.daofind.setParam('thresh', threshold)
        iraf.daofind.setParam('verify', "no")
        iraf.daofind.setParam('datamin', min_value)
        iraf.daofind.setParam('datamax', max_value)
        iraf.daofind.saveParList(filename=daofind_params_file.name)
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            iraf.daofind(f"{fits_path}[{extension}]", ParList=daofind_params_file.name)

        # Obtain photometry results
        iraf.fitskypars.salgorithm = "mode"
        iraf.fitskypars.dannulus = dannulus
        iraf.photpars.weighting = "constant"
        iraf.phot.interactive = "no"
        iraf.phot.verify = "no"
        iraf.phot.update = "no"
        iraf.phot.setParam('calgorithm', "none")
        iraf.phot.setParam('salgorithm', "mode")
        iraf.phot.setParam('annulus', annulus)
        iraf.phot.setParam('dannulus', dannulus)
        iraf.phot.setParam('apertures', aperture)
        iraf.phot.setParam('sigma', sigma_phot)
        iraf.phot.setParam('datamin', "INDEF")
        iraf.phot.setParam('datamax', "INDEF")
        iraf.phot.saveParList(filename=phot_params_file.name)
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            iraf.phot(f"{fits_path}[{extension}]",
                      coords=daofind_file.name,
                      output=phot_file.name,
                      ParList=phot_params_file.name)

        # Filter undefined magnitudes and export a well-formatted CSV file
        iraf.txselect(phot_file.name, filtered_phot_file.name, "MAG!=INDEF && MERR < 2.")
        iraf.txdump(filtered_phot_file.name,
                    fields="XC,YC,MAG,MERR", expr="yes", header="no", parameters="yes",
                    Stdout=photometry_csv_path.name)
        with open(photometry_csv_path.name, "r+") as output_file:
            rows = output_file.read().replace("  ", ",")
            output_file.seek(0)
            output_file.write("x,y,magnitude,magnitude_error\n")
            output_file.write(rows)

        df = pd.read_csv(photometry_csv_path.name)

        return df


class PhotometryTable(enb.icompression.LossyCompressionExperiment):
    """Lossy compression experiment that extracts photometry-based distortion metrics.
    """

    # TODO: add photometry-based metrics
    @enb.atable.column_function([
        enb.atable.ColumnProperties("photometry_object_count", label="Photometry object count", plot_min=0)
    ])
    def set_photometry_columns(self, index, row):
        original_raw_path, codec = self.index_to_path_task(index)
        reconstructed_raw_path = self.codec_results.decompression_results.reconstructed_path

        original_photometry_df = raw_to_photometry_df(raw_path=original_raw_path)
        reconstructed_photometry_df = raw_to_photometry_df(raw_path=reconstructed_raw_path)

        row["photometry_object_count"] = len(reconstructed_photometry_df)
