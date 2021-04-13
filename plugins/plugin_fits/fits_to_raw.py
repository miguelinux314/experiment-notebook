  
##!/usr/bin/python
# -*- coding: utf-8 -*-

import numpy as np
import fitsio
import glob
from astropy.io import fits
import os 
import enb.sets as sets
import enb.isets as isets
from enb.config import options


class FitsVersionTable(sets.FileVersionTable, sets.FilePropertiesTable):
    """Read FITS files and convert them to raw files,
    sorting them by type (integer or float)	and by bits per pixel
    """
    fits_extension = "fits"
    version_name = "FitsToRaw"

    def __init__(self, original_base_dir, version_base_dir):
        super().__init__(
            original_base_dir=original_base_dir,
            version_base_dir=version_base_dir,
            original_properties_table=sets.FilePropertiesTable(),
            version_name=self.version_name)

    def get_default_target_indices(self):
        return sets.get_all_test_files(
            ext="fit", base_dataset_dir=self.original_base_dir) \
               + sets.get_all_test_files(
            ext="fits", base_dataset_dir=self.original_base_dir)


    def original_to_versioned_path(self, original_path):

        hdul = fits.open(original_path)
        header = hdul[0].header 
        if header['NAXIS'] == 0 :
            header=hdul[1].header

        if header['NAXIS'] == 2:
            if header['BITPIX'] < 0:
                name_label = f'-f{header["BITPIX"] * -1}-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                type_name = f'float{header["BITPIX"] * -1}'
            if header['BITPIX'] > 0:
                name_label = f'-i{header["BITPIX"]}-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                type_name = f'uint{header["BITPIX"]}'
        elif header['NAXIS'] == 3:
            if header['BITPIX'] < 0:
                name_label = f'-f{header["BITPIX"] * -1}-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                type_name = f'float{header["BITPIX"] * -1}'
            if header['BITPIX'] > 0:
                name_label = f'-i{header["BITPIX"]}-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                type_name = f'uint{header["BITPIX"]}'

        return os.path.join(
            os.path.dirname(
                os.path.abspath(original_path)).replace(
                os.path.abspath(self.original_base_dir),
                os.path.abspath(self.version_base_dir)),
            type_name,
            os.path.basename(original_path).replace(
                f".{self.fits_extension}", f"{name_label}.raw"))

    def version(self, input_path, output_path, row):
        assert input_path.endswith(self.fits_extension), \
            f"Invalid extension in {input_path} (expected {self.fits_extension})"

        hdul = fits.open(input_path)
        header = hdul[0].header 
        if header['NAXIS'] == 0 :
            header=hdul[1].header
        data = fitsio.read(input_path)
        if header['NAXIS'] == 2:
            data = np.expand_dims(data, axis=2)
        elif header['NAXIS'] == 3:
            pass

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        isets.dump_array_bsq(data, output_path)

if __name__ == '__main__':
    print("This example converts all .fit files in fits_data into raw_data, preserving "
          "the directory hierarchy.")

    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./fits_data")
    version_base_dir = options.base_dataset_dir.replace(f"{os.sep}fits_data", f"{os.sep}raw_data")
    fits_table = FitsVersionTable(original_base_dir=options.base_dataset_dir,
                                  version_base_dir=version_base_dir)

    # This line starts the versioning process.
    # Information about the generated data (including transformation time)
    # can be found in df.
    df = fits_table.get_df()
