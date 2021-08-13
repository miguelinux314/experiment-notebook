#!/usr/bin/env python3
"""Trivial codec implementations, mostly for testing purposes.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/03/31"

import shutil
import numpy as np

import enb.icompression as icompression
import enb.isets as isets


class TrivialLosslessCodec(icompression.LosslessCodec):
    """Trivial is_lossless codec (files are copied without any further processing)
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        """Compress original_path into compress_path using param_dict as params.
        :return: a CompressionResults instance
        """
        shutil.copyfile(original_path, compressed_path)

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        """Decompress compressed_path into reconstructed_path using param_dict
        as params (if needed).
        :return: a DecompressionResults instance
        """
        shutil.copyfile(compressed_path, reconstructed_path)


class TrivialCpWrapper(icompression.WrapperCodec, icompression.LosslessCodec):
    """Trivial codec wrapper for /bin/cp.
    """

    def __init__(self):
        super().__init__(compressor_path="cp", decompressor_path="cp")

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"'{original_path}' '{compressed_path}'"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"'{compressed_path}' '{reconstructed_path}'"


class OffsetLossyCodec(icompression.LossyCodec):
    """Trivial lossy codec that adds a constant to every pixel of the image,
    and stores the result with the same data format as the original.
    Note that overflows result in wrap around values (max+1 results in 0)
    """

    def __init__(self, constant):
        super().__init__(param_dict=dict(constant=constant))

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        array = isets.load_array_bsq(
            file_or_path=original_path, image_properties_row=original_file_info)
        array += self.param_dict["constant"]
        isets.dump_array_bsq(array=array, file_or_path=compressed_path)

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        shutil.copyfile(compressed_path, reconstructed_path)
