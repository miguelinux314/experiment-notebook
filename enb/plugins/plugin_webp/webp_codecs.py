#!/usr/bin/env python3
"""Wrappers for the reference WebP implementation.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2025/11/12"

import os
import tempfile

import enb
from enb import icompression
from enb.config import options
from enb.compression.png import raw_path_to_png, png_to_raw


class WebP(enb.icompression.WrapperCodec):
    def __init__(self, quality=75):
        assert 0 <= quality <= 100, "Quality must be between 0 and 100"
        super().__init__(
            compressor_path=os.path.join(os.path.dirname(__file__), "cwebp"),
            decompressor_path=os.path.join(os.path.dirname(__file__), "dwebp"),
        )
        self.param_dict["quality"] = quality

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        with tempfile.NamedTemporaryFile(dir=options.base_tmp_dir) as png_path:
            raw_path_to_png(raw_path=original_path,
                            png_path=png_path.name,
                            image_properties_row=original_file_info)
            super().compress(original_path=png_path.name,
                             compressed_path=compressed_path,
                             original_file_info=original_file_info)

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with tempfile.NamedTemporaryFile(dir=options.base_tmp_dir) as png_path:            
            super().decompress(compressed_path=compressed_path,
                               reconstructed_path=png_path.name,
                               original_file_info=original_file_info)
            png_to_raw(input_path=png_path.name,
                       output_path=reconstructed_path,
                       adjust_output_path=False)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return (f"-q {self.param_dict['quality']} "
                f"{original_path} "
                f"-o {compressed_path}")

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} -o {reconstructed_path}"
