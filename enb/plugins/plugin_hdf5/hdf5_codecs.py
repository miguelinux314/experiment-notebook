#!/usr/bin/env python3
"""Codec wrapper for the HDF5 lossless image coder
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import numpy as np
import enb
import h5py


class AbstractHdf5Codec(enb.icompression.LosslessCodec):
    MIN_COMPRESSION_LEVEL = 1
    MAX_COMPRESSION_LEVEL = 9
    DEFAULT_COMPRESSION_LEVEL = 5

    def __init__(self, compression_level=DEFAULT_COMPRESSION_LEVEL, param_dict=None):
        assert self.MIN_COMPRESSION_LEVEL <= compression_level <= self.MAX_COMPRESSION_LEVEL
        param_dict = dict() if param_dict is None else param_dict
        param_dict["compression_level"] = compression_level
        super().__init__(param_dict=param_dict)


class GZIP(AbstractHdf5Codec):
    """Apply the Gzip algorithm and Huffman coding to the file using zlib.
    """

    def compress(self, original_path, compressed_path, original_file_info):
        with h5py.File(compressed_path, "w") as compressed_file:
            array = enb.isets.load_array_bsq(
                file_or_path=original_path, image_properties_row=original_file_info)
            compressed_file.create_dataset('dataset_1', data=array, compression='gzip',
                                           compression_opts=self.param_dict["compression_level"])

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with h5py.File(f'{compressed_path}', 'r') as compressed_file, open(reconstructed_path,
                                                                           "wb") as reconstructed_file:
            compressed_file = compressed_file.get('dataset_1')
            compressed_file = np.array(compressed_file)
            enb.isets.dump_array_bsq(array=compressed_file, file_or_path=reconstructed_file)

    @property
    def label(self):
        return f"GZIP"


class LZF(AbstractHdf5Codec):
    """Apply the LZF algorithm using the lzma library
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        with  open(original_path, "rb") as original_file, h5py.File(compressed_path, "w") as compressed_file:
            array = enb.isets.load_array_bsq(
                file_or_path=original_path, image_properties_row=original_file_info)
            compressed_file.create_dataset('dataset_1', data=array, compression='lzf')

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with h5py.File(f'{compressed_path}', 'r') as compressed_file, open(reconstructed_path,
                                                                           "wb") as reconstructed_file:
            compressed_file = compressed_file.get('dataset_1')
            compressed_file = np.array(compressed_file)
            enb.isets.dump_array_bsq(array=compressed_file, file_or_path=reconstructed_file)

    @property
    def label(self):
        return f"LZF"


class SZIP(AbstractHdf5Codec):
    """Apply the SZIP algorithm using zlib.
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        with  open(original_path, "rb") as original_file, h5py.File(compressed_path, "w") as compressed_file:
            array = enb.isets.load_array_bsq(
                file_or_path=original_path, image_properties_row=original_file_info)
            compressed_file.create_dataset('dataset_1', data=array, compression='szip')

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with h5py.File(f'{compressed_path}', 'r') as compressed_file, open(reconstructed_path,
                                                                           "wb") as reconstructed_file:
            compressed_file = compressed_file.get('dataset_1')
            compressed_file = np.array(compressed_file)
            enb.isets.dump_array_bsq(array=compressed_file, file_or_path=reconstructed_file)

    @property
    def label(self):
        return f"SZIP"
