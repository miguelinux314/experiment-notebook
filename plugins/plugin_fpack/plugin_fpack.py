#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the FLIF lossless image coder (precursor of JPEG-LS
"""

import os
import time
import tempfile
import subprocess
import imageio
import shutil
import numpy as np
import enb



class Fpack(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the imageMarlin codec
    """
    def __init__(self,
                 bin_dir=None,
                 compression_method='r'):
                 
        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=os.path.join(bin_dir, "fpack"),
                         decompressor_path=os.path.join(bin_dir, "funpack"),
                         param_dict=dict(compression_method=compression_method)) 

    @property
    def name(self):
        """Don't include the binary signature
        """
        name = f"{self.__class__.__name__}"
        return name

    @property
    def label(self):
        return "fpack"

    def get_compression_params(self, original_path, compressed_path, original_file_info):

        return f" -{self.param_dict['compression_method']}   " \
               f"-O {compressed_path} {original_path}  "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" -O {reconstructed_path} {compressed_path} "
