#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for isets.py
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "07/04/2020"

import unittest
import tempfile
import glob
import os
import numpy as np
import shutil
import subprocess

import test_all
from enb import isets


class TestiSets(unittest.TestCase):

    def test_array_load_dump(self):
        """Test that file properties are correctly obtained and retrieved.
        """
        width = 4
        height = 2
        component_count = 3

        for bytes_per_sample in [1, 2, 4]:
            for signed in [True, False]:
                value_factors = [1] if not signed else [1, -1]
                for value_factor in value_factors:
                    big_endian_values = [True] if bytes_per_sample == 1 else [True, False]
                    for big_endian in big_endian_values:
                        row = dict(
                            width=width, height=height, component_count=component_count,
                            signed=signed, bytes_per_sample=bytes_per_sample, big_endian=big_endian)

                        array = np.zeros((width, height, component_count),
                                         dtype=isets.iproperties_row_to_numpy_dtype(row))
                        i = 0
                        for z in range(component_count):
                            for y in range(height):
                                for x in range(width):
                                    array[x, y, z] = i * value_factor
                                    i += 1

                        _, temp_file_path = tempfile.mkstemp(
                            suffix=f"_{isets.iproperties_row_to_sample_type_tag(row)}.raw")
                        try:
                            isets.dump_array_bsq(array, temp_file_path, mode="wb",
                                                 dtype=isets.iproperties_row_to_numpy_dtype(row))
                            loaded_array = isets.load_array_bsq(file_or_path=temp_file_path,
                                                                image_properties_row=row)
                            assert (array == loaded_array).all(), (array, loaded_array)
                        finally:
                            try:
                                os.remove(temp_file_path)
                            except OSError:
                                pass


if __name__ == '__main__':
    unittest.main()
