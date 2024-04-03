#!/usr/bin/env python3
"""Wrappers for the LC framework implementation
"""
__author__ = "Pau Quintas Torra, Xavier Fernandez Mellado"
__since__ = "2024/04/03"

import os
from enb import icompression


class LCFramework(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self,
                 compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "compress"),
                 decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "decompress")):

        super().__init__(compressor_path=compressor_path,
                         decompressor_path=decompressor_path)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return f"LC_Framework"
