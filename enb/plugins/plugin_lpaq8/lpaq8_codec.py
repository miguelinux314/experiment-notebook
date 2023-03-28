#!/usr/bin/env python3
"""Wrappers for the reference JPEG implementation
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2023/01/12"

import os
from enb import icompression


class LPAQ8(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self, N=9,
                 compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "lpaq8"),
                 decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "lpaq8"),
                 output_invocation_dir=None,
                 signature_in_name=False):
        """
        :param N: Memory usage is 6 + 3*2^N MB  (9 to 1542 MB). 
          Larger numbers usually give better compression at similar speed.
        """
        assert N == int(N), f"N must be an integer value"
        assert 0 <= N <= 9, f"N must be between 0 and 9, both included"
        super().__init__(compressor_path=compressor_path,
                         decompressor_path=decompressor_path,
                         param_dict=dict(N=int(N)),
                         output_invocation_dir=output_invocation_dir,
                         signature_in_name=signature_in_name)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{self.param_dict['N']} {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"d {compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return f"LPAQ8 N{self.param_dict['N']}"
