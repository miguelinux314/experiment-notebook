#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Implementation of a Codec that wraps the direct and inverse
Burrows-Wheeler Transform (BWT).
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "15/02/2023"

import os
import enb


class BWT(enb.icompression.LosslessCodec, enb.icompression.WrapperCodec):
    """Implementation of a Codec that wraps the direct and inverse
    Burrows-Wheeler Transform (BWT).

    Note: this codec does not perform any compression on its own.
    """

    def __init__(self, output_invocation_dir=None, signature_in_name=False):
        bwt_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "bwt")
        super().__init__(
            compressor_path=bwt_path, decompressor_path=bwt_path,
            param_dict=None, output_invocation_dir=output_invocation_dir,
            signature_in_name=signature_in_name)

    def get_compression_params(
            self, original_path, compressed_path, original_file_info):
        return f"-c -i {original_path} -o {compressed_path}"

    def get_decompression_params(
            self, compressed_path, reconstructed_path, original_file_info):
        return f"-d -i {compressed_path} -o {reconstructed_path}"
