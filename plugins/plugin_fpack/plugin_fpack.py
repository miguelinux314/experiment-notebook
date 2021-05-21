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



class Fpack(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the imageMarlin codec
    """
    def __init__(self,
                 bin_dir=None,
                 quantization =0,
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
        name = f"{self.__class__.__name__}"
        return name

    @property
    def label(self):
        return "fpack"

    def get_compression_params(self, original_path, compressed_path, original_file_info):

        return f" -{self.param_dict['compression_method']}   " \
               f" -q {self.param_dict['quantization']} -s {self.param_dict['scale']}" \
               f"-O {compressed_path} {original_path}  "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" -O {reconstructed_path} {compressed_path} "
    
if __name__ == '__main__':
    # options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "/data/research-materials/astronomical_data/RAW")
    exp = enb.icompression.LossyCompressionExperiment(codecs=[Fpack()])

    df = exp.get_df()

    enb.aanalysis.ScalarDistributionAnalyzer().analyze_df(
        full_df=df,
        column_to_properties=exp.column_to_properties,
        target_columns=["bpppc", "compression_ratio"],
        group_by="corpus", show_global=True)

    enb.aanalysis.TwoColumnScatterAnalyzer().analyze_df(
        full_df=df,
        column_to_properties=exp.column_to_properties,
        target_columns=[("bpppc", "mse")])
