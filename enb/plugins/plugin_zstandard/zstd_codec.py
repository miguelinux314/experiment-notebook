#!/usr/bin/env python3
"""Codec wrapper for the Zstandard lossless image coder
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/07/12"

import os
import enb


class Zstandard(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the Zstandard codec
    All data types integer and float 16, 32, 64 can be compressed 
    """

    def __init__(self, compression_level='19', zstd_binary=os.path.join(os.path.dirname(__file__), "zstd")):
        """
        :param compression_level: 1-19, being 19 the maximum data reduction
        """
        super().__init__(compressor_path=zstd_binary,
                         decompressor_path=zstd_binary,
                         param_dict=dict(compression_level=compression_level))

    @property
    def label(self):
        return "Zstandard"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-{self.param_dict['compression_level']} -f {original_path}  -o {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-d -f {compressed_path} -o {reconstructed_path}"
