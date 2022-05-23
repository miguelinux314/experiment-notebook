#!/usr/bin/env python3
"""Codec wrapper for the Zstandard lossless image coder
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/07/12"

import os
import enb
from enb import tarlite
import tempfile
from enb.config import options
import glob

class Zstandard(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the Zstandard codec
    All data types integer and float 16, 32, 64 can be compressed
    """

    def __init__(self, compression_level='19', zstd_binary=os.path.join(os.path.dirname(__file__), "zstd")):
        """
        :param compression_level: 1-19, being 19 the maximum data reduction
        """
        super().__init__(compressor_path=zstd_binary,
                         decompressor_path=zstd_binary,
                         param_dict=dict(compression_level=compression_level))

    @property
    def label(self):
        return "Zstandard"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-{self.param_dict['compression_level']} -f {original_path}  -o {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-d  -f {compressed_path} -o {reconstructed_path}"


class Zstandard_train(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.FITSWrapperCodec):
    """Wrapper for the Zstandard codec
    All data types integer and float 16, 32, 64 can be compressed
    """
    def __init__(self, compression_level='19', zstd_binary=os.path.join(os.path.dirname(__file__), "zstd")):
        """
        :param compression_level: 1-19, being 19 the maximum data reduction
        """
        super().__init__(compressor_path=zstd_binary,
                         decompressor_path=zstd_binary,
                         param_dict=dict(compression_level=compression_level))
    '''
    def get_compression_params(self, original_path, compressed_path, original_file_info):
        """Return a string (shell style) with the parameters
        to be passed to the compressor.
        Same parameter semantics as :meth:`AbstractCodec.compress`.
        :param original_file_info: a dict-like object describing original_path's properties
          (e.g., geometry), or None
        """
        raise NotImplementedError()
    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        """Return a string (shell style) with the parameters
        to be passed to the decompressor.
        Same parameter semantics as :meth:`AbstractCodec.decompress()`.
        :param original_file_info: a dict-like object describing original_path's properties
          (e.g., geometry), or None
        """
        raise NotImplementedError()
    '''
    def compress(self, original_path, compressed_path, original_file_info):
        print('FILES', original_path, compressed_path)
        os.system(f" {self.compressor_path} --train {original_path} --optimize-cover -o {os.path.join(os.path.dirname(__file__), 'dict.zstd')}")
        os.system(f" {self.compressor_path} --ultra -{self.param_dict['compression_level']}  -D {os.path.join(os.path.dirname(__file__), 'dict.zstd')}  -f {original_path}  -o {os.path.join(os.path.dirname(__file__), 'compressed_trained_path.zstd')}")
        input_paths=[os.path.join(os.path.dirname(__file__), 'dict.zstd'), os.path.join(os.path.dirname(__file__), 'compressed_trained_path.zstd')]

        tarlite.tarlite_files(input_paths=input_paths, output_tarlite_path=compressed_path)

    def decompress(self, compressed_path, reconstructed_path, original_file_info):
        tr = tarlite.untarlite_files(input_tarlite_path=compressed_path, output_dir_path=os.path.dirname(__file__))
        os.system(f"{self.compressor_path} -d -D {os.path.join(os.path.dirname(__file__), 'dict.zstd')}  -f {os.path.join(os.path.dirname(__file__), 'compressed_trained_path.zstd')} -o {reconstructed_path}")
