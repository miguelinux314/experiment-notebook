#!/usr/bin/env python3
"""Codec wrapper for the FLIF lossless image coder (precursor of JPEG-LS)
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/02/09"

import os
import enb


class FLIF(enb.icompression.LosslessCodec, enb.icompression.PNGWrapperCodec):
    def __init__(self, flif_binary=os.path.join(os.path.dirname(__file__), "flif"),
                 effort_percentage=60):
        super().__init__(compressor_path=flif_binary, decompressor_path=flif_binary,
                         param_dict=dict(effort_percentage=effort_percentage))

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 1, f"This implementation of FLIF supports only 8-bit images"
        assert original_file_info["component_count"] == 1, f"Flif can only guarantee losslessness for 1 component"
        return f"-e --effort={self.param_dict['effort_percentage']} " \
               f"--overwrite {original_path} {compressed_path} " \
               f"--no-interlace "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-d --overwrite {compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return "FLIF"
