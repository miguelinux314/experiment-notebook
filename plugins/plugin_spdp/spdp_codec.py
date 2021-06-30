#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the SPDP lossless image coder
"""

import os
import enb
from enb.config import options


class Spdp(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.WrapperCodec):
    """Wrapper for the SPDP codec
    All data types integer and float 16, 32, 64 can be compressed 
    """

    def __init__(self,spdp_binary=os.path.join(os.path.dirname(__file__), "spdp"), compression_level=9):

        super().__init__(compressor_path=spdp_binary,
                         decompressor_path=spdp_binary,
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
        return "spdp"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f" {self.param_dict['compression_level']} <{original_path}>  {compressed_path}" 


    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" <{compressed_path}> {reconstructed_path} " 