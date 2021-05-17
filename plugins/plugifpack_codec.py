#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the FPACK lossless image coder """

import os
import time
import tempfile
import subprocess
import imageio
import shutil
import numpy as np
import enb
import icompression

class ImageFpack(enb.icompression.LosslessCodec,  icompression.FITSWrapperCodec):
    """Wrapper for the imageFpack codec
    """
    def __init__(self,
                 #bin_dir=None,
                 compression_method='-r',
                 fpack_binary=os.path.join(os.path.dirname(__file__), "fpack")):
        #bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=fpack_binary,
                         #compressor_path=os.path.join(bin_dir, "fpack"),
                         decompressor_path=fpack_binary.replace("fpack", "funpack"),
                         #decompressor_path=os.path.join(bin_dir, "funpack"),
                         param_dict=dict(compression_method=compression_method)) 
                         #in latter version add: quantization and dithering

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
        return "ImageFpack"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        #assert original_file_info["bytes_per_sample"] == 1, f"ImageFpck supports monocomponent 8-bit images only"

        return f"fpack -{self.param_dict['compression_method']}   " \
               f"-O {compressed_path} {original_path}  "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"funpack -O {reconstructed_path} {compressed_path} "
