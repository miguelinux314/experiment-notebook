#!/usr/bin/env python3
"""Codec wrapper for the Zstandard lossless image coder
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/07/12"

import os
import enb
from enb import tarlite
import tempfile
import subprocess

class Zstandard(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.fits.FITSWrapperCodec):
    """Wrapper for the Zstandard codec
    All data types integer and float 16, 32, 64 can be compressed
    """

    def __init__(self, compression_level=19, zstd_binary=os.path.join(os.path.dirname(__file__), "zstd")):
        """
        :param compression_level: 1-22, being 22 the maximum data reduction
        """
        assert 1 <= int(compression_level) <= 22, f"Invalid compression level {compression_level}"
        super().__init__(compressor_path=zstd_binary,
                         decompressor_path=zstd_binary,
                         param_dict=dict(compression_level=compression_level))

    @property
    def label(self):
        return f"Zstandard {self.param_dict['compression_level']}"

    def assert_valid_data_type(self, original_file_info):
        """Verify that the input data type is supported, else raise an exception
        """
        assert not original_file_info["float"], f"Only integer samples are supported by {self.__class__.__name__}"
        assert original_file_info["big_endian"], f"Only big-endian samples are supported by {self.__class__.__name__}"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        self.assert_valid_data_type(original_file_info=original_file_info)
        return f"-{self.param_dict['compression_level']} " \
               f"{'--ultra ' if self.param_dict['compression_level'] > 19 else ''}" \
               f"-f {original_path}  -o {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-d  -f {compressed_path} -o {reconstructed_path}"


class Zstandard_train(Zstandard):
    """Wrapper for the Zstandard codec, which produces a dictionary file for the input data and then employs
    it for compression. The generated dictionary is included in the compressed data size measurements.

    All data types integer and float 16, 32, 64 can be compressed
    """

    def assert_valid_data_type(self, original_file_info):
        """Verify that the input data type is supported, else raise an exception
        """
        super().assert_valid_data_type(original_file_info=original_file_info)
        assert original_file_info["bytes_per_sample"] == 4, \
            f"Only 32-bit samples are supported by {self.__class__.__name__}"

    def compress(self, original_path, compressed_path, original_file_info):
        self.assert_valid_data_type(original_file_info=original_file_info)

        with tempfile.TemporaryDirectory(dir=enb.config.options.base_tmp_dir) as tmp_dir:
            dict_path = os.path.join(tmp_dir, "dict.zstd")
            dict_compressed_path = os.path.join(tmp_dir, "compressed.zstd")

            # Generate dictionary
            invocation = f"{self.compressor_path} --train {original_path} --optimize-cover -o {dict_path}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Status = {status} != 0.\n"
                                f"Input=[{invocation}].\n"
                                f"Output=[{output}]")

            # Compress using that dictionary
            invocation = f" {self.compressor_path} " \
                         f"{'--ultra ' if int(self.param_dict['compression_level']) > 19 else ''}" \
                         f"-{self.param_dict['compression_level']} -D {dict_path} -f {original_path} " \
                         f"-o {dict_compressed_path}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Status = {status} != 0.\n"
                                f"Input=[{invocation}].\n"
                                f"Output=[{output}]")

            # Unite the compressed data and the side information
            tarlite.tarlite_files(input_paths=(dict_path, dict_compressed_path), output_tarlite_path=compressed_path)

    def decompress(self, compressed_path, reconstructed_path, original_file_info):
        with tempfile.TemporaryDirectory(dir=enb.config.options.base_tmp_dir) as tmp_dir:
            dict_path = os.path.join(tmp_dir, "dict.zstd")
            dict_compressed_path = os.path.join(tmp_dir, "compressed.zstd")

            # Separate the compressed data from the side information
            tarlite.untarlite_files(input_tarlite_path=compressed_path, output_dir_path=tmp_dir)

            # Decompress
            invocation = f"{self.compressor_path} -d -D {dict_path} -f {dict_compressed_path} -o {reconstructed_path}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Status = {status} != 0.\n"
                                f"Input=[{invocation}].\n"
                                f"Output=[{output}]")

    @property
    def label(self):
        return f"Zstandard pretrain {self.param_dict['compression_level']}"
