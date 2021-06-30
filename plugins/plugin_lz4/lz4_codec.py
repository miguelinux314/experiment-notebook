#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the LZ4 lossless image coder
"""

import os
import enb
from enb.config import options


class Lz4(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the LZ4 codec
    All data types integer and float 16, 32, 64 can be compressed 
    """

    def __init__(self,lz4_binary=os.path.join(os.path.dirname(__file__), "lz4"), compression_level=9):

        super().__init__(compressor_path=lz4_binary,
                         decompressor_path=lz4_binary,
                         param_dict=dict(compression_level=compression_level))
        """
        :param compression_level: 1-9, being 9 the maximum data reduction       
        """

    @property
    def name(self):
        """Don't include the binary signature
        """
        name = f"{self.__class__.__name__}{'__' if self.param_dict else ''}" \
               f"{'_'.join(f'{k}={v}' for k, v in self.param_dict.items())}"
        return name

    @property
    def label(self):
        return "lz4"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f" -{self.param_dict['compression_level']} -k {original_path}  {compressed_path}" 


    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" -d -{self.param_dict['compression_level']}  {compressed_path} {reconstructed_path} " 