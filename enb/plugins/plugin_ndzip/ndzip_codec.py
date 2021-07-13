#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the Ndzip lossless image coder
"""

import os
import enb


class Ndzip(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.WrapperCodec):
    """Wrapper for the Ndzip codec.
    Only float 16, 32 and 64 can be compressed .
    """

    def __init__(self, ndzip_binary=os.path.join(os.path.dirname(__file__), "compress")):

        super().__init__(compressor_path=ndzip_binary,
                         decompressor_path=ndzip_binary,
                         param_dict=dict())

    @property
    def label(self):
        return "ndzip"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["float"] == True, 'data type must be float or double'
        if original_file_info.bytes_per_sample * 8 == 64:
            return f"-t double -n {original_file_info.samples} -i {original_path} -o {compressed_path}"

        elif original_file_info.bytes_per_sample * 8 == 32:
            return f"-t float -n {original_file_info.samples} -i {original_path} -o {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):

        if original_file_info.bytes_per_sample * 8 == 64:
            return f"-d -t double -n {original_file_info.samples} -i {compressed_path} -o {reconstructed_path}"

        elif original_file_info.bytes_per_sample * 8 == 32:
            return f"-d -t float -n {original_file_info.samples} -i {compressed_path} -o {reconstructed_path}"