#!/usr/bin/env python3
"""Wrapper for the JPEG-XL reference implementation
"""
__author__ = "Ashwin Kumar Gururajan <ashwin.gururajan@uab.cat>"
__since__ = "2021/02/15"

import os
from enb import icompression


class JPEG_XL(icompression.LosslessCodec, icompression.LossyCodec, icompression.PNGWrapperCodec):
    def __init__(self, quality_0_to_100=100, compression_level=7,
                 lossless=True,
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
        :param lossless: if True, the modular mode of JPEG-XL is employed (in this case quality 100 is required)
        """
        assert 3 <= compression_level <= 9
        assert 0 <= quality_0_to_100 <= 100
        assert (not lossless) or quality_0_to_100 == 100, f"Lossless mode can only be employed with quality 100"
        icompression.PNGWrapperCodec.__init__(
            self, compressor_path=compressor_path, decompressor_path=decompressor_path,
            param_dict=dict(
                quality_0_to_100=quality_0_to_100,
                compression_level=compression_level,
                lossless=lossless),
            output_invocation_dir=None)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["component_count"] == 1, \
            f"Only one component seems to be supported by {self.__class__.__name__}"
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are supported by {self.__class__.__name__}"

        return f"{original_path} {compressed_path} " \
               f"-q {self.param_dict['quality_0_to_100']} " \
               f"-e {self.param_dict['compression_level']}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return f"JPEG XL"
