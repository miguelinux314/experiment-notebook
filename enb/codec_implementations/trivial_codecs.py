#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "31/03/2020"

import shutil
import enb.codec as codec


class TrivialLosslessCodec(codec.LosslessCodec):
    """Trivial is_lossless codec (files are copied without any further processing)
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        """Compress original_path into compress_path using param_dict as params.
        :return a CompressionResults instance
        """
        shutil.copyfile(original_path, compressed_path)

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        """Decompress compressed_path into reconstructed_path using param_dict
        as params (if needed).
        :return a DecompressionResults instance
        """
        shutil.copyfile(compressed_path, reconstructed_path)


class TrivialCpWrapper(codec.WrapperCodec, codec.LosslessCodec):
    """Trivial codec wrapper for /bin/cp.
    """

    def __init__(self):
        super().__init__(compressor_path="cp", decompressor_path="cp")

    def get_compression_params(self, original_path, compressed_path, original_file_info: codec.FileInfo):
        return f"'{original_path}' '{compressed_path}'"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info: codec.FileInfo):
        return f"'{compressed_path}' '{reconstructed_path}'"
