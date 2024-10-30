#!/usr/bin/env python3
"""Unit tests for the codec wrappers within enb.compression
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2024/10/30"

import unittest
import tempfile
import os
import numpy as np
import filecmp

import test_all
from enb import isets
from enb.compression.wrapper import QuantizationWrapperCodec, ReindexWrapper
import enb.compression.codec


class TestQuantizationWrapperCodec(unittest.TestCase):
    def test_pae(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            width, height, component_count = 128, 128, 12
            array = np.zeros((width, height, component_count), dtype=">u1")
            i = 0
            for z in range(component_count):
                for y in range(height):
                    for x in range(width):
                        array[x, y, z] = i
                        i = (i + 1) % 256

            original_path = os.path.join(tmp_dir, f"img-u8be-{component_count}x{height}x{width}.raw")
            compressed_path = os.path.join(tmp_dir, f"img-u8be-{component_count}x{height}x{width}.comp")
            reconstructed_path = os.path.join(tmp_dir, f"img-u8be-{component_count}x{height}x{width}.rec")

            isets.dump_array_bsq(array, original_path)

            for qstep in (1, 2, 3, 10):
                for p in (compressed_path, reconstructed_path):
                    if os.path.exists(p):
                        os.remove(p)
                q_wrapped_codec = QuantizationWrapperCodec(codec=enb.compression.codec.PassthroughCodec(), qstep=1)
                q_wrapped_codec.compress(original_path, compressed_path)
                q_wrapped_codec.decompress(compressed_path, reconstructed_path)
                reconstructed_array = isets.load_array(reconstructed_path)

                assert np.max(array.astype(np.int64) - reconstructed_array.astype(np.int64)) <= qstep // 2


class TestReindexWrapper(unittest.TestCase):
    def test_reindex_wrapper(self):
        codec = ReindexWrapper(codec=enb.compression.codec.PassthroughCodec(), width_bytes=1)

        with tempfile.TemporaryDirectory() as tmp_dir:
            width, height, component_count = 128, 128, 12
            array = np.zeros((width, height, component_count), dtype=">u2")
            i = 0
            for z in range(component_count):
                for y in range(height):
                    for x in range(width):
                        array[x, y, z] = i
                        i = (i + 1) % 256

            original_path = os.path.join(tmp_dir, f"img-u16be-{component_count}x{height}x{width}.raw")
            compressed_path = original_path[:-len(".raw")] + ".cmp"
            reconstructed_path = original_path[:-len(".raw")] + ".rec"

            isets.dump_array_bsq(array, original_path)
            codec.compress(original_path, compressed_path)
            codec.decompress(compressed_path, reconstructed_path)
            assert filecmp.cmp(original_path, reconstructed_path)


if __name__ == '__main__':
    unittest.main()
