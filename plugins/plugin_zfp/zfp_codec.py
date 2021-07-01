#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the zfp lossless image coder 
"""

import os
import enb
from enb.config import options


class Zfp(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.WrapperCodec):
    """Wrapper for the zfp codec
    Allowed data type to be compressed: integer 32 & 64 , float 32 & 64
    """

    def __init__(self, zfp_binary=os.path.join(os.path.dirname(__file__), "zfp")):
        """
        param:dtype: valid types in zfp are f32, f64, i32 and i64
        """
        super().__init__(compressor_path=zfp_binary,
                         decompressor_path=zfp_binary,
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
        return "ZFP"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] != 2, 'data type can not be 16 bpp'
        dimensions = 1

        if original_file_info.float == True:
            return f"-i {os.path.abspath(original_path)} " \
                   f"-z {os.path.abspath(compressed_path)} " \
                   f"-t f{original_file_info.bytes_per_sample*8} " \
                   f"-{dimensions} {original_file_info.samples} -R"
        
        if original_file_info.float == False:
            return f"-i {os.path.abspath(original_path)} " \
                   f"-z {os.path.abspath(compressed_path)} " \
                   f"-t i{original_file_info.bytes_per_sample*8} " \
                   f"-{dimensions} {original_file_info.samples} -R"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        dimensions = 1
        # TODO: include {original_file_info.samples} instead of defining a dummy variable (here and everywhere else)
        if original_file_info.float == True:
            return f" -z {os.path.abspath(compressed_path)} " \
                   f"-o {os.path.abspath(reconstructed_path)}  " \
                   f"-t f{original_file_info.bytes_per_sample*8} " \
                   f"-{dimensions} {original_file_info.samples} -R"
        
        if original_file_info.float == False:
            return f" -z {os.path.abspath(compressed_path)} " \
                   f"-o {os.path.abspath(reconstructed_path)}  " \
                   f"-t i{original_file_info.bytes_per_sample*8} " \
                   f"-{dimensions} {original_file_info.samples} -R"


if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    # options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "/data/research-materials/astronomical_data/RAW")
    # TODO: fix this, we are not at Fpack
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
