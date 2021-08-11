#!/usr/bin/env python3
"""Wrapper for the JPEG-XL reference implementation
"""
__author__ = "Ashwin Kumar Gururajan <ashwin.gururajan@uab.cat>"
__since__ = "2021/02/15"

import os
from enb import icompression


class JPEG_XL(icompression.LosslessCodec, icompression.PNGWrapperCodec):
    def __init__(self, quality_0_to_100=100, compression_level=7,
                 compressor_path=os.path.join(os.path.dirname(__file__), "cjxl"),
                 decompressor_path=os.path.join(os.path.dirname(__file__), "djxl")):
        """
        :param quality_0_to_100: Quality setting. Range: -inf .. 100.
        100 = mathematically lossless. Default for already-lossy input (JPEG/GIF).
        Positive quality values roughly match libjpeg quality.
        Uses jpeg_xl parameter -q and was chosen over -d maxError
        (defined by butteraugli distance) becuase of slightly better throughput
        (approx 1.2 Mp/s) under lossless mode
        :param compression_level: higher values mean slower compression
        """
        assert 3 <= compression_level <= 9
        assert 0 <= quality_0_to_100 <= 100
        icompression.PNGWrapperCodec.__init__(
            self, compressor_path=compressor_path, decompressor_path=decompressor_path,
            param_dict=dict(quality_0_to_100=quality_0_to_100, compression_level=compression_level),
            output_invocation_dir=None)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_path} {compressed_path} " \
               f"-q {self.param_dict['quality_0_to_100']} " \
               f"-s {self.param_dict['compression_level']}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return f"JPEG XL"
