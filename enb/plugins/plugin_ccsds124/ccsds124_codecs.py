#!/usr/bin/env python3
"""Wrappers for the CCSDS 124.0-B-1 codecs.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/11/09"

import os
import re

import enb.log
from enb import icompression


class CCSDS124_Periodic(icompression.LosslessCodec, icompression.WrapperCodec):
    default_r_period = 0
    default_p_period = 10
    default_large_r = 0

    def __init__(self, r_period=0, p_period=10, f_period=0, large_r=0):
        """
        Initialize a CCSDS 124.0-B-1 codec.
        :param r_period: period with which reference packets are sent. 0 for sending them only when necessary.
        :param p_period: period with which the mask is updated. 0 for no updates.
        :param f_period: period with which the full mask is sent. 0 for sending it only when necessary.
        :param large_r: robustness level R.
        """
        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "ccsds124_encoder_periodic"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "ccsds124_decoder"))
        assert r_period >= 0
        assert p_period >= 0
        assert f_period >= 0
        assert 0 <= large_r <= 7
        self.param_dict["r_period"] = r_period
        self.param_dict["p_period"] = p_period
        self.param_dict["f_period"] = f_period
        self.param_dict["large_r"] = large_r

    @property
    def label(self):
        return f"CCSDS 124 " \
               f"$R={self.param_dict['large_r']}$ " \
               f"$T_r={self.param_dict['r_period']}$ " \
               f"$T_p={self.param_dict['p_period']}$ " \
               f"$T_f={self.param_dict['f_period']}$"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        try:
            packet_length_bits = original_file_info["packet_length_bits"]
        except KeyError:
            try:
                packet_length_bits = 8 * int(re.search(r"FL(\d+)bytes", os.path.basename(original_path)).group(1))
            except AttributeError:
                packet_length_bits = 8 * original_file_info["bytes_per_sample"]
                enb.log.warn(f"Unable to determine the packet length in bits for {original_path} with {self}. "
                             f"Falling back to 8*bytes_per_sample = {packet_length_bits}")

        return f"-p {self.param_dict['p_period']} " \
               f"-r {self.param_dict['r_period']} " \
               f"-f {self.param_dict['f_period']} " \
               f"-R {self.param_dict['large_r']} " \
               f"{original_path} {packet_length_bits} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} " \
               f"{reconstructed_path} " \
               f"{reconstructed_path}.packet_length"
