#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrappers for E. Maglis's M-CALIC implementation
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "30/04/2020"

import os
import sortedcontainers
import tempfile
import numpy as np
import glob
import copy
import subprocess
import shutil
import random

from enb import icompression
from enb.config import get_options
from enb import isets
from enb import tarlite

options = get_options()


class MCALIC_Magli(icompression.LosslessCodec, icompression.NearLosslessCodec, icompression.WrapperCodec):
    FORMAT_BSQ, FORMAT_BIL = range(2)
    default_format = FORMAT_BSQ

    max_tested_spatial_size = 17418240
    max_dimension_size = 2500
    split_height_count = 3
    split_width_count = 3

    def __init__(self, max_error=0, bin_dir=None, data_format=None, output_invocation_dir=None):
        """
        :param max_error: maximum pixelwise error allowed. Use 0 for lossless
          compression
        :param bin_dir: path to the directory that contains the
          ldc_encoder, ldc_decoder and ldc_header_tool binaries. If it is None,
          options.external_bin_base_dir is None. If this is None as well, the
          same directory of this script is used by default.
        :param data_format: bsq/bil format of the expected data.
          If none, the default (BSQ) is used
        """
        bin_dir = bin_dir if bin_dir is not None else options.external_bin_base_dir
        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        assert os.path.isdir(bin_dir), f"Invalid binary dir {bin_dir}."

        param_dict = sortedcontainers.SortedDict()
        max_error = int(max_error)
        assert max_error >= 0, f"Invalid max_error {max_error}"
        param_dict["max_error"] = max_error
        data_format = data_format if data_format is not None else self.default_format
        assert data_format in [self.FORMAT_BSQ, self.FORMAT_BIL], f"Invalid data format {data_format}"
        param_dict["data_format"] = data_format
        icompression.WrapperCodec.__init__(
            self, compressor_path=os.path.join(bin_dir, "Mcalic_enc_nl"),
            decompressor_path=os.path.join(bin_dir, "Mcalic_dec_nl"),
            param_dict=param_dict, output_invocation_dir=output_invocation_dir)

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        # Tested limit: self.max_tested_spatial_size
        if original_file_info["width"] <= self.max_dimension_size \
                and original_file_info["height"] <= self.max_dimension_size:
            return self.compress_one(original_path=original_path,
                                     compressed_path=compressed_path,
                                     original_file_info=original_file_info)
        else:
            tl_writer = tarlite.TarliteWriter()
            img = isets.load_array_bsq(file_or_path=original_path, image_properties_row=original_file_info)
            with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
                compound_size = 0
                total_compression_time = 0
                for y in range(self.split_height_count):
                    for x in range(self.split_width_count):
                        small_array = \
                            img[x * (original_file_info["width"] // self.split_width_count):
                                (((x + 1) * (original_file_info[
                                                 "width"] // self.split_width_count)) if x < self.split_width_count - 1 else
                                 original_file_info["width"]),
                            y * (original_file_info["height"] // self.split_height_count):
                            (((y + 1) * (original_file_info[
                                             "height"] // self.split_height_count)) if y < self.split_height_count - 1 else
                             original_file_info["height"]),
                            :]
                        small_path = os.path.join(tmp_dir, f"{x}_{y}.raw")
                        small_compressed_path = os.path.join(tmp_dir, f"{x}_{y}.mcalic")
                        isets.dump_array_bsq(small_array, small_path)
                        small_file_info = copy.copy(original_file_info)
                        small_file_info["width"], small_file_info["height"], small_file_info[
                            "component_count"] = small_array.shape
                        compression_results = self.compress_one(
                            original_path=small_path, compressed_path=small_compressed_path,
                            original_file_info=small_file_info)
                        total_compression_time += compression_results.compression_time_seconds
                        tl_writer.add_file(small_compressed_path)
                        os.remove(small_path)
                        compound_size += small_array.size

                assert compound_size == original_file_info[
                    "samples"], f"compound_size = {compound_size} != {original_file_info['samples']} = original samples"
                tl_writer.write(output_path=compressed_path)

                compression_results = self.compression_results_from_paths(original_path=original_path,
                                                                          compressed_path=compressed_path)
                compression_results.compression_time_seconds = total_compression_time
                return compression_results

    def compress_one(self, original_path: str, compressed_path: str, original_file_info=None):
        """Compress one image tile with M-CALIC.
        """
        assert original_file_info["bytes_per_sample"] == 2, \
            f"This implementation of M-CALIC ({self.compressor_path}) only supports 16bpp"
        assert original_file_info["component_count"] > 1, \
            f"This implementation of M-CALIC ({self.compressor_path}) only supports images with more than one component"


        with tempfile.NamedTemporaryFile(
                dir=options.base_tmp_dir, prefix=f"bil_le_{os.path.basename(original_path)}") as bil_le_file:
            # M-Calic implementation requires little endian, unsigned 16bpp BIL format
            original_dtype = isets.iproperties_row_to_numpy_dtype(image_properties_row=original_file_info)
            img = np.fromfile(original_path, dtype=original_dtype).reshape(
                original_file_info["component_count"], original_file_info["height"], original_file_info["width"])
            

            offset = None
            if original_file_info["signed"]:
                offset, original_max = int(img.min()), int(img.max())
                offset = min(offset, 0)
                assert original_max - offset <= 2 ** 15 - 1, \
                    f"Invalid dynamic range of signed image ({offset}, {original_max})"
                img = (img.astype("i4") - offset).astype(original_dtype.replace("i", "u"))

            if original_file_info["big_endian"]:
                img = img.astype(original_dtype.replace(">", "<").replace("i", "u"))
            img.swapaxes(0, 1).tofile(bil_le_file.name)

            if original_file_info["signed"]:
                with tempfile.NamedTemporaryFile(dir=options.base_tmp_dir,
                                                 prefix=f"bil_le_{os.path.basename(original_path)}",
                                                 suffix=".mcalic") as tmp_compressed_file, \
                        tempfile.NamedTemporaryFile(dir=options.base_tmp_dir,
                                                    prefix=f"side_info_{os.path.basename(original_path)}",
                                                    suffix=".txt", mode="w") as si_file:
                    si_file.write(f"{abs(offset):d}")
                    si_file.flush()
                    compression_results = super().compress(original_path=bil_le_file.name,
                                                           compressed_path=tmp_compressed_file.name,
                                                           original_file_info=original_file_info)
                    tarlite.TarliteWriter(initial_input_paths=[si_file.name, tmp_compressed_file.name]).write(
                        compressed_path)
                    compression_results.original_path = original_path
                    compression_results.compressed_path = compressed_path
                    return compression_results
            else:
                compression_results = super().compress(
                    original_path=bil_le_file.name, compressed_path=compressed_path,
                    original_file_info=original_file_info)
                compression_results.original_path = original_path
                return compression_results

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        s = f"{original_path} {compressed_path} " \
            f"{original_file_info['component_count']} {original_file_info['height']} {original_file_info['width']} " \
            f"{8 * original_file_info['bytes_per_sample']} {self.param_dict['max_error']} {self.param_dict['data_format']}"
        return s

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        if original_file_info["width"] <= self.max_dimension_size and original_file_info[
            "height"] <= self.max_dimension_size:
            return self.decompress_one(compressed_path=compressed_path,
                                       reconstructed_path=reconstructed_path,
                                       original_file_info=original_file_info)
        else:
            tl_reader = tarlite.TarliteReader(tarlite_path=compressed_path)
            img = np.zeros(
                (original_file_info["width"], original_file_info["height"], original_file_info["component_count"]),
                dtype=isets.iproperties_row_to_numpy_dtype(image_properties_row=original_file_info))
            total_decompression_time = 0
            with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
                tl_reader.extract_all(output_dir_path=tmp_dir)
                invocation = f"ls -lah {tmp_dir}"
                status, output = subprocess.getstatusoutput(invocation)
                if status != 0:
                    raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                        status, invocation, output))

                for y in range(self.split_height_count):
                    for x in range(self.split_width_count):
                        small_compressed_path = os.path.join(tmp_dir, f"{x}_{y}.mcalic")
                        assert os.path.exists(small_compressed_path)
                        small_path = os.path.join(tmp_dir, f"{x}_{y}.raw")
                        small_file_info = copy.copy(original_file_info)

                        small_file_info["height"] = original_file_info["height"] // self.split_height_count \
                            if y < self.split_height_count - 1 \
                            else original_file_info["height"] - (self.split_height_count - 1) * (
                                original_file_info["height"] // self.split_height_count)

                        small_file_info["width"] = original_file_info["width"] // self.split_width_count \
                            if x < self.split_width_count - 1 \
                            else original_file_info["width"] - (self.split_width_count - 1) * (
                                original_file_info["width"] // self.split_width_count)

                        dr = self.decompress_one(compressed_path=small_compressed_path, reconstructed_path=small_path,
                                                 original_file_info=small_file_info)
                        total_decompression_time += dr.decompression_time_seconds
                        small_array = isets.load_array_bsq(file_or_path=small_path,
                                                           image_properties_row=small_file_info)
                        img[x * (original_file_info["width"] // self.split_width_count):
                            (((x + 1) * (original_file_info[
                                             "width"] // self.split_width_count)) if x < self.split_width_count - 1 else
                             original_file_info["width"]),
                        y * (original_file_info["height"] // self.split_height_count):
                        (((y + 1) * (original_file_info[
                                         "height"] // self.split_height_count)) if y < self.split_height_count - 1 else
                         original_file_info["height"]),
                        :] = small_array
                isets.dump_array_bsq(array=img, file_or_path=reconstructed_path)

            decompression_results = self.decompression_results_from_paths(
                compressed_path=compressed_path, reconstructed_path=reconstructed_path)
            decompression_results.decompression_time_seconds = total_decompression_time
            return decompression_results

    def decompress_one(self, compressed_path, reconstructed_path, original_file_info=None):
        total_decompression_time = 0
        with tempfile.NamedTemporaryFile(
                dir=options.base_tmp_dir,
                prefix=f"reconstructed_{os.path.basename(reconstructed_path)}",
                suffix=".raw") as bil_le_file:
            offset = 0
            if original_file_info["signed"]:
                reader = tarlite.TarliteReader(compressed_path)
                with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_extract_dir:
                    reader.extract_all(tmp_extract_dir)

                    import subprocess
                    invocation = f"ls -lah {tmp_extract_dir}"
                    status, output = subprocess.getstatusoutput(invocation)
                    if status != 0:
                        raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                            status, invocation, output))

                    with open(glob.glob(os.path.join(tmp_extract_dir, "*.txt"))[0]) as si_file:
                        offset = int(si_file.read())
                        assert offset >= 0

                    os.path.getsize(tmp_extract_dir)
                    inner_compressed_path = glob.glob(os.path.join(tmp_extract_dir, "*.mcalic"))[0]

                    dr = self.decompress_short_names(compressed_path=inner_compressed_path,
                                                     reconstructed_path=bil_le_file.name,
                                                     original_file_info=original_file_info)
                    total_decompression_time += dr.decompression_time_seconds
            else:
                dr = self.decompress_short_names(compressed_path=compressed_path, reconstructed_path=bil_le_file.name,
                                                 original_file_info=original_file_info)
                total_decompression_time += dr.decompression_time_seconds

            original_dtype = isets.iproperties_row_to_numpy_dtype(image_properties_row=original_file_info)

            img = np.fromfile(bil_le_file.name, dtype=original_dtype.replace(">", "<").replace("i", "u")).reshape(
                original_file_info["height"], original_file_info["component_count"], original_file_info["width"])

            if original_file_info["signed"]:
                if offset != 0:
                    img = (img.astype("i4") - offset).astype(original_dtype)
                else:
                    img = img.astype(original_dtype)

            img = img.swapaxes(0, 1)
            if original_file_info["big_endian"] and not original_file_info["signed"]:
                # Signed file are already converted back to big_endian if necessary in the previous call to astype()
                img = img.astype(original_dtype)
            img.tofile(reconstructed_path)

        try:
            # The decoder always produces this file
            os.remove("seqRec")
        except FileNotFoundError:
            pass

        decompression_results = self.decompression_results_from_paths(compressed_path=compressed_path,
                                                                      reconstructed_path=reconstructed_path)
        decompression_results.decompression_time_seconds = total_decompression_time
        return decompression_results

    def decompress_short_names(self, compressed_path, reconstructed_path, original_file_info):
        """Binary seems to have problems with too long file names
        """
        c_path = f"{random.randint(0, 10000000)}.raw"
        r_path = f"{random.randint(0, 10000000)}.raw"
        try:
            shutil.copyfile(compressed_path, c_path)
            decompression_results = super().decompress(compressed_path=c_path,
                                                       reconstructed_path=r_path,
                                                       original_file_info=original_file_info)
            shutil.copyfile(r_path, reconstructed_path)
            decompression_results.compressed_path = compressed_path
            decompression_results.reconstructed_path = reconstructed_path
            return decompression_results
        finally:
            for p in (c_path, r_path):
                if os.path.exists(p):
                    os.remove(p)

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{reconstructed_path} {compressed_path} " \
               f"{original_file_info['component_count']} {original_file_info['height']} {original_file_info['width']} " \
               f"{8*original_file_info['bytes_per_sample']} {self.param_dict['max_error']} {self.param_dict['data_format']}"

    @property
    def label(self):
        return "M-CALIC"
