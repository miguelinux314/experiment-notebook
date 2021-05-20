#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the FLIF lossless image coder (precursor of JPEG-LS
"""

import os
import enb
from enb.config import options
from astropy.io import fits

# TODO: document the new class: at the very least, the compression_method parameter

class Fpzip(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the fpzip codec
    """
    
    def __init__(self, fpzip_binary=os.path.join(os.path.dirname(__file__), "fpzip")):

        super().__init__(compressor_path=fpzip_binary,
                         decompressor_path=fpzip_binary,
                         param_dict=dict())    
    
    @property
    def name(self):
        """Don't include the binary signature
        """
        name = f"{self.__class__.__name__}{'__' if self.param_dict else ''}" \
               f"{'_'.join(f'{k}={v}' for k, v in self.param_dict.items())}"
        return name

    @property
    def label(self):
        return "fpzip"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        hdul=fits.open(original_path)
        hdr = hdul[0].header
        
        dimensions = hdr['NAXIS']
        x = hdr['NAXIS1']
        y = hdr['NAXIS2']
        z = hdr['NAXIS3']
        print(dimensions,x,y,z)
        print(f"-i {original_path}  -o {compressed_path} -{dimensions} {x} {y} {z} ")
        return f"-i {original_path}  -o {compressed_path}" \
               f"-{dimensions} {x} {y} {z} "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-d -i {compressed_path} -o {reconstructed_path} " \
            f"-{dimensions} {x} {y} {z}  "


if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    #options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "/data/research-materials/astronomical_data/RAW")
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
