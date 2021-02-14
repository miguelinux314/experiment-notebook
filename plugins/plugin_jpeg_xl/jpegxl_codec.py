#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper for the JPEG-XL reference implementation
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "09/02/2021"

import os
import enb


class JPEG_XL(enb.icompression.LosslessCodec, enb.icompression.PNGWrapperCodec):
    def __init__(self, quality_0_to_15=0, compression_level=7,
                 compressor_path=os.path.join(os.path.dirname(__file__), "cjxl"),
                 decompressor_path=os.path.join(os.path.dirname(__file__), "djxl")):
        """
        :param quality_0_to_15: butterogli distance; 0 means lossless
        :param compression_level: higher values mean slower compression
        """
        assert 3 <= compression_level <= 9
        super().__init__(compressor_path=compressor_path,
                         decompressor_path=decompressor_path,
                         param_dict=dict(quality_0_to_15=quality_0_to_15,
                                         compression_level=compression_level))

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_path} {compressed_path} " \
               f"-d {self.param_dict['quality_0_to_15']} " \
               f"-s {self.param_dict['compression_levell']}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {reconstructed_path}"
