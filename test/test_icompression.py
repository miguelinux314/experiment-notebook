#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the icompression module
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "6/4/2020"

import unittest
import tempfile
import subprocess
import glob
import os
import sys
import numpy as np
import shutil

import test_all
from enb import icompression
from enb import isets
from enb.config import get_options

options = get_options()


class ConstantOutputCodec(icompression.LosslessCodec):
    """Codec that reconstructs an image with the same geometry
    but all pixels identical to a constant provided at initialization
    time
    """

    def __init__(self, reconstruct_value):
        """
        :param reconstruct_value: value that all pixels of
          the reconstructed images have.
        """
        super().__init__()
        self.reconstruct_value = reconstruct_value

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        dt = isets.iproperties_row_to_numpy_dtype(image_properties_row=original_file_info)
        a = np.full((original_file_info["width"],
                     original_file_info["height"],
                     original_file_info["component_count"]),
                    fill_value=self.reconstruct_value, dtype=dt)
        isets.dump_array_bsq(array=a, file_or_path=reconstructed_path)

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        shutil.copyfile(original_path, compressed_path)


class TestIcompression(unittest.TestCase):

    def test_mse_pae(self):
        """Test MSE and PAE calculation for simple images
        for all supported data types.
        """
        width = 37
        height = 64
        component_count = 7
        original_constant = 10

        for signed in [True, False]:
            for bytes_per_sample in [1, 2, 4]:
                for big_endian in [True, False]:
                    if bytes_per_sample == 1 and not big_endian:
                        continue
                    dtype = ((">" if big_endian else "<") if bytes_per_sample > 1 else "") \
                            + ("i" if signed else "u") \
                            + str(bytes_per_sample)
                    sample_tag = ("s" if signed else "u") \
                                 + str(8 * bytes_per_sample) \
                                 + ("be" if big_endian else "le")

                    fill_values = [original_constant] if not signed else [-original_constant, original_constant]
                    for fill_value in fill_values:
                        array = np.full((width, height, component_count),
                                        fill_value=fill_value, dtype=dtype)
                        for error in [-3, 3]:
                            with tempfile.TemporaryDirectory() as tmp_dir, \
                                    tempfile.TemporaryDirectory() as persistence_dir, \
                                    tempfile.NamedTemporaryFile(
                                        dir=tmp_dir,
                                        suffix=f"-{component_count}x{height}x{width}_{sample_tag}.raw") as tmp_file:
                                isets.dump_array_bsq(array=array, file_or_path=tmp_file.name)

                                coc = ConstantOutputCodec(reconstruct_value=fill_value + error)
                                options.persistence_dir = persistence_dir
                                ce = icompression.LossyCompressionExperiment(
                                    codecs=[coc],
                                    dataset_paths=[tmp_file.name],
                                )
                                df = ce.get_df()
                                assert (df["pae"] == abs(error)).all(), \
                                    (df["pae"], abs(error))
                                assert (np.abs(df["mse"] - error ** 2) < (2 * sys.float_info.epsilon)).all(), \
                                    (df["mse"], abs(error))


if __name__ == '__main__':
    unittest.main()
