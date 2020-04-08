#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for isets.py
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "07/04/2020"

import unittest
import tempfile
import os
import numpy as np

import test_all
from enb import pgm
from enb import isets


class TestPGM(unittest.TestCase):

    def test_pgm_read_write(self):
        width = 67
        height = 34

        for bytes_per_sample in [1, 2]:
            array = np.zeros((width, height), dtype=f"u{bytes_per_sample}")
            max_pixel_value = 2 ** (8 * bytes_per_sample) - 1
            i = 0
            for y in range(height):
                for x in range(width):
                    array[x, y] = (i % (max_pixel_value + 1))
                    i += 1
            array[0, 0] = max_pixel_value
            assert array[0, 0] == max_pixel_value

            with tempfile.NamedTemporaryFile() as tmp_file:
                pgm.write_pgm(array=array, bytes_per_sample=bytes_per_sample, output_path=tmp_file.name)
                loaded_array = pgm.read_pgm(input_path=tmp_file.name)
                assert array.shape == loaded_array.shape
                assert (array == loaded_array).all(), (array, '\n', loaded_array)


if __name__ == '__main__':
    unittest.main()
