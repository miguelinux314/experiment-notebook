#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the fpzip lossless image coder
"""

import os
import enb
from enb.config import options


class Fpzip(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.WrapperCodec):
    """Wrapper for the fpzip codec
    Allowed data type to be compressed: float 32
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
        return "FPZIP"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 4 and original_file_info["float"] == True,'data type must be float 32'
        dimensions = 1

        return f"-i {os.path.abspath(original_path)} " \
               f" -o {os.path.abspath(compressed_path)} " \
               f"-{dimensions} {original_file_info.samples} "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        dimensions = 1

        return f"-d -i {compressed_path} -o {reconstructed_path} -{dimensions} {original_file_info.samples} "


if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    # options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "/data/research-materials/astronomical_data/RAW")
    exp = enb.icompression.LossyCompressionExperiment(codecs=[Fpzip()])

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
