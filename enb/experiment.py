#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tools to run compression experiments
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "19/09/2019"

import os
import filecmp
import collections
import recordclass
import itertools
import tempfile
import time
import hashlib

from enb import atable
from enb.atable import indices_to_internal_loc
from enb import sets
from enb import codec
from enb.config import get_options

options = get_options()

# ---- Begin configurable part

codec_name_column = "codec_name"
codec_label_column = "codec_label"


# ---- End configurable part

class Comparer:
    """Class to compare original, compressed and reconstructed files
    """

    def compare(self, compression_results: codec.CompressionResults,
                decompression_results: codec.DecompressionResults,
                metainfo_series):
        """
        :param compression_results: CompressionResults instance
        :param decompression_results: DecompressionResults instance
        :param metainfo_series: if not None, a pd.Series-like instance with metainfo
          about the original file
        :return: a RecordClass instance with all relevant fields of the comparison
        """
        raise NotImplementedError()


class BasicComparer(Comparer):
    class ComparisonResults(recordclass.RecordClass):
        """Minimum set of results obtained from a compression experiment instance
        """
        # compression_bps: bits per sample after compression
        # compression_efficiency_1byte_entropy: original image's byte entropy / bps
        # hexdigest of the compressed file contents
        codec_name: str = None
        codec_param_dict: dict = None
        lossless_reconstruction: bool = None
        compression_ratio: float = None
        compression_time_seconds: float = None
        decompression_time_seconds: float = None
        bytes_per_sample: int = None
        compressed_size_bytes: int = None
        compression_efficiency_1byte_entropy: float = None
        compression_bps: float = None
        compressed_file_sha256: float = None

    def compare(self, compression_results: codec.CompressionResults,
                decompression_results: codec.DecompressionResults,
                metainfo_series):
        """
        :param compression_results: CompressionResults instance
        :param decompression_results: DecompressionResults instance
        :return: a recordclass instance with all relevant fields of the comparison
        """
        assert compression_results.compressed_path == decompression_results.compressed_path

        bytes_per_sample = os.path.getsize(compression_results.original_path) // metainfo_series["samples"]
        assert bytes_per_sample * metainfo_series["samples"] == os.path.getsize(compression_results.original_path)

        compression_bps = 8 * os.path.getsize(decompression_results.compressed_path) / (metainfo_series["samples"])
        compression_efficiency_1byte_entropy = (metainfo_series["entropy_1B_bps"] * bytes_per_sample) / compression_bps

        hasher = hashlib.sha256()
        hasher.update(open(compression_results.compressed_path, "rb").read())
        compressed_file_sha256 = hasher.hexdigest()

        return self.ComparisonResults(
            codec_name=compression_results.codec_name,
            codec_param_dict=dict(compression_results.codec_param_dict),
            bytes_per_sample=bytes_per_sample,
            compressed_size_bytes=os.path.getsize(compression_results.compressed_path),
            compression_time_seconds=compression_results.compression_time_seconds,
            decompression_time_seconds=decompression_results.decompression_time_seconds,
            lossless_reconstruction=filecmp.cmp(compression_results.original_path,
                                                decompression_results.reconstructed_path),
            compression_ratio=os.path.getsize(compression_results.original_path) /
                              os.path.getsize(compression_results.compressed_path),
            compression_bps=compression_bps,
            compression_efficiency_1byte_entropy=compression_efficiency_1byte_entropy,
            compressed_file_sha256=compressed_file_sha256)


class CompressionExperiment(atable.ATable):
    pass


class CompressionExperiment(BasicComparer, CompressionExperiment):
    base_tmp_dir = options.base_tmp_dir
    os.makedirs(base_tmp_dir, exist_ok=True)

    ignored_columns = [
        "codec_param_dict",  # not needed since codec.AbstractCodec shows these by default
    ]

    def __init__(self, codecs,
                 target_file_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_table: sets.FilePropertiesTable = None,
                 overwrite_file_properties=False,
                 parallel_dataset_property_processing=None):
        """
        :param codecs: list of AbstractCodec instances
        :param target_file_paths: list of paths to the files to be used as input for compression.
          If it is None, this list is obtained automatically from the configured
          base dataset dir.
        :param csv_experiment_path: if not None, path to the CSV file giving persistence
          support to this experiment.
          If None, it is automatically determined within options.persistence_dir.
        :param csv_dataset_path: if not None, path to the CSV file given persistence
          support to the dataset file properties.
          If None, it is automatically determined within options.persistence_dir.
        :param dataset_table: if not None, it must be a FilePropertiesTable instance or
          subclass instance that can be used to obtain dataset file metainformation,
          and/or gather it from csv_dataset_path. If None, a new FilePropertiesTable
          instance is created and used for this purpose.
        :param overwrite_file_properties: if True, file properties are recomputed before starting
          the experiment. Useful for temporary and/or random datasets. Note that overwrite
          control for the experiment results themselves is controlled in the call
          to get_df
        :param parallel_row_processing: if not None, it determines whether file properties
          are to be obtained in parallel. If None, it is given by not options.sequential.
        """
        target_file_paths = target_file_paths if target_file_paths is not None \
            else sets.get_all_test_files()

        if csv_dataset_path is None:
            os.makedirs(options.persistence_dir, exist_ok=True)
            csv_dataset_path = os.path.join(options.persistence_dir, "dataset_properties_persistence.csv")
        self.dataset_table = dataset_table if dataset_table is not None \
            else sets.FilePropertiesTable(csv_support_path=csv_dataset_path)

        self.dataset_table.ignored_columns = set(self.dataset_table.ignored_columns + self.ignored_columns)

        assert len(self.dataset_table.indices) == 1, f"FileInfo tables are expected to have a single index"

        if options.verbose:
            print(f"Obtaining properties [{type(self.dataset_table).__name__}] "
                  f"of {len(target_file_paths)} files...")
        self.dataset_table_df = self.dataset_table.get_df(
            target_indices=target_file_paths,
            parallel_row_processing=(parallel_dataset_property_processing
                                     if parallel_dataset_property_processing is not None
                                     else not options.sequential),
            overwrite=overwrite_file_properties)
        self.target_file_paths = target_file_paths
        self.codecs_by_name = collections.OrderedDict({
            codec_.name: codec_ for codec_ in codecs})

        if csv_experiment_path is None:
            os.makedirs(options.persistence_dir, exist_ok=True)
            csv_experiment_path = os.path.join(options.persistence_dir, "experiment_persistence.csv")
        super().__init__(csv_support_path=csv_experiment_path,
                         index=self.dataset_table.indices + [codec_name_column])

    @property
    def joined_column_to_properties(self):
        property_dict = dict(self.dataset_table.column_to_properties)
        property_dict.update(self.column_to_properties)
        return property_dict

    @property
    def codecs(self):
        return self.codecs_by_name.values()

    @codecs.setter
    def codecs(self, new_codecs):
        self.codecs_by_name = collections.OrderedDict({
            codec.name: codec for codec in new_codecs})

    def get_df(self, target_indices=None, fill=True, overwrite=False,
               parallel_row_processing=True, target_codecs=None):
        """Get a DataFrame with the results of the experiment.
        :param parallel_row_processing: if True, parallel computation is used to fill the df,
          including compression
        :param target_paths, target_codecs: if not None, results are calculated for these
          instead of for all elements in self.target_file_paths and self.codecs,
          respectively
        """
        target_indices = self.target_file_paths if target_indices is None else target_indices
        target_codecs = self.codecs if target_codecs is None else target_codecs
        target_codec_names = [c.name for c in target_codecs]
        df = super().get_df(target_indices=tuple(itertools.product(
            sorted(set(target_indices)), sorted(set(target_codec_names)))),
            parallel_row_processing=parallel_row_processing,
            fill=fill, overwrite=overwrite)
        rsuffix = "__redundant__index"
        df = df.join(self.dataset_table_df.set_index(self.dataset_table.index),
                     on=self.dataset_table.index, rsuffix=rsuffix)
        return df[list(c for c in df.columns if not c.endswith(rsuffix))]

    @CompressionExperiment.column_function([
        atable.ColumnProperties(name=field_name, fun=None,
                                label=field_name.replace("_", " ").title(),
                                plot_min=0 if field_name in ["compression_efficiency_1byte_entropy",
                                                             "compression_ratio",
                                                             "compression_bps", "compression_time_seconds"] else None)
        for field_name in BasicComparer.ComparisonResults.__fields__
        if field_name not in codec_name_column])
    def set_comparison_results(self, index, series):
        """Perform a compression-decompression cycle and store the comparison results
        """
        original_file_path, codec_name = index
        file_info_series = self.dataset_table_df.loc[indices_to_internal_loc(original_file_path)]
        codec = self.codecs_by_name[codec_name]
        with tempfile.NamedTemporaryFile(mode="w", dir=self.base_tmp_dir) \
                as compressed_file, \
                tempfile.NamedTemporaryFile(mode="w", dir=self.base_tmp_dir) \
                        as reconstructed_file:
            if options.verbose > 1:
                print(f"[E]xecuting compression {codec.name} on {index}")
            time_before = time.process_time()
            cr = codec.compress(original_path=original_file_path,
                                compressed_path=compressed_file.name,
                                original_file_info=file_info_series)
            process_compression_time = time.process_time() - time_before
            if cr is None:
                if options.verbose > 1:
                    print(f"[E]xecuting decompression {codec.name} on {index}")
                cr = codec.compression_results_from_paths(
                    original_path=original_file_path, compressed_path=compressed_file.name)

            time_before = time.process_time()
            dr = codec.decompress(compressed_path=compressed_file.name,
                                  reconstructed_path=reconstructed_file.name,
                                  original_file_info=file_info_series)
            process_decompression_time = time.process_time() - time_before
            if dr is None:
                dr = codec.decompression_results_from_paths(
                    compressed_path=compressed_file.name,
                    reconstructed_path=reconstructed_file.name)

            comparison_results = self.compare(
                compression_results=cr,
                decompression_results=dr,
                metainfo_series=file_info_series)

            if comparison_results.compression_time_seconds is None:
                comparison_results.compression_time_seconds = process_compression_time
            if comparison_results.decompression_time_seconds is None:
                comparison_results.decompression_time_seconds = process_decompression_time

            for field in comparison_results.__fields__:
                series[field] = comparison_results[field]

    @CompressionExperiment.column_function("codec_label")
    def set_codec_label(self, input_path, file_info):
        file_info[_column_name] = self.codecs_by_name[file_info["codec_name"]].label


if __name__ == "__main__":
    print("Non executable module")
