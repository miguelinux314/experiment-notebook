#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the tarlite module
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "08/04/2020"

import os
import glob
import tempfile
import filecmp
import unittest

__file__ = os.path.abspath(__file__)
import test_all

import enb.tarlite as tarlite


class TestTarlite(unittest.TestCase):
    def test_read_write(self):
        with tempfile.NamedTemporaryFile() as tmp_tarlite_file:
            input_paths = glob.glob(os.path.join(os.path.abspath(os.path.dirname(__file__)), "*.py"))
            tw = tarlite.TarliteWriter(initial_input_paths=input_paths)
            tw.write(output_path=tmp_tarlite_file.name)

            tr = tarlite.TarliteReader(tarlite_path=tmp_tarlite_file.name)
            with tempfile.TemporaryDirectory() as tmp_extract_dir:
                tr.extract_all(output_dir_path=tmp_extract_dir)

                for input_path in input_paths:
                    check_path = os.path.join(tmp_extract_dir, os.path.basename(input_path))
                    assert filecmp.cmp(input_path, check_path)


if __name__ == '__main__':
    unittest.main()
