#!/usr/bin/env python3
"""Codec wrapper for the Fpack lossless and lossy image coder 
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2021/07/01"

import os
import enb


class Fpack(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the imageMarlin codec.
    """

    def __init__(self,
                 bin_dir=None,
                 quantization=0,
                 scale=0,
                 compression_method='r'):
        """
        :param bin_dir: path to the dir with the fapec and unfapec binaries
        :param compression method: compression method used (r - Rice, h - Hcompress,
        p - PLIO, g - Gzip or i2f - converts integer to floats and uses Rice compression )
        :param quanization: quantization level
        :param scale: Scale factor for lossy compression when using Hcompress        
        """

        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=os.path.join(bin_dir, "fpack"),
                         decompressor_path=os.path.join(bin_dir, "funpack"),
                         param_dict=dict(compression_method=compression_method, quantization=quantization, scale=scale))

    @property
    def name(self):
        """Don't include the binary signature
        """
        return f"{self.__class__.__name__}{'__' if self.param_dict else ''}" \
               f"{'_'.join(f'{k}={v}' for k, v in self.param_dict.items())}"

    @property
    def label(self):
        return "FPACK"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f" -{self.param_dict['compression_method']} " + \
               (f" -q {self.param_dict['quantization']} " if self.param_dict["compression_method"] == "g" else " ") + \
               f" -s {self.param_dict['scale']} " \
               f" -O {compressed_path} {original_path} "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" -O {reconstructed_path} {compressed_path} "
