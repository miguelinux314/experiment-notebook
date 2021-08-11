#!/usr/bin/env python3
"""Codec wrapper for the fpzip lossless image coder
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2021/06/01"

import os
import enb


class Fpzip(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.WrapperCodec):
    """Wrapper for the fpzip codec
    Allowed data type to be compressed: float 32
    """

    def __init__(self, fpzip_binary=os.path.join(os.path.dirname(__file__), "fpzip")):
        super().__init__(compressor_path=fpzip_binary,
                         decompressor_path=fpzip_binary,
                         param_dict=dict())

    @property
    def label(self):
        return "FPZIP"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 4 and original_file_info[
            "float"] == True, 'data type must be float 32'
        dimensions = 1

        return f"-i {os.path.abspath(original_path)} " \
               f" -o {os.path.abspath(compressed_path)} " \
               f"-{dimensions} {original_file_info.samples} "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        dimensions = 1

        return f"-d -i {compressed_path} -o {reconstructed_path} -{dimensions} {original_file_info.samples} "
