#!/usr/bin/env python3
"""Slave script to run iraf as a separate process, so that it is automatically cleaned up 
and memory is not hogged.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2022/11/16"

import os
import tempfile
import contextlib
import argparse

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

from pyraf import iraf


def fits_to_csv(
        fits_path, csv_path,
        extension=0, fwhm=3.5, sigma=6, threshold=8.0,
        min_value=3_000_000, max_value=50_000_000,
        annulus=10.0, dannulus=10.0, aperture=4.0,
        sigma_phot=0.0):
    """Apply IRAF to the raw file in `raw_path` and store a CSV file into `csv_path`.
    """
    if os.path.exists(csv_path):
        os.remove(csv_path)

    with tempfile.NamedTemporaryFile() as daofind_file, \
            tempfile.NamedTemporaryFile() as phot_file, \
            tempfile.NamedTemporaryFile() as daofind_params_file, \
            tempfile.NamedTemporaryFile() as phot_params_file, \
            tempfile.NamedTemporaryFile() as filtered_phot_file:
        for tmp_file in (daofind_file, phot_file, daofind_params_file,
                         phot_params_file, filtered_phot_file):
            os.remove(tmp_file.name)

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
        iraf.daofind.setParam('cache', "no")
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
                    Stdout=csv_path)
        with open(csv_path, "r+") as output_file:
            rows = output_file.read().replace("  ", ",")
            output_file.seek(0)
            output_file.truncate(0)
            output_file.write("x,y,magnitude,magnitude_error\n")
            output_file.write(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_fits_path", help="Path to the FITS image to be processed with iraf")
    parser.add_argument("output_csv_path", help="Path to the output CSV file to be generated")
    options = parser.parse_args()
    print(f"Processing {options.input_fits_path} into {options.output_csv_path}...")
    fits_to_csv(options.input_fits_path, options.output_csv_path)
    print(f"Done processing {options.input_fits_path} into {options.output_csv_path}!")
