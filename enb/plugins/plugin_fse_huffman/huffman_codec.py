#!/usr/bin/env python3
"""FSE's Huff0 codec wrapper.
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2021/06/01"

import os
from enb import icompression


class FSEHuffman(icompression.WrapperCodec, icompression.LosslessCodec):
    """FSE's Huff0 codec wrapper (block adaptive)
    """
    def __init__(self, huff_binary=os.path.join(os.path.dirname(os.path.abspath(__file__)), "fse")):
        icompression.WrapperCodec.__init__(self,
                                           compressor_path=huff_binary,
                                           decompressor_path=huff_binary,
                                           param_dict=None, output_invocation_dir=None)

        self.huff_binary = huff_binary

        assert os.path.isfile(huff_binary)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        try:
            os.remove(compressed_path)
        except FileNotFoundError:
            pass
        return f"-h {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        try:
            os.remove(reconstructed_path)
        except FileNotFoundError:
            pass
        return f"-h -d {compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return "Huffman (block adaptive)"
