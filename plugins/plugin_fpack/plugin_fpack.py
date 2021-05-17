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



class ImageFpack(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the imageMarlin codec
    """
    def __init__(self,
                 compression_method='-r',
                 fpack_binary=os.path.join(os.path.dirname(__file__), "fpack")):
        super().__init__(compressor_path=fpack_binary,
                         decompressor_path=fpack_binary.replace("fpack", "funpack"),
                         param_dict=dict(compression_method=compression_method)) 
        self.fpack_binary = fpack_binary

        assert os.path.isfile(fpack_binary)

    @property
    def name(self):
        """Don't include the binary signature
        """
        name = f"{self.__class__.__name__}"

    @property
    def label(self):
        return "fpack"

    def get_compression_params(self, original_path, compressed_path, original_file_info):

        return f"fpack -{self.param_dict['compression_method']}   " \
               f"-O {compressed_path} {original_path}  "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"funpack -O {reconstructed_path} {compressed_path} "
