#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evaluate the availability of data compressor/decompressor pairs (codecs) defined for enb.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "06/07/2021"

import os
import tempfile
import filecmp
import itertools

import enb
from enb.config import options
# Plugin import
from plugins import plugin_jpeg, plugin_flif
from plugins import plugin_mcalic
from plugins import plugin_ccsds122
# from plugins import plugin_fapec
from plugins import plugin_fse_huffman
from plugins import plugin_lcnl
from plugins import plugin_marlin
from plugins import plugin_zip
from plugins import plugin_jpeg_xl
from plugins import plugin_hevc
from plugins import plugin_kakadu
from plugins import plugin_vvc
from plugins import plugin_fpack
from plugins import plugin_zstandard
from plugins import plugin_fpzip
from plugins import plugin_zfp
from plugins import plugin_fpc
from plugins import plugin_spdp
from plugins import plugin_lz4


class AvailabilityExperiment(enb.experiment.Experiment):
    def __init__(self, codecs):
        super().__init__(tasks=codecs, dataset_info_table=enb.isets.ImagePropertiesTable)

    @enb.atable.column_function([
        enb.atable.ColumnProperties("is_working", label="Does the codec work for this input?"),
        enb.atable.ColumnProperties("is_lossless", label="Was compression lossless?"),
        enb.atable.ColumnProperties("cr_dr", label="Compression ratio respect to the dynamic range."),
    ])
    def set_availability_columns(self, index, row):
        file_path, codec = self.index_to_path_task(index)
        try:
            with tempfile.NamedTemporaryFile() as tmp_compressed_file, \
                    tempfile.NamedTemporaryFile() as tmp_reconstructed_file:
                os.remove(tmp_compressed_file.name)
                os.remove(tmp_reconstructed_file.name)
                codec.compress(
                    original_path=file_path,
                    compressed_path=tmp_compressed_file.name,
                    original_file_info=self.get_dataset_info_row(file_path))
                if not os.path.isfile(tmp_compressed_file.name) or not os.path.getsize(tmp_compressed_file.name):
                    raise enb.icompression.CompressionException(f"[E]rror compressing {index}")
                codec.decompress(
                    compressed_path=tmp_compressed_file.name,
                    reconstructed_path=tmp_reconstructed_file.name,
                    original_file_info=self.get_dataset_info_row(file_path))
                row["is_working"] = True
                row["is_lossless"] = filecmp.cmp(file_path, tmp_reconstructed_file.name)
                row["cr_dr"] = self.get_dataset_info_row(file_path)["samples"] \
                               * self.get_dataset_info_row(file_path)["dynamic_range_bits"] \
                               / (8 * os.path.getsize(tmp_compressed_file.name))
        except Exception as ex:
            row["is_working"] = False
            row["is_lossless"] = False
            row["cr_dr"] = 0


if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    base_classes = set([enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.LossyCodec])
    codec_classes = set(itertools.chain(*([c for c in cls.__subclasses__() if "abstract" not in c.__name__.lower()]
                                          for cls in base_classes)))
    codec_classes = set(cls for cls in codec_classes if cls not in base_classes)

    exp = AvailabilityExperiment(codecs=sorted((cls() for cls in codec_classes), key=lambda codec: codec.label))
    df = exp.get_df()
