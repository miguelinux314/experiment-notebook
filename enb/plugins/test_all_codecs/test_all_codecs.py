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
import re

import enb
from enb.config import options

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
    # These are the availability levels supported so far
    UNAVAILABLE, NOT_LOSSLESS, LOSSLESS = range(3)
    availability_to_label = {
        UNAVAILABLE: "Unavailable",
        NOT_LOSSLESS: "Not lossless",
        LOSSLESS: "Lossless",
    }
    availability_modes = [UNAVAILABLE, NOT_LOSSLESS, LOSSLESS]

    def split_groups(self, reference_df=None):
        """Each row of the table corresponds to a single codec (label)."""
        reference_df = reference_df if reference_df is not None else self.reference_df
        return reference_df.groupby("task_label")

    @enb.atable.column_function("type_to_availability", label="\nCodec availability for different data types",
                                has_dict_values=True,
                                plot_min=min(availability_modes) - 0.2,
                                plot_max=max(availability_modes) + 0.2)
    def set_type_bands_to_availability(self, index, row):
        local_df = self.label_to_df[index]
        type_to_availability = dict()
        for (type_name, component_count), type_df in local_df.groupby(["type_name", "component_count"]):
            band_str = f"band{'s' if component_count != 1 else ''}"
            key = f"{type_name:>6s} {component_count:3d} {band_str:<5s}"
            if not type_df["is_working"].all():
                type_to_availability[key] = CodecSummaryTable.UNAVAILABLE
            elif type_df["is_lossless"].all():
                type_to_availability[key] = CodecSummaryTable.LOSSLESS
            else:
                type_to_availability[key] = CodecSummaryTable.NOT_LOSSLESS
        row[_column_name] = type_to_availability


if __name__ == '__main__':
    if options.verbose:
        print(f"{' [ Codec Availability Test Script ] ':=^100s}")

    # Plugin import -- these are mandatory so that they can be automatically loaded below
    from enb.plugins import plugin_jpeg, plugin_flif
    from enb.plugins import plugin_mcalic
    from enb.plugins import plugin_ccsds122
    # from enb.plugins import plugin_fapec
    from enb.plugins import plugin_fse_huffman
    from enb.plugins import plugin_lcnl
    from enb.plugins import plugin_marlin
    from enb.plugins import plugin_zip
    from enb.plugins import plugin_jpeg_xl
    from enb.plugins import plugin_hevc
    from enb.plugins import plugin_kakadu
    from enb.plugins import plugin_vvc
    from enb.plugins import plugin_fpack
    from enb.plugins import plugin_zstandard
    from enb.plugins import plugin_fpzip
    from enb.plugins import plugin_zfp
    from enb.plugins import plugin_fpc
    from enb.plugins import plugin_spdp
    from enb.plugins import plugin_lz4


    def log_event(s):
        if options.verbose:
            s = f" {s}..."
            print(f"\n{s:->100s}\n")


    # Make sure data are ready
    log_event("Preparing test dataset")
    from generate_test_images import generate_test_images

    generate_test_images()
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    # This part searches for all defined codecs so far. Import new codecs to make them appear in the list
    base_classes = {enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec, enb.icompression.LossyCodec}
    codec_classes = set(itertools.chain(*([c for c in cls.__subclasses__()
                                           if "abstract" not in c.__name__.lower()]
                                          for cls in base_classes)))
    # Remove any unwanted classes from the analysis
    forbidden_classes = set(base_classes)
    codec_classes = set(cls for cls in codec_classes if cls not in base_classes)

    # Run the experiment
    log_event(f"The following {len(codec_classes)} codecs have been found")
    for c in codec_classes:
        print(f"\t:: {c.__name__}")

    log_event(f"Running the experiment. This might take some time...")
    exp = AvailabilityExperiment(codecs=sorted((cls() for cls in codec_classes), key=lambda codec: codec.label))
    full_availability_df = exp.get_df()


    # A little pre-plotting embellishment
    def save_availability_plot(summary_df, output_plot_path):
        """Allows plotting of different subsets of the full df.
        """

        def type_to_key(a):
            """Used to consistently sort typenames, e.g., u8be < s16le"""
            type_list = ["u", "s", "f"]
            type_code = type_list.index(a.strip()[0])
            bps_code = int(re.search(r'(\d+)', a).group(1))
            band_count = int(re.search('(\d+) band', a).group(1))
            return f"{type_code:05d}_{bps_code:05d}_{0 if 'be' in a else 1}_{band_count:2d}_{a}"

        # Define the x tick positions
        all_keys = set()
        for d in summary_df["type_to_availability"]:
            all_keys.update(d.keys())
        all_keys = sorted(all_keys, key=type_to_key)
        key_to_x = {k: i for i, k in enumerate(all_keys)}
        offset = 0
        last_key = all_keys[0]
        for k in all_keys:
            if k[:3] != last_key[:3]:
                offset += 1.2
            elif ("be" in last_key and "le" in k) or ("le" in last_key and "be" in k):
                offset += 0.3
            last_key = k
            key_to_x[k] += offset

        enb.aanalysis.ScalarDictAnalyzer().analyze_df(
            full_df=summary_df,
            target_columns=["type_to_availability"],
            column_to_properties=CodecSummaryTable.column_to_properties,
            group_by="group_label",
            y_tick_list=CodecSummaryTable.availability_modes,
            y_tick_label_list=[CodecSummaryTable.availability_to_label[m] for m in
                               CodecSummaryTable.availability_modes],
            key_to_x=key_to_x,
            fig_height=0.7 * len(codec_classes),
            fig_width=4 + len(key_to_x) * 0.1,
            output_plot_path=output_plot_path,
            show_global=False)


    # Generate the plots for different subsets of the full results table
    log_event("Experiment successfully run. Plotting availability analysis...")
    integer_df = full_availability_df[full_availability_df["float"] == False]
    signed_df = integer_df[integer_df["signed"] == True]
    unsigned_df = integer_df[integer_df["signed"] == False]
    float_df = full_availability_df[full_availability_df["float"] == True]
    options.no_new_results = False
    for label, full_df in (
            ("general", full_availability_df),
            ("unsigned", unsigned_df),
            ("signed", signed_df),
            ("float", float_df)):
        summary_df = CodecSummaryTable(
            csv_support_path=os.path.join(options.persistence_dir, f"persistence_summary_{label}.csv"),
            reference_df=full_df).get_df()
        save_availability_plot(summary_df, os.path.join(options.plot_dir, f"codec_availability_{label}.pdf"))

    if options.verbose:
        print(f"Saving PNG versions of the PDF files...")
    enb.aanalysis.pdf_to_png(input_dir=options.plot_dir, output_dir=options.plot_dir)
