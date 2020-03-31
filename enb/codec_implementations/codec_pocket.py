#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrappers for POCKET+ implementations
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "23/09/2019"

import os
import subprocess

import codec
import config


class PocketPlusCWE_Aug2019(codec.LosslessCodec, codec.WrapperCodec):
    """Wrapper for the POCKET+ demo made available at CCSDS CWE.

    - It produces 'compressed_data.bin' at cwd, no matter what.
    - Arguments are read from stdin in lines
        <file path>\n<update rate 5..20>\n<window in 1..4>
    """
    default_compressor_path = os.path.join(
        config.options.external_bin_base_dir, "pocket_plus_cwe_aug2019", "compression_pocket_plus_cwe_aug2019")
    default_decompressor_path = os.path.join(
        config.options.external_bin_base_dir, "pocket_plus_cwe_aug2019", "decompression_pocket_plus_cwe_aug2019")

    def __init__(self, positive_update_rate=5, window=None):
        """
        :param positive_update_rate: positive update rate to use for all inputs
        :param window: if not None, window size to be used for all files. Otherwise, the window
          equals the fixed-length packet size
        """
        assert window is None or window == int(window), window
        assert window is None or 1 <= window <= 4, window
        assert positive_update_rate == int(positive_update_rate), positive_update_rate
        assert 3 <= positive_update_rate <= 200, positive_update_rate
        self.positive_update_rate = positive_update_rate
        self.window = window

        assert os.path.exists(self.default_compressor_path + ".sh")
        assert os.path.exists(self.default_decompressor_path + ".sh")
        super().__init__(compressor_path=self.default_compressor_path,
                         decompressor_path=self.default_decompressor_path,
                         param_dict=dict(pur=positive_update_rate, window=window))

    @property
    def name(self):
        """Name of the codec. Subclasses are expected to yield different values
        when different parameters are used. By default, the class name is folled
        by all elements in self.param_dict sorted alphabetically are included
        in the name."""
        name = f"{self.__class__.__name__}"
        if self.param_dict:
            name += "__" + "_".join(f"{k}={v}" for k, v in sorted(self.param_dict.items())
                                    if k != "window" or v is not None)
        return name

    @property
    def label(self):
        return f"POCKET+ T$_{{pur}}$={self.positive_update_rate:04d}"

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        """Compress using the bash wrapper and a temporary dir
        """
        if self.window is not None:
            window = self.window
        elif original_file_info is not None:
            window = original_file_info["bytes_per_sample"]
        else:
            raise codec.CompressionException(
                original_path=original_path, compressed_path=compressed_path,
                file_info=original_file_info, status=-1,
                output=f"self.window = {self.window} but original_file_info = {original_file_info}")

        status, output = subprocess.getstatusoutput(
            f"{self.compressor_path}.sh "
            f"'{os.path.abspath(original_path)}' "
            f"'{os.path.abspath(compressed_path)}' "
            f"{self.positive_update_rate} "
            f"{window}")
        if status != 0 or not os.path.getsize(compressed_path):
            raise codec.CompressionException(
                original_path=original_path, compressed_path=compressed_path,
                file_info=original_file_info, status=status, output=output)

    def decompress(self, compressed_path, reconstructed_path, original_file_info: codec.FileInfo = None):
        """Decompress using the bash wrapper and a temporary dir
        """
        window = self.window if self.window is not None \
            else original_file_info["bytes_per_sample"]

        status, output = subprocess.getstatusoutput(
            f"{self.decompressor_path}.sh "
            f"'{os.path.abspath(compressed_path)}' "
            f"'{os.path.abspath(reconstructed_path)}' "
            f"{window}")
        if status != 0 or not os.path.getsize(reconstructed_path):
            raise codec.DecompressionException(
                compressed_path=compressed_path, reconstructed_path=reconstructed_path,
                file_info=original_file_info, status=status, output=output)


if __name__ == "__main__":
    print("Non executable module")
