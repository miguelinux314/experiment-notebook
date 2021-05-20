#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the FLIF lossless image coder (precursor of JPEG-LS
"""

import os
import enb
from enb.config import options


# TODO: document the new class: at the very least, the compression_method parameter

class Fpack(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the fpack codec
    """

    def __init__(self, bin_dir=None, compression_method='r'):
        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(os.path.abspath(__file__))
        super().__init__(compressor_path=os.path.join(bin_dir, "fpack"),
                         decompressor_path=os.path.join(bin_dir, "funpack"),
                         param_dict=dict(compression_method=compression_method))

    @property
    def name(self):
        """Don't include the binary signature
        """
        name = f"{self.__class__.__name__}{'__' if self.param_dict else ''}" \
               f"{'_'.join(f'{k}={v}' for k, v in self.param_dict.items())}"
        return name

    @property
    def label(self):
        return "fpack"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-{self.param_dict['compression_method']} " \
               f"-O {compressed_path} {original_path}  "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-O {reconstructed_path} {compressed_path}"


if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    exp = enb.icompression.LossyCompressionExperiment(codecs=[Fpack()])
    # df = exp.get_df()
    # print(f"[watch] len(df)={len(df)}")
    
