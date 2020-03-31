#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit testsfor the xor_rle module
"""

import unittest

from enb.codec_implementations import codec_xor_rle
import test_codec


class TestXOR_RLE(unittest.TestCase):
    def test_huffman_table(self):
        test_codec.test_one_codec(codec_xor_rle.XOR_RLE_HuffmanTable())


if __name__ == '__main__':
    unittest.main()
