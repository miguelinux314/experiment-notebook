#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tools to run compression experiments
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "19/09/2019"

import os
import filecmp
import collections
import itertools
import tempfile
import time
import hashlib

from enb import atable
from enb.atable import indices_to_internal_loc
from enb import sets
from enb import imagesets
from enb.config import get_options

options = get_options()


class ExperimentTask:
    """Identify an :py:class:`Experiment`'s task and its configuration.
    """

    def __init__(self, param_dict=None):
        """
        :param param_dict: dictionary of configuration parameters used
          for this task. By default, they are part of the task's name.
        """
        self.param_dict = dict(param_dict) if param_dict is not None else {}

    @property
    def name(self):
        """Unique name that uniquely identifies a task and its configuration.
        It is not intended to be displayed as much as to be used as an index.
        """
        name = f"{self.__class__.__name__}"
        if self.param_dict:
            name += "__" + "_".join(f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name

    @property
    def label(self):
        """Label to be displayed for the task in output reports.
        May not be strictly unique nor fully informative.
        By default, the task's name is returned.
        """
        return self.name

    def __repr__(self):
        return f"<{self.__class__.__name__} (" \
               + ', '.join(repr(param) + '=' + repr(value)
                           for param, value in self.param_dict.items()) \
               + ")>"


class Experiment(atable.ATable):
    """An Experiment allows seamless execution of one or more tasks upon a
        corpus of test files. Tasks are identified by a file index and a
        :py:class:`ExperimentTask`'s (unique) name.

        For each task, any number of table columns can be defined to gather
        results of interest. This allows easy extension to highly complex and/or
        specific experiments.

        Automatic persistence of the obtained results is provided, to allow faster
        experiment development and result replication.

        Internally, an Experiment consists of an ATable containing the properties
        of the test corpus, and is itself another ATable that contains the
        results of an experiment with as many user-defined columns as needed.
        When the :meth:`~Experiment.get_df` method is called, a joint DataFrame
        instance is returned that contains both the experiment results, and the
        associated metainformation columns for each corpus element.
        """

    task_name_column = "task_name"

    def __init__(self, tasks,
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table: sets.FilePropertiesTable = None,
                 overwrite_file_properties=False,
                 parallel_dataset_property_processing=None):
        """
        :param tasks: an iterable of :py:class:`ExperimentTask` instances. Each test file
          is processed by all defined tasks. For each (file, task) combination,
          a row is included in the table returned by :py:meth:`~get_df()`.
        :param dataset_paths: list of paths to the files to be used as input.
          If it is None, this list is obtained automatically calling sets.get_all_test_file()
        :param csv_experiment_path: if not None, path to the CSV file giving persistence
          support to this experiment.
          If None, it is automatically determined within options.persistence_dir.
        :param csv_dataset_path: if not None, path to the CSV file given persistence
          support to the dataset file properties.
          If None, it is automatically determined within options.persistence_dir.
        :param dataset_info_table: if not None, it must be a sets.FilePropertiesTable instance or
          subclass instance that can be used to obtain dataset file metainformation,
          and/or gather it from csv_dataset_path. If None, a new sets.FilePropertiesTable
          instance is created and used for this purpose.
        :param overwrite_file_properties: if True, file properties are necessarily
          computed before starting the experiment. This can be useful for temporary
          and/or random datasets. If False, file properties are loaded from the
          persistent storage when available. Note that this parameter does not
          affect whether experiment results are retrieved from persistent storage if available.
          This is controlled via the parameters passed to get_df()
        :param parallel_row_processing: if not None, it determines whether file properties
          are to be obtained in parallel. If None, it is given by not options.sequential.

        """
        self.tasks = list(tasks)

        dataset_paths = dataset_paths if dataset_paths is not None \
            else sets.get_all_test_files()

        if csv_dataset_path is None:
            csv_dataset_path = os.path.join(options.persistence_dir,
                                            f"{dataset_info_table.__class__.__name__}_persistence.csv")
        os.makedirs(os.path.dirname(csv_dataset_path), exist_ok=True)
        self.dataset_info_table = dataset_info_table if dataset_info_table is not None \
            else imagesets.ImagePropertiesTable(csv_support_path=csv_dataset_path)

        self.dataset_info_table.ignored_columns = \
            set(self.dataset_info_table.ignored_columns + self.ignored_columns)

        assert len(self.dataset_info_table.indices) == 1, \
            f"dataset_info_table is expected to have a single index"

        if options.verbose:
            print(f"Obtaining properties of {len(dataset_paths)} files... "
                  f"[dataset info: {type(self.dataset_info_table).__name__}]")
        self.dataset_table_df = self.dataset_info_table.get_df(
            target_indices=dataset_paths,
            parallel_row_processing=(parallel_dataset_property_processing
                                     if parallel_dataset_property_processing is not None
                                     else not options.sequential),
            overwrite=overwrite_file_properties)

        self.target_file_paths = dataset_paths

        if csv_experiment_path is None:
            csv_experiment_path = os.path.join(options.persistence_dir,
                                               f"{self.__class__.__name__}_persistence.csv")
        os.makedirs(os.path.dirname(csv_experiment_path), exist_ok=True)
        super().__init__(csv_support_path=csv_experiment_path,
                         index=self.dataset_info_table.indices + [self.task_name_column])

    def get_df(self, target_indices=None, fill=True, overwrite=False,
               parallel_row_processing=True, target_tasks=None):
        """Get a DataFrame with the results of the experiment.

        :param parallel_row_processing: if True, parallel computation is used to fill the df,
          including compression
        :param target_paths, target_tasks: if not None, results are calculated for these
          instead of for all elements in self.target_file_paths and self.codecs,
          respectively
        """
        target_indices = self.target_file_paths if target_indices is None else target_indices
        target_tasks = self.tasks if target_tasks is None else target_tasks

        self.tasks_by_name = collections.OrderedDict({task.name: task for task in target_tasks})
        target_task_names = [t.name for t in target_tasks]
        df = super().get_df(target_indices=tuple(itertools.product(
            sorted(set(target_indices)), sorted(set(target_task_names)))),
            parallel_row_processing=parallel_row_processing,
            fill=fill, overwrite=overwrite)
        rsuffix = "__redundant__index"
        df = df.join(self.dataset_table_df.set_index(self.dataset_info_table.index),
                     on=self.dataset_info_table.index, rsuffix=rsuffix)
        if options.verbose:
            redundant_columns = list(c.replace(rsuffix, "")
                                     for c in df.columns if not c.endswith(rsuffix))
            if redundant_columns:
                print("[W]arning: redundant dataset/experiment column(s): " +
                      ', '.join(redundant_columns) + ".")
        return df[(c for c in df.columns if not c.endswith(rsuffix))]

    @property
    def joined_column_to_properties(self):
        """Get the combined dictionary of :class:`atable.ColumnProperties`
        indexed by column name. This dictionary contains the dataset properties
        columns and the experiment columns.

        Note that :py:attr:`~enb.Experiment.column_to_properties` returns only the experiment
        columns.
        """
        property_dict = dict(self.dataset_info_table.column_to_properties)
        property_dict.update(self.column_to_properties)
        return property_dict


class Experiment(Experiment):
    @Experiment.column_function(Experiment.task_name_column)
    def set_task_name(self, index, series):
        file_path, task_name = index
        series[_column_name] = self.tasks_by_name[task_name].name

    @Experiment.column_function("task_label")
    def set_task_name(self, index, series):
        file_path, task_name = index
        series[_column_name] = self.tasks_by_name[task_name].label

    @Experiment.column_function("param_dict")
    def set_param_dict(self, index, series):
        file_path, task_name = index
        series[_column_name] = self.tasks_by_name[task_name].param_dict


class CompressionExperiment(Experiment):
    def __init__(self, codecs,
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table: imagesets.ImagePropertiesTable = None,
                 overwrite_file_properties=False,
                 parallel_dataset_property_processing=None):
        """
        :param codecs: list of :py:class:`AbstractCodec` instances. Note that
          codecs are compatible with the interface of :py:class:`ExperimentTask`.
        :param dataset_paths: list of paths to the files to be used as input for compression.
          If it is None, this list is obtained automatically from the configured
          base dataset dir.
        :param csv_experiment_path: if not None, path to the CSV file giving persistence
          support to this experiment.
          If None, it is automatically determined within options.persistence_dir.
        :param csv_dataset_path: if not None, path to the CSV file given persistence
          support to the dataset file properties.
          If None, it is automatically determined within options.persistence_dir.
        :param dataset_info_table: if not None, it must be a ImagePropertiesTable instance or
          subclass instance that can be used to obtain dataset file metainformation,
          and/or gather it from csv_dataset_path. If None, a new ImagePropertiesTable
          instance is created and used for this purpose.
        :param overwrite_file_properties: if True, file properties are recomputed before starting
          the experiment. Useful for temporary and/or random datasets. Note that overwrite
          control for the experiment results themselves is controlled in the call
          to get_df
        :param parallel_row_processing: if not None, it determines whether file properties
          are to be obtained in parallel. If None, it is given by not options.sequential.
        """
        table_class = type(dataset_info_table) if dataset_info_table is not None else imagesets.ImagePropertiesTable
        csv_dataset_path = csv_dataset_path if csv_dataset_path is not None \
            else os.path.join(options.persistence_dir, f"{table_class.__name__}_persistence.csv")
        imageinfo_table = dataset_info_table if dataset_info_table is not None \
            else imagesets.ImagePropertiesTable(csv_support_path=csv_dataset_path)

        csv_dataset_path = csv_dataset_path if csv_dataset_path is not None \
            else f"{dataset_info_table.__class__.__name__}_persistence.csv"
        super().__init__(tasks=codecs,
                         dataset_paths=dataset_paths,
                         csv_experiment_path=csv_experiment_path,
                         csv_dataset_path=csv_dataset_path,
                         dataset_info_table=imageinfo_table,
                         overwrite_file_properties=overwrite_file_properties,
                         parallel_dataset_property_processing=parallel_dataset_property_processing)

    @property
    def codecs(self):
        """:return: an iterable of defined codecs
        """
        return self.tasks_by_name.values()

    @codecs.setter
    def codecs(self, new_codecs):
        self.tasks_by_name = collections.OrderedDict({
            codec.name: codec for codec in new_codecs})

    @property
    def codecs_by_name(self):
        """Alias for :py:attr:`tasks_by_name`
        """
        return self.tasks_by_name


class CompressionExperiment(CompressionExperiment):

    @CompressionExperiment.column_function([
        atable.ColumnProperties(name="compression_ratio", label="Compression ratio", plot_min=0),
        atable.ColumnProperties(name="compression_efficiency_1byte_entropy",
                                label="Compression efficiency (1B entropy)", plot_min=0),
        atable.ColumnProperties(name="lossless_reconstruction", label="Lossless?"),
        atable.ColumnProperties(name="compression_time_seconds", label="Compression time (s)", plot_min=0),
        atable.ColumnProperties(name="decompression_time_seconds", label="Decompression time (s)", plot_min=0),
        atable.ColumnProperties(name="compressed_size_bytes", label="Compressed size (bytes)", plot_min=0),
        atable.ColumnProperties(name="compressed_file_sha256", label="Compressed file's SHA256")
    ])
    def set_comparison_results(self, index, series):
        """Perform a compression-decompression cycle and store the comparison results
        """
        original_file_path, codec_name = index
        image_info_series = self.dataset_table_df.loc[indices_to_internal_loc(original_file_path)]
        codec = self.codecs_by_name[codec_name]
        with tempfile.NamedTemporaryFile(mode="w", dir=options.base_tmp_dir) \
                as compressed_file, \
                tempfile.NamedTemporaryFile(mode="w", dir=options.base_tmp_dir) \
                        as reconstructed_file:
            if options.verbose > 1:
                print(f"[E]xecuting compression {codec.name} on {index}")
            time_before = time.process_time()
            cr = codec.compress(original_path=original_file_path,
                                compressed_path=compressed_file.name,
                                original_file_info=image_info_series)
            process_compression_time = time.process_time() - time_before
            if cr is None:
                if options.verbose > 1:
                    print(f"[E]xecuting decompression {codec.name} on {index}")
                cr = codec.compression_results_from_paths(
                    original_path=original_file_path, compressed_path=compressed_file.name)

            time_before = time.process_time()
            dr = codec.decompress(compressed_path=compressed_file.name,
                                  reconstructed_path=reconstructed_file.name,
                                  original_file_info=image_info_series)
            process_decompression_time = time.process_time() - time_before
            if dr is None:
                dr = codec.decompression_results_from_paths(
                    compressed_path=compressed_file.name,
                    reconstructed_path=reconstructed_file.name)

            assert cr.compressed_path == dr.compressed_path
            assert image_info_series["bytes_per_sample"] * image_info_series["samples"] \
                   == os.path.getsize(cr.original_path)
            compression_bps = 8 * os.path.getsize(dr.compressed_path) / (image_info_series["samples"])
            compression_efficiency_1byte_entropy = (image_info_series["entropy_1B_bps"] * image_info_series[
                "bytes_per_sample"]) / compression_bps
            hasher = hashlib.sha256()
            hasher.update(open(cr.compressed_path, "rb").read())
            compressed_file_sha256 = hasher.hexdigest()

            series["lossless_reconstruction"] = filecmp.cmp(cr.original_path, dr.reconstructed_path)
            series["compression_efficiency_1byte_entropy"] = compression_efficiency_1byte_entropy
            series["compressed_size_bytes"] = os.path.getsize(cr.compressed_path)
            series["compression_time_seconds"] = cr.compression_time_seconds \
                if cr.compression_time_seconds is not None \
                else process_compression_time
            series["decompression_time_seconds"] = dr.decompression_time_seconds \
                if dr.decompression_time_seconds is not None \
                else process_decompression_time
            series["compression_ratio"] = os.path.getsize(cr.original_path) / os.path.getsize(cr.compressed_path)
            series["compressed_file_sha256"] = compressed_file_sha256
