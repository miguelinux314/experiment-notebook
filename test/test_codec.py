#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the codec.py module
"""
import sys
import unittest
import os
import filecmp
import argparse
import shutil
import random

random.seed(0xbadc0f33)

from test_all import options
import codec
import codec_implementations
from codec_implementations import codec_pocket


class TrivialLosslessCodec(codec.LosslessCodec):
    """Trivial is_lossless codec (simply copy and read the file)
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        """Compress original_path into compress_path using param_dict as params.
        :return a CompressionResults instance
        """
        shutil.copyfile(original_path, compressed_path)

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        """Decompress compressed_path into reconstructed_path using param_dict
        as params (if needed).
        :return a DecompressionResults instance
        """
        shutil.copyfile(compressed_path, reconstructed_path)


class TrivialCpWrapper(codec.WrapperCodec, codec.LosslessCodec):
    """Trivial codec wrapper for /bin/cp
    """

    def __init__(self):
        super().__init__(compressor_path="cp", decompressor_path="cp")

    def get_compression_params(self, original_path, compressed_path, original_file_info: codec.FileInfo):
        return f"'{original_path}' '{compressed_path}'"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info: codec.FileInfo):
        return f"'{compressed_path}' '{reconstructed_path}'"


class TestAllCodecs(unittest.TestCase):
    """Test the AbstractCodec class
    """

    def test_trivial_lossless(self):
        """Test the trivial raw-output codec.
        """
        for cls in [TrivialLosslessCodec, TrivialCpWrapper]:
            test_one_codec(cls())

    def test_all_lossless(self):
        """Test all lossless codecs
        """
        for cls in codec.get_lossless_codec_classes():
            if cls.__name__ == codec_pocket.PocketPlusCWE_Aug2019.__name__:
                c = cls(window=1)
            else:
                c = cls()
            test_one_codec(c)


def test_one_codec(codec_instance):

    if options.verbose:
        print(f"\n\tLossless check for {codec_instance.name}")

    FL, packet_count = 3, 1024
    original_path = f"test_raw.FL{FL}bytes.raw"
    compressed_path = "compressed.bin"
    reconstructed_path = "reconstructed.raw"
    try:
        output_bytes = bytearray()
        for _ in range(FL * packet_count):
            output_bytes.append(random.randint(0, 255))
        output_file = open(original_path, "wb")
        output_file.write(output_bytes)
        output_file.close()
        cr = codec_instance.compress(original_path=original_path,
                                     compressed_path=compressed_path)
        dr = codec_instance.decompress(compressed_path=compressed_path,
                                       reconstructed_path=reconstructed_path)
        if cr:
            assert cr.original_path == original_path
            assert cr.compressed_path == compressed_path
            assert cr.codec_name == codec_instance.name
        if dr:
            assert dr.compressed_path == compressed_path
            assert dr.reconstructed_path == reconstructed_path
        if cr and dr:
            assert dr.codec_name == cr.codec_name
            assert dr.codec_param_dict == cr.codec_param_dict
        assert os.path.exists(reconstructed_path), \
            f"Codec {codec_instance.name} did not produce any compressed file"
        assert filecmp.cmp(original_path, reconstructed_path), \
            (codec_instance, original_path, compressed_path, reconstructed_path)
    finally:
        for p in (original_path, compressed_path, reconstructed_path):
            if os.path.exists(p):
                os.remove(p)


if __name__ == '__main__':
    unittest.main()
