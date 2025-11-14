#!/usr/bin/env python3
"""Wrapper for the JPEG-XL reference implementation
"""
__author__ = ("Ashwin Kumar Gururajan <ashwin.gururajan@uab.cat>, "
              "Xavier Fernández-Mellado, "
              "Miguel Hernández-Cabronero <miguel.hernandez@uab.cat>")
__since__ = "2021/02/15"

import os
import enb


class JPEG_XL(enb.icompression.LosslessCodec,
              enb.icompression.LossyCodec,
              enb.compression.pgm.PAMWrapperCodec):
    def __init__(self, quality_0_to_100=100, compression_level=7, threads=0,
                 lossless=True,
                 compressor_path=os.path.join(os.path.dirname(__file__), "cjxl"),
                 decompressor_path=os.path.join(os.path.dirname(__file__), "djxl")):
        """
        :param quality_0_to_100: Quality setting. Range: -inf .. 100.
        100 = mathematically lossless. Default for already-lossy input (JPEG/GIF).
        Positive quality values roughly match libjpeg quality.
        Uses jpeg_xl parameter -q and was chosen over -d maxError
        (defined by butteraugli distance) becuase of slightly better throughput
        (approx 1.2 Mp/s) under lossless mode
        :param compression_level: higher values mean slower compression
        :param lossless: if True, the modular mode of JPEG-XL is employed (in this case quality 100 is required)
        :param threads: -1 use machine default, 0 do not use multithreading, >1 select number of threads
        """
        assert 3 <= compression_level <= 9
        assert -1 <= threads
        assert 0 <= quality_0_to_100 <= 100
        assert (not lossless) or quality_0_to_100 == 100, f"Lossless mode can only be employed with quality 100"

        enb.compression.pgm.PAMWrapperCodec.__init__(
            self, compressor_path=compressor_path, decompressor_path=decompressor_path,
            param_dict=dict(
                quality_0_to_100=quality_0_to_100,
                compression_level=compression_level,
                lossless=lossless,
                threads=threads),
            output_invocation_dir=None)
        self.compressor_path = os.path.abspath(self.compressor_path)
        self.decompressor_path = os.path.abspath(self.decompressor_path)

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        try:
            component_count = original_file_info["component_count"]
        except KeyError:
            component_count = file_path_to_geometry_dict(original_path)["component_count"]
        assert component_count in (1, 3), \
            "JPEG XL only supports 1 and 3 component images."

        ap_original_path = os.path.abspath(original_path)
        ap_compressed_path = os.path.abspath(compressed_path)
        previous_cwd = os.getcwd()
        os.chdir(os.path.dirname(self.compressor_path))
        super().compress(ap_original_path, ap_compressed_path, original_file_info)
        os.chdir(previous_cwd)

    def decompress(self, compressed_path: str, reconstructed_path: str, original_file_info=None):
        ap_compressed_path = os.path.abspath(compressed_path)
        ap_reconstructed_path = os.path.abspath(reconstructed_path)
        previous_cwd = os.getcwd()
        os.chdir(os.path.dirname(self.decompressor_path))
        super().decompress(ap_compressed_path, ap_reconstructed_path, original_file_info)
        os.chdir(previous_cwd)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are supported by {self.__class__.__name__}"

        return f"{original_path} {compressed_path} " \
               f"-q {self.param_dict['quality_0_to_100']} " \
               f"-e {self.param_dict['compression_level']} " \
               f"--num_threads={self.param_dict['threads']} " \
               f"--quiet"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return f"JPEG XL"
