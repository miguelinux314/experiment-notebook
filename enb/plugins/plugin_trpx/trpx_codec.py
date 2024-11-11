#!/usr/bin/env python3
"""Wrapper for the Terse/Prolix lossless codec.

https://github.com/senikm/trpx
https://senikm.github.io/trpx/
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2024/11/11"

import os

import enb.isets
from enb import icompression


class TRPX(icompression.WrapperCodec, icompression.LosslessCodec):
    """Wrapper for the Terse/Prolix lossless codec.
    https://github.com/senikm/trpx
    https://senikm.github.io/trpx/
    """

    def __init__(self, compressor_path=None, decompressor_path=None):
        if compressor_path is None:
            compressor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_codec")
        if decompressor_path is None:
            decompressor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_codec")
        super().__init__(compressor_path=compressor_path, decompressor_path=decompressor_path)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        geometry_dict = enb.isets.file_path_to_geometry_dict(
            file_path=original_path, existing_dict=dict(original_file_info))
        if geometry_dict["float"] is not False or geometry_dict["bytes_per_sample"] not in (1, 2, 4):
            raise ValueError(f"Invalid input data type; only uint8_t, uint16_t and uint32_t are supported,"
                             f"but the following was found for {original_path!r}: {geometry_dict}.")
        return f"compress {geometry_dict['bytes_per_sample']} {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        geometry_dict = dict(original_file_info)
        if geometry_dict["float"] or geometry_dict["bytes_per_sample"] not in (1, 2, 4):
            raise ValueError(f"Invalid input data type; only uint8_t, uint16_t and uint32_t are supported,"
                             f"but the following was found: {geometry_dict}.\n\n"
                             f'@@{geometry_dict["float"]!r}@@')
        return f"decompress {geometry_dict['bytes_per_sample']} {compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return "TRPX"
