#!/usr/bin/env python3
"""Evaluate the availability of data compressor/decompressor pairs (codecs) defined for enb.

By default, all detected, non-"abstract" codecs are tested.
If one or more command line arguments are passed, only codec classes matching that name will be tested.
Empty codec selections are invalid.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/07/06"

import sys
import os
import tempfile
import filecmp
import glob
import re
import traceback
import importlib

import enb
from enb.config import options


class AvailabilityExperiment(enb.experiment.Experiment):
    def __init__(self, codecs):
        super().__init__(tasks=codecs, dataset_info_table=enb.isets.ImagePropertiesTable)

    @enb.atable.column_function([
        enb.atable.ColumnProperties("is_working", label="Does the codec work for this input?"),
        enb.atable.ColumnProperties("is_lossless", label="Was compression lossless?"),
        enb.atable.ColumnProperties("cr_dr",
                                    label="Compression ratio respect to the dynamic range."),
        enb.atable.ColumnProperties("error_str", label="Error string for this execution"),
    ])
    def set_availability_columns(self, index, row):
        file_path, codec = self.index_to_path_task(index)
        try:
            with tempfile.NamedTemporaryFile() as tmp_compressed_file, \
                    tempfile.NamedTemporaryFile(suffix=".raw") as tmp_reconstructed_file:
                os.remove(tmp_compressed_file.name)
                os.remove(tmp_reconstructed_file.name)
                codec.compress(
                    original_path=file_path,
                    compressed_path=tmp_compressed_file.name,
                    original_file_info=self.get_dataset_info_row(file_path))
                if not os.path.isfile(tmp_compressed_file.name) or not os.path.getsize(
                        tmp_compressed_file.name):
                    raise enb.icompression.CompressionException(
                        f"[E]rror compressing {index} -- did not produce a file")
                codec.decompress(
                    compressed_path=tmp_compressed_file.name,
                    reconstructed_path=tmp_reconstructed_file.name,
                    original_file_info=self.get_dataset_info_row(file_path))
                row["is_working"] = True
                row["is_lossless"] = filecmp.cmp(file_path, tmp_reconstructed_file.name)
                row["cr_dr"] = self.get_dataset_info_row(file_path)["samples"] \
                               * self.get_dataset_info_row(file_path)["dynamic_range_bits"] \
                               / (8 * os.path.getsize(tmp_compressed_file.name))
                row["error_str"] = "No error"
        except Exception as ex:
            row["error_str"] = repr(traceback.format_exc())
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

    def split_groups(self, reference_df=None, include_all_group=None):
        """Each row of the table corresponds to a single codec (label)."""
        reference_df = reference_df if reference_df is not None else self.reference_df
        return reference_df.groupby("task_label")

    @enb.atable.column_function("type_to_availability",
                                label="\nCodec availability for different data types",
                                has_dict_values=True,
                                plot_min=min(availability_modes) - 0.2,
                                plot_max=max(availability_modes) + 0.2)
    def set_type_bands_to_availability(self, index, row):
        local_df = self.label_to_df[index]
        type_to_availability = dict()
        for (type_name, component_count), type_df in local_df.groupby(
                ["type_name", "component_count"]):
            if type_name[1] == "8":
                type_name = f"{type_name[:1]} 8{type_name[2:]}"
            type_name = f"{type_name[:3]} bit {type_name[3:]}"
            if type_name[0] == "f":
                type_name = f"Float {type_name[1:]}"
            elif type_name[0] == "u":
                type_name = f"Unsigned int {type_name[1:]}"
            elif type_name[0] == "s":
                type_name = f"Signed int {type_name[1:]}"

            if type_name[-2:] == "be":
                type_name = f"{type_name[:-2]}   big endian"
            elif type_name[-2:] == "le":
                type_name = f"{type_name[:-2]} little endian"

            key = f"{type_name} {component_count:02d} bands"
            if not type_df["is_working"].all():
                type_to_availability[key] = CodecSummaryTable.UNAVAILABLE
            elif type_df["is_lossless"].all():
                type_to_availability[key] = CodecSummaryTable.LOSSLESS
            else:
                type_to_availability[key] = CodecSummaryTable.NOT_LOSSLESS
        row[_column_name] = type_to_availability


def main():
    enb.config.options.chunk_size = enb.config.options.chunk_size or 2048
    enb.logger.message("\n[bold]Codec Availability Test[/bold]\n", markup=True)

    # Plugin import -- these are needed so that codecs get defined and can
    # be automatically retrieved below (ignore IDE non-usage warnings).
    # NOTE: the build script should have created the `plugins` folder with all these codecs

    enb.logger.verbose("Importing plugin modules", rule=True)
    plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
    assert os.path.isdir(plugin_dir), \
        "The build script should have placed everything under plugins, " \
        "please report this if you feel it is a bug."
    for d in [p for p in glob.glob(os.path.join(plugin_dir, "*")) if
              os.path.exists(os.path.join(p, "__init__.py"))]:
        print(f"Importing {os.path.basename(d)}...")
        importlib.import_module(f"{os.path.basename(plugin_dir)}.{os.path.basename(d)}")

    # Make sure data are ready
    enb.logger.verbose("Preparing test dataset", rule=True)
    from generate_test_images import generate_test_images

    generate_test_images()
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    # This part searches for all defined codecs so far. Import new codecs to make them appear in the list
    # It also filters away any class with 'abstract' in the name.
    codec_classes = enb.misc.get_all_subclasses(
        enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec,
        enb.icompression.LossyCodec)

    # Remove any unwanted classes from the analysis
    excluded_names = (
        "abstract", "fapec", "v2f", "magli", "greenbook", "mhdc", "mhdc_pot",
        "fpc", "spdp", "zstandard_train", "quantizationwrappercodec")

    # Instantiate the codec classes that can be initialized automatically
    codec_classes = set(
        c for c in codec_classes if not any(n in c.__name__.lower() for n in excluded_names))
    filter_args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if filter_args:
        enb.logger.verbose(f"Filtering for {', '.join(repr(s) for s in filter_args)}", rule=True)
        codec_classes = [c for c in codec_classes
                         if
                         any(s.strip().lower() in c.__name__.strip().lower() for s in filter_args)]
        if not codec_classes:
            enb.logger.verbose("Error: no codec matched the filter strings "
                               f"({', '.join(repr(v) for v in sys.argv[1:] if not v.startswith('-'))}). "
                               f"Exiting now.", rule=True)
            raise ValueError(sys.argv)
    codec_list = list(cls() for cls in codec_classes)

    # Add manual codecs to be included in the analysis
    codec_list.append(enb.icompression.QuantizationWrapperCodec(
        codec=[c for c in codec_classes if c.__name__ == "LZMA"][0](),
        qstep=1))

    codec_list = sorted(codec_list, key=lambda c: c.__class__.__name__.lower())

    if options.verbose:
        enb.logger.verbose(f"The following {len(codec_list)} codecs have been found"
                           f"{' (after filtering)' if len(sys.argv) > 1 else ''}", rule=True)
        for c in codec_list:
            print(f"\t:: {c.__class__.__name__}")

    # Run the experiment
    enb.logger.verbose(f"Running the experiment. This might take some time...", rule=True)
    exp = AvailabilityExperiment(codecs=codec_list)
    full_availability_df = exp.get_df()

    summary_df = CodecSummaryTable(
        csv_support_path=os.path.join(options.persistence_dir, f"persistence_summary.csv"),
        full_df=full_availability_df).get_df()
    analyzer = enb.aanalysis.DictNumericAnalyzer()

    all_keys = sorted(list(summary_df.iloc[0]["type_to_availability"].keys()))

    selected_keys = all_keys
    key_to_x = {k: i for i, k in enumerate(selected_keys)}
    for i in range(4, len(selected_keys), 4):
        for k in all_keys[i:]:
            key_to_x[k] += 1.75

    analyzer.get_df(
        full_df=summary_df,
        target_columns=["type_to_availability"],
        group_by="group_label",
        key_to_x=key_to_x,
        x_tick_list=[key_to_x[k] for k in selected_keys],
        x_tick_label_list=selected_keys,
        x_tick_label_angle=90,
        fig_width=10,
        fig_height=27,
        y_tick_list=CodecSummaryTable.availability_modes,
        y_tick_label_list=[CodecSummaryTable.availability_to_label[m] for m in
                           CodecSummaryTable.availability_modes],
        y_min=-0.3,
        y_max=2.3,
        global_x_label="Data type",
        show_count=False,
        global_y_label="",
        show_grid=True,
    )

    enb.logger.verbose("Test all codecs successfully completed")
    print(f"You can now see the availability plots in .pdf and .png format at {options.plot_dir}")


if __name__ == '__main__':
    main()
