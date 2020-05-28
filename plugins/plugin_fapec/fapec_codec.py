#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrappers for the FAPEC codec
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "25/05/2020"

import os

from enb import icompression
from enb.config import get_options

options = get_options()


class FAPEC_NP(icompression.LossyCodec, icompression.LosslessCodec, icompression.WrapperCodec):
    """Wrapper for FAPEC with no preprocessing (-np option).
    """
    BAND_FORMAT_BIP, BAND_FORMAT_BIL, BAND_FORMAT_BSQ, BAND_FORMAT_BAYER = range(4)
    default_band_format = BAND_FORMAT_BSQ

    def __init__(self, bin_dir=None, chunk_size_str="64M", threads=1,
                 lsb_discard_count=0,
                 adaptiveness_block_length=64,
                 output_invocation_dir=None):
        """
        :param bin_dir:
        :param chunk_size_str:
        :param threads:
        :param prediction_band_count: number of bands used for multi-component prediction
        :param lsb_discard_count:  number of LSBs discarded
        :param adaptiveness_block_length:
        """
        param_dict = dict()
        param_dict["chunk"] = chunk_size_str
        assert lsb_discard_count >= 0
        if lsb_discard_count > 0:
            param_dict["lossy"] = lsb_discard_count
        assert threads >= 0
        param_dict["mt"] = threads
        assert 32 <= adaptiveness_block_length <= 1024
        param_dict["bl"] = adaptiveness_block_length

        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=os.path.join(bin_dir, "fapec"),
                         decompressor_path=os.path.join(bin_dir, "unfapec"),
                         param_dict=param_dict, output_invocation_dir=output_invocation_dir)

    def get_dtype(self, original_file_info):
        return 8 * original_file_info["bytes_per_sample"]

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        """Get the dictionary of parameters to use in the -x k=v options of lcnl_header_tool.
        """
        invocation_params = dict(self.param_dict)
        invocation_params.update(
            hd=0, chd=0,
            dtype=self.get_dtype(original_file_info=original_file_info),
            np=("tc" if original_file_info["signed"] else "us"))
        invocation = " ".join(f"-{k} {v}" for k, v in invocation_params.items())
        if original_file_info["signed"]:
            invocation += " -signed"
        if original_file_info["big_endian"]:
            invocation += " -be"
        invocation += " -ow -noattr "
        invocation += f"-o {compressed_path} {original_path}"
        return invocation

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        invocation = f"-o {reconstructed_path} -ow {compressed_path}"
        return invocation
