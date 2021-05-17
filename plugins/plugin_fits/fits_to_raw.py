
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import fitsio
from astropy.io import fits
import os

import enb.isets
import sets
import enb.isets as isets
from enb.config import options


class FitsVersionTable(sets.FileVersionTable, sets.FilePropertiesTable):
    """Read FITS files and convert them to raw files,
    sorting them by type (integer or float)	and by bits per pixel
    """
    fits_extension = "fit"
    allowed_extensions = ["fit", "fits"]
    version_name = "FitsToRaw"

    def __init__(self, original_base_dir, version_base_dir):
        super().__init__(
            original_base_dir=original_base_dir,
            version_base_dir=version_base_dir,
            original_properties_table=sets.FilePropertiesTable(),
            version_name=self.version_name,
            check_generated_files=False)

    def get_default_target_indices(self):
        indices = []
        for ext in self.allowed_extensions:
            indices.extend(sets.get_all_test_files(
                ext=ext, base_dataset_dir=self.original_base_dir))
        return indices

    def original_to_versioned_path(self, original_path):
        if original_path.lower().endswith(".fit"):
            input_ext = "fit"
        elif original_path.lower().endswith(".fits"):
            input_ext = "fits"
        else:
            raise ValueError(f"Invalid input extension {original_path}")

        return os.path.join(
            os.path.dirname(
                os.path.abspath(original_path)).replace(
                os.path.abspath(self.original_base_dir),
                os.path.abspath(self.version_base_dir)),
                os.path.basename(original_path).replace(
                f".{input_ext}", f".raw"))

    @enb.atable.redefines_column
    def set_version_time(self, file_path, row):
        row[_column_name] = 0

    @enb.atable.redefines_column
    def set_version_repetitions(self, file_path, row):
        row[_column_name] = 1

    def version(self, input_path, output_path, row):
        if input_path.lower().endswith(".fit"):
            input_ext = ".fit"
        elif input_path.lower().endswith(".fits"):
            input_ext = ".fits"
        else:
            raise ValueError(f"Invalid extension found in {input_path}")

        hdul = fits.open(input_path)
        saved_images = 0
        for hdu_index, hdu in enumerate(hdul):
            if hdu.header["NAXIS"] == 0:
                continue
            data = hdu.data.transpose()
            header = hdu.header

            if header['NAXIS'] == 2:
                if header['BITPIX'] < 0:
                    name_label = f'-f{-header["BITPIX"]}-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                    dtype_name = f'float{-header["BITPIX"]}'
                    enb_type_name = f"f{-header['BITPIX']}"
                elif header['BITPIX'] > 0:
                    name_label = f'-u{header["BITPIX"]}be-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                    dtype_name = f'<u{header["BITPIX"] // 8}'
                    enb_type_name = f"u{header['BITPIX']}be"
                else:
                    raise ValueError(f"Invalid bitpix {header['BITPIX']}")

                # Make 2D data 3D in an efficient way
                data = np.expand_dims(data, axis=2)
            elif header['NAXIS'] == 3:
                if header['BITPIX'] < 0:
                    name_label = f'-f{-header["BITPIX"]}-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                    dtype_name = f'float{-header["BITPIX"]}'
                    enb_type_name = f"f{-header['BITPIX']}"
                elif header['BITPIX'] > 0:
                    name_label = f'-u{header["BITPIX"]}be-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                    dtype_name = f'<u{header["BITPIX"] // 8}'
                    enb_type_name = f"u{header['BITPIX']}be"
                else:
                    raise ValueError(f"Invalid bitpix {header['BITPIX']}")
            else:
                raise Exception(f"Invalid header['NAXIS'] = {header['NAXIS']}")

            output_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), enb_type_name)
            effective_output_path = os.path.join(
                output_dir,
                f"{os.path.basename(output_path).replace('.raw', '')}_img{saved_images}{name_label}.raw")
            os.makedirs(os.path.dirname(effective_output_path), exist_ok=True)
            if options.verbose > 2:
                print(f"Dumping FITS->raw ({effective_output_path}) from hdu_index={hdu_index}")
            enb.isets.dump_array_bsq(array=data, file_or_path=effective_output_path, dtype=dtype_name)
            fits_header_path = os.path.join(os.path.dirname(os.path.abspath(effective_output_path)).replace(
                os.path.abspath(self.version_base_dir),
                f"{os.path.abspath(self.version_base_dir)}_headers"),
                os.path.basename(effective_output_path).replace('.raw', '') + "-fits_header.txt")
            os.makedirs(os.path.dirname(fits_header_path), exist_ok=True)
            print(f"[watch] fits_header_path={fits_header_path}")
            if os.path.exists(fits_header_path):
                os.remove(fits_header_path)
            header.totextfile(fits_header_path)
            saved_images += 1


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
