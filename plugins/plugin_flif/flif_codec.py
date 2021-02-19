#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the FLIF lossless image coder (precursor of JPEG-LS
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "09/02/2021"

import os
import time
import tempfile
import subprocess
import imageio
import numpy as np
import enb

class FLIF(enb.icompression.LosslessCodec, enb.icompression.PNGWrapperCodec):
    def __init__(self, flif_binary=os.path.join(os.path.dirname(__file__), "flif")):
        super().__init__(compressor_path=flif_binary, decompressor_path=flif_binary)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 1, f"This implementation of FLIF supports only 8-bit images"
        return f"-e --overwrite {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-d --overwrite {compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return "FLIF"