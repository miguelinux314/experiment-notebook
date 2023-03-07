#!/usr/bin/env python3
"""Unit tests for isets.py
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/07"

import unittest
import tempfile
import os
import numpy as np

import test_all
from enb import isets


class TestiSets(unittest.TestCase):

    def test_array_load_dump(self):
        """Test that loading and dumping of numpy arrays
        indexed by [x,y,z] is correctly performed.
        """
        width = 4
        height = 2
        component_count = 3

        for order in ["bsq", "bip", "bil"]:
            for is_float in [True, False]:
                bytes_per_sample_values = [2, 4, 8] if is_float else [1, 2, 4, 8]
                for bytes_per_sample in bytes_per_sample_values:
                    for signed in [True, False]:
                        value_factors = [1] if not signed else [1, -1]
                        for value_factor in value_factors:
                            big_endian_values = [True] if (bytes_per_sample == 1 or is_float) \
                                else [True, False]
                            for big_endian in big_endian_values:
                                self.run_one_case(big_endian, bytes_per_sample,
                                                  component_count, height,
                                                  is_float, order, signed,
                                                  value_factor, width)

    def run_one_case(self, big_endian, bytes_per_sample, component_count,
                     height, is_float, order, signed, value_factor, width):
        row = dict(
            width=width, height=height, component_count=component_count,
            float=is_float,
            signed=signed, bytes_per_sample=bytes_per_sample,
            big_endian=big_endian)
        array = np.zeros((width, height, component_count),
                         dtype=isets.iproperties_row_to_numpy_dtype(row))
        i = 0
        for z in range(component_count):
            for y in range(height):
                for x in range(width):
                    array[x, y, z] = i * value_factor
                    i += 1
        fd, temp_file_path = tempfile.mkstemp(
            suffix=f"_{isets.iproperties_row_to_sample_type_tag(row)}.raw")
        try:
            dtype_string = isets.iproperties_row_to_numpy_dtype(row)
            isets.dump_array(array, temp_file_path, mode="wb",
                             dtype=dtype_string, order=order)
            loaded_array = isets.load_array(
                file_or_path=temp_file_path,
                image_properties_row=row,
                order=order)
            assert (array == loaded_array).all(), (array, loaded_array)
            assert os.path.getsize(temp_file_path) \
                   == width * height * component_count * bytes_per_sample
        finally:
            try:
                os.remove(temp_file_path)
                os.close(fd)
            except OSError:
                pass


if __name__ == '__main__':
    unittest.main()
