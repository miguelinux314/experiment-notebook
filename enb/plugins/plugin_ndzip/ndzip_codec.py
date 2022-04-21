#!/usr/bin/env python3
"""Codec wrapper for the Ndzip lossless image coder
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/05/25"

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
        assert original_file_info["float"] == True, f"Only floating point data is supported by {self.label}"
        if original_file_info["bytes_per_sample"] == 8:
            return f"-t double -n {original_file_info['samples']} -i {original_path} -o {compressed_path}"
        elif original_file_info["bytes_per_sample"] == 4:
            return f"-t float -n {original_file_info['samples']} -i {original_path} -o {compressed_path}"
        else:
            raise ValueError(f"Only 32-bit and 64-bit float samples are supported by {self.label}")

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        assert original_file_info["float"] == True, f"Only floating point data is supported by {self.label}"
        if original_file_info["bytes_per_sample"] == 8:
            return f"-d -t double -n {original_file_info['samples']} -i {compressed_path} -o {reconstructed_path}"
        elif original_file_info["bytes_per_sample"] == 4:
            return f"-d -t float -n {original_file_info['samples']} -i {compressed_path} -o {reconstructed_path}"
        else:
            raise ValueError(f"Only 32-bit and 64-bit float samples are supported by {self.label}")
