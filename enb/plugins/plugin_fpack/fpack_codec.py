#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the Fpack lossless and lossy image coder 
"""

import os
import time
import tempfile
import subprocess
import imageio
import shutil
import numpy as np
import enb


class FPACK_GZIP(enb.icompression.LosslessCodec, enb.icompression.FITSWrapperCodec):

    def __init__(self,
                 bin_dir=None):

        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=os.path.join(bin_dir, "fpack"),
                         decompressor_path=os.path.join(bin_dir, "funpack"),
                         param_dict=dict())

    @property
    def name(self):
        """Don't include the binary signature
        """
        return f"{self.__class__.__name__}{'__' if self.param_dict else ''}" \
               f"{'_'.join(f'{k}={v}' for k, v in self.param_dict.items())}"

    @property
    def label(self):
        return "FPACK - GZIP"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f" -q 0 -s 0 -g   -O {compressed_path} {original_path}" 
        
    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" -O {reconstructed_path} {compressed_path} "
 
 
class FPACK_RICE(enb.icompression.LosslessCodec, enb.icompression.FITSWrapperCodec):
    def __init__(self,
                 bin_dir=None):

        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=os.path.join(bin_dir, "fpack"),
                         decompressor_path=os.path.join(bin_dir, "funpack"),
                         param_dict=dict())

    @property
    def name(self):
        """Don't include the binary signature
        """
        return f"{self.__class__.__name__}{'__' if self.param_dict else ''}" \
               f"{'_'.join(f'{k}={v}' for k, v in self.param_dict.items())}"

    @property
    def label(self):
        return "FPACK - RICE"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f" -r  -O {compressed_path} {original_path}" 
        
    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" -O {reconstructed_path} {compressed_path} "
            
            
class FPACK_HCOMPRESS(enb.icompression.LosslessCodec, enb.icompression.FITSWrapperCodec):
    def __init__(self,
                 bin_dir=None):

        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=os.path.join(bin_dir, "fpack"),
                         decompressor_path=os.path.join(bin_dir, "funpack"),
                         param_dict=dict())

    @property
    def name(self):
        """Don't include the binary signature
        """
        return f"{self.__class__.__name__}{'__' if self.param_dict else ''}" \
               f"{'_'.join(f'{k}={v}' for k, v in self.param_dict.items())}"

    @property
    def label(self):
        return "FPACK - HCOMPRESS"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f" -h  -O {compressed_path} {original_path}" 
        
    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" -O {reconstructed_path} {compressed_path} "

