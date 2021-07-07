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
        enb.atable.ColumnProperties("cr_dr", label="Compression ratio respect to the dynamic range.")
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


class CodecSummaryTable(enb.atable.SummaryTable):
    UNAVAILABLE, NOT_LOSSLESS, LOSSLESS, AVAILABILITY_MODE_COUNT = range(4)

    def split_groups(self, reference_df=None):
        reference_df = reference_df if reference_df is not None else self.reference_df
        return reference_df.groupby("task_label")

    @enb.atable.column_function("type_to_availability", label="Data type to availability", has_dict_values=True,
                                plot_min=UNAVAILABLE - 0.3, plot_max=AVAILABILITY_MODE_COUNT - 1 + 0.3)
    def set_type_to_availability(self, index, row):
        local_df = self.label_to_df[index]
        type_to_availability = dict()
        for (type_name, component_count), type_df in local_df.groupby(["type_name", "component_count"]):
            key = f"{type_name} {component_count}"

            if not type_df["is_working"].all():
                type_to_availability[key] = CodecSummaryTable.UNAVAILABLE
            elif type_df["is_lossless"].all():
                type_to_availability[key] = CodecSummaryTable.LOSSLESS
            else:
                type_to_availability[key] = CodecSummaryTable.NOT_LOSSLESS
        row[_column_name] = type_to_availability


if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    base_classes = {enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.LossyCodec}
    codec_classes = set(itertools.chain(*([c for c in cls.__subclasses__()
                                           if "abstract" not in c.__name__.lower()]
                                          for cls in base_classes)))
    codec_classes = set(cls for cls in codec_classes if cls not in base_classes)

    exp = AvailabilityExperiment(codecs=sorted((cls() for cls in codec_classes), key=lambda codec: codec.label))
    full_availability_df = exp.get_df()

    df = CodecSummaryTable(
        csv_support_path=os.path.join(options.persistence_dir, f"persistence_summary.csv"),
        reference_df=full_availability_df).get_df()

    enb.aanalysis.ScalarDictAnalyzer().analyze_df(
        full_df=df,
        target_columns=["type_to_availability"],
        column_to_properties=CodecSummaryTable.column_to_properties,
        group_by="group_label",
        y_tick_list=[CodecSummaryTable.UNAVAILABLE, CodecSummaryTable.NOT_LOSSLESS, CodecSummaryTable.LOSSLESS],
        y_tick_label_list=["Unavailable", "Not lossless", "Lossless"],
        show_global=False)
