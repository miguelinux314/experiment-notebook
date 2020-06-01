#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper for the CCSDS 122 (MHDC) codec
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "29/05/2020"

import os
import math
import enb.icompression
from enb.config import get_options

options = get_options()

class MHDC_Abstract(enb.icompression.LosslessCodec, enb.icompression.WrapperCodec):
    """Default values as in Green Book
    """
    def __init__(self, wavelet_2d_type="Integer", bin_dir=None, output_invocation_dir=None):
        """
        :param wavelet_2d_type: "Integer" for lossless 2D DWT, "Float" for lossy 2D DWT
        """
        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=os.path.join(bin_dir, "mhdcEncoder.sh"),
                         decompressor_path=os.path.join(bin_dir, "mhdcDecoder.sh"),
                         output_invocation_dir=output_invocation_dir)
        assert wavelet_2d_type in ["Integer", "Float"]
        self.param_dict["wavelet_2d_type"] = wavelet_2d_type

    def get_transform_params(self, original_file_info):
        """Return a string with the transformation params for each subclass.
        """
        raise NotImplementedError()

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-i {original_path} " \
               f"-x {original_file_info['width']} " \
               f"-y {original_file_info['height']} " \
               f"-z {original_file_info['component_count']} " \
               f"-s {'yes' if original_file_info['signed'] else 'no'} " \
               f"-U {self.param_dict['U'] if 'U' in self.param_dict else 0} " \
               f"-D {self.param_dict['D'] if 'D' in self.param_dict else 0} " \
               f"-R {math.ceil(original_file_info['width']/8)} " \
               f"-S {self.param_dict['S'] if 'S' in self.param_dict else 128} " \
               f"-W {self.param_dict['W'] if 'W' in self.param_dict else 1} " \
               f"-w {self.param_dict['wavelet_2d_type']} " \
               f"-o {compressed_path} " \
               f"{self.get_transform_params(original_file_info=original_file_info)}"
    
    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-i '{compressed_path}' -o '{reconstructed_path}'"

class MHDC_ID(MHDC_Abstract):
    @property
    def label(self):
        return f"CCSDS-122"

    def get_transform_params(self, original_file_info):
        return f"-t id"

class MHDC_POT(MHDC_Abstract):
    def __init__(self, bin_dir=None, output_invocation_dir=None,
                 F=32, Omega=12):
        super().__init__(bin_dir=bin_dir, output_invocation_dir=output_invocation_dir)
        self.param_dict["F"] = F
        self.param_dict["Omega"] = Omega

    @property
    def label(self):
        return f"CCSDS-122-POT"

    def get_transform_params(self, original_file_info):
        return f"-t pot -F {self.param_dict['F']} -O {self.param_dict['Omega']}"


class MHDC_IWT(MHDC_Abstract):
    def __init__(self, bin_dir=None, output_invocation_dir=None):
        super().__init__(bin_dir=bin_dir, output_invocation_dir=output_invocation_dir)

    @property
    def label(self):
        return f"CCSDS-122-IWT"

    def get_transform_params(self, original_file_info):
        return f"-t iwt"
