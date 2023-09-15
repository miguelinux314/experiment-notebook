#!/usr/bin/env python3
"""FITS format manipulation tools.
See https://fits.gsfc.nasa.gov/fits_documentation.html.
"""
__author__ = "Òscar Maireles"
__since__ = "2020/04/01"

# pylint: disable=no-self-use

import os
import tempfile

import numpy as np
from astropy.io import fits

import enb
from enb import sets
from enb.config import options


class FITSVersionTable(enb.sets.FileVersionTable, enb.sets.FilePropertiesTable):
    """Read FITS files and convert them to raw files, sorting them by type (
    integer or float) and by bits per pixel.
    """
    fits_extension = "fit"
    allowed_extensions = ["fit", "fits"]
    version_name = "FitsToRaw"

    # No need to set  dataset_files_extension here,
    # because get_default_target_indices is overwriten.
    def __init__(self, original_base_dir, version_base_dir):
        """:param version_base_dir: path to the versioned base directory
          (versioned directories preserve names and structure within
          the base dir)

        :param original_base_dir: path to the original directory
          (it must contain all indices requested later with self.get_df()).
          If None, options.base_datset_dir is used
        """
        super().__init__(
            original_base_dir=original_base_dir,
            version_base_dir=version_base_dir,
            original_properties_table=sets.FilePropertiesTable(),
            version_name=self.version_name,
            check_generated_files=False)

    def get_default_target_indices(self):
        indices = []
        for ext in self.allowed_extensions:
            indices.extend(enb.atable.get_all_input_files(
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
                f".{input_ext}", ".raw"))

    @enb.atable.redefines_column
    def set_version_repetitions(self, file_path, row):
        """Set the number of times the versioning process is performed.
        """
        # pylint: disable=unused-argument
        row[_column_name] = 1

    def version(self, input_path, output_path, row):
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        if not input_path.lower().endswith(".fit") \
                and not input_path.lower().endswith(".fits"):
            raise ValueError(f"Invalid extension found in {input_path}")

        hdul = fits.open(input_path, ignore_missing_simple=True)
        saved_images = 0
        for hdu_index, hdu in enumerate(hdul):
            if hdu.header["NAXIS"] == 0:
                continue
            data = hdu.data.transpose()
            header = hdu.header

            if header['BITPIX'] == 8:
                pass
            else:

                if header['NAXIS'] == 1:
                    if header['BITPIX'] < 0:
                        name_label = f'-f{-header["BITPIX"]}-1x1x{header["NAXIS1"]}'
                        dtype_name = f'float{-header["BITPIX"]}'
                        enb_type_name = f"f{-header['BITPIX']}"
                    elif header['BITPIX'] > 0:
                        name_label = f'-u{header["BITPIX"]}be-1x1x{header["NAXIS1"]}'
                        dtype_name = f'>u{header["BITPIX"] // 8}'
                        enb_type_name = f"u{header['BITPIX']}be"
                    else:
                        raise ValueError(f"Invalid bitpix {header['BITPIX']}")
                    data = np.expand_dims(data, axis=1)
                    data = np.expand_dims(data, axis=2)

                elif header['NAXIS'] == 2:
                    if header['BITPIX'] < 0:
                        name_label = f'-f{-header["BITPIX"]}' \
                                     f'-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        dtype_name = f'float{-header["BITPIX"]}'
                        enb_type_name = f"f{-header['BITPIX']}"
                    elif header['BITPIX'] > 0:
                        name_label = f'-u{header["BITPIX"]}be' \
                                     f'-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        dtype_name = f'>u{header["BITPIX"] // 8}'
                        enb_type_name = f"u{header['BITPIX']}be"
                    else:
                        raise ValueError(f"Invalid bitpix {header['BITPIX']}")

                    data = np.expand_dims(data, axis=2)
                elif header['NAXIS'] == 3:
                    if header['BITPIX'] < 0:
                        name_label = f'-f{-header["BITPIX"]}' \
                                     f'-{header["NAXIS3"]}' \
                                     f'x{header["NAXIS2"]}' \
                                     f'x{header["NAXIS1"]}'
                        dtype_name = f'float{-header["BITPIX"]}'
                        enb_type_name = f"f{-header['BITPIX']}"
                    elif header['BITPIX'] > 0:
                        name_label = f'-u{header["BITPIX"]}be-' \
                                     f'{header["NAXIS3"]}' \
                                     f'x{header["NAXIS2"]}' \
                                     f'x{header["NAXIS1"]}'
                        dtype_name = f'>u{header["BITPIX"] // 8}'
                        enb_type_name = f"u{header['BITPIX']}be"
                    else:
                        raise ValueError(f"Invalid bitpix {header['BITPIX']}")
                elif header['NAXIS'] == 4:
                    if header['BITPIX'] < 0:
                        name_label = f'-f{-header["BITPIX"]}' \
                                     f'-{header["NAXIS3"]}' \
                                     f'x{header["NAXIS2"]}' \
                                     f'x{header["NAXIS1"]}'
                        dtype_name = f'float{-header["BITPIX"]}'
                        enb_type_name = f"f{-header['BITPIX']}"
                    elif header['BITPIX'] > 0:
                        name_label = f'-u{header["BITPIX"]}be' \
                                     f'-{header["NAXIS3"]}' \
                                     f'x{header["NAXIS2"]}' \
                                     f'x{header["NAXIS1"]}'
                        dtype_name = f'>u{header["BITPIX"] // 8}'
                        enb_type_name = f"u{header['BITPIX']}be"
                    else:
                        raise ValueError(f"Invalid bitpix {header['BITPIX']}")
                    data = np.squeeze(data, axis=3)
                else:
                    raise Exception(
                        f"Invalid header['NAXIS'] = {header['NAXIS']}")

                output_dir = os.path.join(
                    os.path.dirname(os.path.abspath(output_path)),
                    enb_type_name)
                effective_output_path = os.path.join(
                    output_dir,
                    f"{os.path.basename(output_path).replace('.raw', '')}"
                    f"_img{saved_images}{name_label}.raw")
                os.makedirs(os.path.dirname(effective_output_path),
                            exist_ok=True)
                if os.path.isfile(effective_output_path):
                    pass
                else:
                    if options.verbose > 2:
                        print(
                            f"Dumping FITS->raw ({repr(effective_output_path)})"
                            f" from hdu_index={hdu_index}")
                    enb.isets.dump_array_bsq(array=data,
                                             file_or_path=effective_output_path,
                                             dtype=dtype_name)
                    fits_header_path = os.path.join(os.path.dirname(
                        os.path.abspath(effective_output_path)).replace(
                        os.path.abspath(self.version_base_dir),
                        f"{os.path.abspath(self.version_base_dir)}_headers"),
                        os.path.basename(effective_output_path).replace(
                            '.raw', '') + "-fits_header.txt")
                    os.makedirs(os.path.dirname(fits_header_path),
                                exist_ok=True)
                    if options.verbose > 2:
                        print(
                            f"Writing to fits_header_path={repr(fits_header_path)}")
                    if os.path.exists(fits_header_path):
                        os.remove(fits_header_path)
                    header.totextfile(fits_header_path)

            saved_images += 1


class FITSWrapperCodec(enb.icompression.WrapperCodec):
    """Raw images are coded into FITS before compression with the wrapper,
    and FITS is decoded to raw after decompression.
    """

    # pylint: disable=abstract-method

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        img = enb.isets.load_array_bsq(
            file_or_path=original_path, image_properties_row=original_file_info)
        with tempfile.NamedTemporaryFile(suffix=".fits") as tmp_file:
            os.remove(tmp_file.name)
            array = img.swapaxes(0, 2)
            hdu = fits.PrimaryHDU(array)
            hdu.writeto(tmp_file.name)

            if os.path.exists(compressed_path):
                os.remove(compressed_path)
            compression_results = super().compress(original_path=tmp_file.name,
                                                   compressed_path=compressed_path,
                                                   original_file_info=original_file_info)
            crs = self.compression_results_from_paths(
                original_path=original_path, compressed_path=compressed_path)
            crs.compression_time_seconds = max(0,
                                              compression_results.compression_time_seconds)
            crs.maximum_memory_kb = compression_results.maximum_memory_kb
            return crs

    def decompress(self, compressed_path, reconstructed_path,
                   original_file_info=None):

        with tempfile.NamedTemporaryFile(suffix=".fits") as tmp_file:
            os.remove(tmp_file.name)
            decompression_results = super().decompress(
                compressed_path=compressed_path,
                reconstructed_path=tmp_file.name)

            hdul = fits.open(tmp_file.name)
            assert len(hdul) == 1
            data = hdul[0].data.transpose()
            header = hdul[0].header

            if header['NAXIS'] == 2:
                if header['BITPIX'] < 0:
                    dtype_name = f'float{-header["BITPIX"]}'
                elif header['BITPIX'] > 0:
                    dtype_name = f'>u{header["BITPIX"] // 8}'
                else:
                    raise ValueError(f"Invalid bitpix {header['BITPIX']}")
            elif header['NAXIS'] == 3:
                if header['BITPIX'] < 0:
                    dtype_name = f'float{-header["BITPIX"]}'
                elif header['BITPIX'] > 0:
                    dtype_name = f'>u{header["BITPIX"] // 8}'
                else:
                    raise ValueError(f"Invalid bitpix {header['BITPIX']}")
            else:
                raise Exception(f"Invalid header['NAXIS'] = {header['NAXIS']}")

            enb.isets.dump_array_bsq(array=data,
                                     file_or_path=reconstructed_path,
                                     dtype=dtype_name)
            decompression_results.compressed_path = compressed_path
            decompression_results.reconstructed_path = reconstructed_path
            return decompression_results
