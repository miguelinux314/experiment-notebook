#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the codec.py module
"""
import unittest
import os
import filecmp
import shutil
import random

random.seed(0xbadc0f33)

from test_all import options
from codec_implementations import trivial_codecs as trivial_codecs


class TestAllCodecs(unittest.TestCase):
    """Test the AbstractCodec class
    """

    def test_trivial_lossless(self):
        """Test the trivial raw-output codec.
        """
        for cls in [trivial_codecs.TrivialLosslessCodec,
                    trivial_codecs.TrivialCpWrapper]:
            test_one_codec(cls())


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
