#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrappers for different types of LZ codecs such as Deflate, LZMA, BZIP2
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "04/01/2021"

import zlib
import lzma
import bz2

from enb import icompression


class AbstractZipCodec(icompression.LosslessCodec):
    MIN_COMPRESSION_LEVEL = 1
    MAX_COMPRESSION_LEVEL = 9
    DEFAULT_COMPRESSION_LEVEL = 5

    def __init__(self, compression_level=DEFAULT_COMPRESSION_LEVEL, param_dict=None):
        assert self.MIN_COMPRESSION_LEVEL <= compression_level <= self.MAX_COMPRESSION_LEVEL
        param_dict = dict() if param_dict is None else param_dict
        param_dict["compression_level"] = compression_level
        super().__init__(param_dict=param_dict)


class LZ77Huffman(AbstractZipCodec):
    """Apply the LZ77 algorithm and Huffman coding to the file using zlib.
    """

    def compress(self, original_path, compressed_path, original_file_info):
        with open(original_path, "rb") as original_file, open(compressed_path, "wb") as compressed_file:
            compressed_file.write(zlib.compress(original_file.read(), level=self.param_dict["compression_level"]))

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with open(compressed_path, "rb") as compressed_file, open(reconstructed_path, "wb") as reconstructed_file:
            reconstructed_file.write(zlib.decompress(compressed_file.read()))

    @property
    def label(self):
        return f"LZ77Huff {self.param_dict['compression_level']}"


class LZMA(AbstractZipCodec):
    """Apply the LZMA algorithm using the lzma library
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        with open(original_path, "rb") as input_file, open(compressed_path, "wb") as output_file:
            output_file.write(lzma.compress(input_file.read(), preset=self.param_dict["compression_level"]))

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with open(compressed_path, "rb") as compressed_file, open(reconstructed_path, "wb") as reconstructed_file:
            reconstructed_file.write(lzma.decompress(compressed_file.read()))

    @property
    def label(self):
        return f"LZMA {self.param_dict['compression_level']}"


class BZIP2(AbstractZipCodec):
    """Apply the BZIP2 algorithm using zlib.
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        with open(original_path, "rb") as input_file, open(compressed_path, "wb") as output_file:
            output_file.write(bz2.compress(input_file.read(), self.param_dict["compression_level"]))

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with open(compressed_path, "rb") as compressed_file, open(reconstructed_path, "wb") as reconstructed_file:
            reconstructed_file.write(bz2.decompress(compressed_file.read()))

    @property
    def label(self):
        return f"BZIP2 {self.param_dict['compression_level']}"
