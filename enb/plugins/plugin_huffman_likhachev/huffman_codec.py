#!/usr/bin/env python3
"""Wrapper of Huffman codec from https://github.com/ALikhachev/Huffman-code
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2022/02/26"

import os
from enb import icompression


class HuffmanCodec(icompression.WrapperCodec, icompression.LosslessCodec):
    """Wrapper for Nayuki's arithmetic coder, originally downloaded from 
    https://github.com/nayuki/Reference-arithmetic-coding/
    """

    def __init__(self, compressor_path=None, decompressor_path=None):
        if compressor_path is None:
            compressor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "huffman")
        if decompressor_path is None:
            decompressor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "huffman")
        super().__init__(compressor_path=compressor_path, decompressor_path=decompressor_path)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        try:
            os.remove(compressed_path)
        except FileNotFoundError:
            pass
        return f"qe {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        try:
            os.remove(reconstructed_path)
        except FileNotFoundError:
            pass
        return f"d {compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return "Huffman"
