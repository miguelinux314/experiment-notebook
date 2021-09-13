#!/usr/bin/env python3
"""Codec wrapper for the FPC lossless image coder
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import os
import enb


class Fpc(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.WrapperCodec):
    """Wrapper for the FPC codec
    All data types integer and float 16, 32, 64 can be compressed 
    """

    def __init__(self, fpc_binary=os.path.join(os.path.dirname(__file__), "fpc"), compression_level=25):
        super().__init__(compressor_path=fpc_binary,
                         decompressor_path=fpc_binary,
                         param_dict=dict(compression_level=compression_level))
        """
        :param compression_level: 1-29, being 29 the maximum data reduction       
        """

    @property
    def label(self):
        return "FPC"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f" {self.param_dict['compression_level']} <{original_path}>  {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" < {compressed_path} > {reconstructed_path} "
