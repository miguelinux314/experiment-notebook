#!/usr/bin/env python3
"""Wrapper for Michael Dipperstein's RLE codec, originally downloaded from
https://github.com/MichaelDipperstein/rle. Also see https://michaeldipperstein.github.io/rle.html.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2024/01/15"

import os
from enb import icompression


class RLECodec(icompression.WrapperCodec, icompression.LosslessCodec):
    """Wrapper for Michael Dipperstein's RLE codec, originally downloaded from
    https://michaeldipperstein.github.io/index.html. Also see https://michaeldipperstein.github.io/rle.html.
    """

    def __init__(self, packbits=False, compressor_path=None, decompressor_path=None):
        """
        :param packbits: if True, the packbits variant is employed
        """
        if compressor_path is None:
            compressor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rle")
        if decompressor_path is None:
            decompressor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rle")
        super().__init__(compressor_path=compressor_path, decompressor_path=decompressor_path,
                         param_dict=dict(packbits=packbits))

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-c {'-v' if self.param_dict['packbits'] else ''} -i {original_path} -o {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-d {'-v' if self.param_dict['packbits'] else ''} -i {compressed_path} -o {reconstructed_path}"

    @property
    def label(self):
        return f"RLE{' packbits' if self.param_dict['packbits'] else ''}"
