#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the bitstream module
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"

import os
import unittest

import random
random.seed(0xbadc0f33)

from enb import bitstream


class TestBitstream(unittest.TestCase):
    def test_individual_bits(self):
        # input_bits = [0,1,1,1,0,0,0,1,1,0,0,1,1,0,0,0,1]
        global_input_bits = [0, 1, 1, 1, 0, 0, 0, 1,
                             1, 0, 0, 1, 1, 0, 0, 0,
                             1]
        tmp_path = "test.bin"
        try:
            for input_bits in (global_input_bits[:i] for i in range(1, len(global_input_bits) + 1)):
                with bitstream.OutputBitStream(tmp_path) as obs:
                    for bit in input_bits:
                        obs.put_bit(bit)

                with bitstream.InputBitStream(tmp_path) as ibs:
                    read_bits = [ibs.get_bit() for _ in range(len(input_bits))]

                assert input_bits == read_bits
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_unsigned_values(self):
        tmp_path = "test.bin"
        try:
            value_count = 64
            for B in range(1, 65):
                global_input_values = [random.randint(0, 2**B - 1) for _ in range(value_count)]
                for input_values in (global_input_values[:i] for i in range(1, len(global_input_values)+1)):
                    with bitstream.OutputBitStream(tmp_path) as obs:
                        for value in input_values:
                            obs.put_unsigned_value(value=value, nbits=B)

                    with bitstream.InputBitStream(tmp_path) as ibs:
                        read_values = [ibs.get_unsigned_value(nbits=B) for _ in range(len(input_values))]

                    assert input_values == read_values
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == '__main__':
    unittest.main()
