#!/usr/bin/env python3
"""Codec wrapper for the zfp lossless image coder 
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2021/06/01"

import os
import enb


class Zfp(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.WrapperCodec):
    """Wrapper for the zfp codec
    Allowed data type to be compressed: integer 32 & 64 , float 32 & 64
    """

    def __init__(self, zfp_binary=os.path.join(os.path.dirname(__file__), "zfp")):
        """
        param:dtype: valid types in zfp are f32, f64, i32 and i64
        """
        super().__init__(compressor_path=zfp_binary,
                         decompressor_path=zfp_binary,
                         param_dict=dict())

    @property
    def label(self):
        return "ZFP"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] != 2, 'data type can not be 16 bpp'
        dimensions = 1

        if original_file_info.float == True:
            return f"-i {os.path.abspath(original_path)} " \
                   f"-z {os.path.abspath(compressed_path)} " \
                   f"-t f{original_file_info.bytes_per_sample * 8} " \
                   f"-{dimensions} {original_file_info.samples} -R"

        if original_file_info.float == False:
            return f"-i {os.path.abspath(original_path)} " \
                   f"-z {os.path.abspath(compressed_path)} " \
                   f"-t i{original_file_info.bytes_per_sample * 8} " \
                   f"-{dimensions} {original_file_info.samples} -R"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        dimensions = 1
        # TODO: include {original_file_info.samples} instead of defining a dummy variable (here and everywhere else)
        if original_file_info.float == True:
            return f" -z {os.path.abspath(compressed_path)} " \
                   f"-o {os.path.abspath(reconstructed_path)}  " \
                   f"-t f{original_file_info.bytes_per_sample * 8} " \
                   f"-{dimensions} {original_file_info.samples} -R"

        if original_file_info.float == False:
            return f" -z {os.path.abspath(compressed_path)} " \
                   f"-o {os.path.abspath(reconstructed_path)}  " \
                   f"-t i{original_file_info.bytes_per_sample * 8} " \
                   f"-{dimensions} {original_file_info.samples} -R"
