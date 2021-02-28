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
import shutil
import numpy as np
import enb


class ImageMarlin(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.PNGWrapperCodec):
    """Wrapper for the imageMarlin codec
    """
    def __init__(self,
                 qstep=1,
                 entfreq=1,
                 marlin_binary=os.path.join(os.path.dirname(__file__), "imageMarlin")):
        super().__init__(compressor_path=marlin_binary,
                         decompressor_path=marlin_binary,
                         param_dict=dict(qstep=qstep, entfreq=entfreq))
        self.marlin_binary = marlin_binary
        assert qstep >= 1
        assert int(qstep) == qstep
        assert os.path.isfile(marlin_binary)

    @property
    def name(self):
        """Don't include the binary signature
        """
        name = f"{self.__class__.__name__}"
        if self.param_dict:
            name += "__" + "_".join(f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name

    @property
    def label(self):
        return "ImageMarlin"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 1, f"ImageMarlin supports monocomponent 8-bit images only"

        return f"c {original_path} {compressed_path} " \
               f"-qstep={self.param_dict['qstep']} " \
               f"-entfreq={self.param_dict['entfreq']} "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"d {compressed_path} {reconstructed_path}"
