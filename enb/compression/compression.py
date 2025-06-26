#!/usr/bin/env python3
"""Data compression tools common to any compression modality.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/01"

import os
import re
import filecmp
import hashlib
import tempfile
import time
import collections
import shutil
import math
from typing import Optional

import numpy as np

from scipy import signal
from scipy.ndimage.filters import convolve

import enb
import enb.isets
import enb.tcall
from enb.config import options


class CompressionResults:
    """Base class that defines the minimal fields that are returned by a call
    to a coder's compress() method (or produced by the CompressionExperiment
    instance).
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, codec_name=None, codec_param_dict=None,
                 original_path=None,
                 compressed_path=None,
                 compression_time_seconds=None,
                 maximum_memory_kb=None):
        """
        :param codec_name: codec's reported_name
        :param codec_param_dict: dictionary of parameters to the codec
        :param original_path: path to the input original file
        :param compressed_path: path to the output compressed file
        :param compression_time_seconds: effective average compression time in
          seconds
        :param maximum_memory_kb: maximum resident memory in kilobytes
        """
        # pylint: disable=too-many-arguments
        self.codec_name = codec_name
        self.codec_param_dict = codec_param_dict
        self.original_path = original_path
        self.compressed_path = compressed_path
        self.compression_time_seconds = compression_time_seconds
        self.maximum_memory_kb = maximum_memory_kb


class DecompressionResults:
    """Base class that defines the minimal fields that are returned by a call
    to a coder's decompress() method (or produced by the
    CompressionExperiment instance).
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, codec_name=None, codec_param_dict=None,
                 compressed_path=None,
                 reconstructed_path=None,
                 decompression_time_seconds=None,
                 maximum_memory_kb=None):
        """
        :param codec_name: codec's reported_name
        :param codec_param_dict: dictionary of parameters to the codec
        :param compressed_path: path to the output compressed file
        :param reconstructed_path: path to the reconstructed file after
          decompression
        :param decompression_time_seconds: effective decompression time in
          seconds
        :param maximum_memory_kb: maximum resident memory in kilobytes
        """
        # pylint: disable=too-many-arguments
        self.codec_name = codec_name
        self.codec_param_dict = codec_param_dict
        self.compressed_path = compressed_path
        self.reconstructed_path = reconstructed_path
        self.decompression_time_seconds = decompression_time_seconds
        self.maximum_memory_kb = maximum_memory_kb


class CompressionException(Exception):
    """Base class for exceptions occurred during a compression instance
    """

    def __init__(self, original_path=None, compressed_path=None, file_info=None,
                 status=None, output=None):
        # pylint: disable=too-many-arguments
        super().__init__(f"status={status}, output={output}")
        self.original_path = original_path
        self.compressed_path = compressed_path
        self.file_info = file_info
        self.status = status
        self.output = output


class DecompressionException(Exception):
    """Base class for exceptions occurred during a decompression instance
    """

    def __init__(self, compressed_path=None, reconstructed_path=None,
                 file_info=None, status=None, output=None):
        # pylint: disable=too-many-arguments
        super().__init__(f"status={status}, output={output}")
        self.reconstructed_path = reconstructed_path
        self.compressed_path = compressed_path
        self.file_info = file_info
        self.status = status
        self.output = output


class CompressionExperiment(enb.experiment.Experiment):
    """This class allows seamless execution of compression experiments.

    In the functions decorated with @atable,column_function, the row argument
    contains two magic properties, compression_results and decompression_results.
    These give access to the :class:`CompressionResults` and :class:`DecompressionResults`
    instances resulting respectively from compressing and decompressing
    according to the row index parameters. The paths referenced in the compression
    and decompression results are valid while the row is being processed, and
    are disposed of afterwards.
    Also, the image_info_row attribute gives access to the image metainformation
    (e.g., geometry)
    """
    dataset_files_extension = "raw"
    default_file_properties_table_class = enb.isets.ImagePropertiesTable
    row_wrapper_column_name = "_codec_wrapper"

    class CompressionDecompressionWrapper:
        """This class is instantiated for each row of the table, and added to a temporary
        column row_wrapper_column_name. Column-setting methods can then access this wrapper,
        and in particular its `compression_results` and `decompression_results` properties,
        which will run compression and decompression at most once. This way, many columns can
        be defined independently without needing to compress and decompress for each one.
        """

        def __init__(self, file_path, codec, image_info_row,
                     reconstructed_copy_dir=None,
                     compressed_copy_dir=None):
            """
            :param file_path: path to the original image being compressed
            :param codec: AbstractCodec instance to be used for compression/decompression
            :param image_info_row: dict-like object with geometry and
              data type information about file_path
            :param reconstructed_copy_dir: if not None, a copy of the reconstructed images
              is stored, based on the class of codec.
            :param compressed_copy_dir: if not None, a copy of the compressed images
              is stored, based on the class of codec.
            """
            # pylint: disable=too-many-arguments
            self.file_path = file_path
            self.codec = codec
            self.image_info_row = image_info_row
            self._compression_results = None
            self._decompression_results = None
            self.compressed_copy_dir = compressed_copy_dir
            self.reconstructed_copy_dir = reconstructed_copy_dir

        @property
        def compression_results(self) -> CompressionResults:
            """Perform the actual compression experiment for the selected row.
            """
            if self._compression_results is None:
                os.makedirs(options.base_tmp_dir, exist_ok=True)
                # Assign a unique temporary path to the compressed file and avoid introducing spurious geometry tags
                tmp_compressed_path = None
                while ((tmp_compressed_path is None) or
                       (re.search(r"\d+x\d+x\d+.*\D\d+x\d+x\d+", os.path.basename(tmp_compressed_path)) is not None)):
                    fd, tmp_compressed_path = tempfile.mkstemp(
                        dir=options.base_tmp_dir,
                        prefix=f"compressed_{os.path.basename(self.file_path)}_")
                    os.close(fd)
                    os.remove(tmp_compressed_path)

                try:
                    measured_times = []
                    measured_memory = []

                    enb.logger.debug(
                        f"Executing compression {self.codec.name} on {self.file_path} "
                        f"[{options.repetitions} times]")
                    for repetition_index in range(options.repetitions):
                        enb.logger.debug(
                            f"Executing compression {self.codec.name} on {self.file_path} "
                            f"[rep{repetition_index + 1}/{options.repetitions}]")
                        time_before_ns = time.time_ns()
                        self._compression_results = self.codec.compress(
                            original_path=self.file_path,
                            compressed_path=tmp_compressed_path,
                            original_file_info=self.image_info_row)

                        if not os.path.isfile(tmp_compressed_path) \
                                or os.path.getsize(tmp_compressed_path) == 0:
                            raise CompressionException(
                                original_path=self.file_path,
                                compressed_path=tmp_compressed_path,
                                file_info=self.image_info_row,
                                output=f"Compression of {self.file_path} "
                                       f"didn't produce a file (or it was empty)")

                        wall_compression_time = \
                            (time.time_ns() - time_before_ns) / 1e9
                        if self._compression_results is None:
                            enb.logger.debug(
                                f"[W]arning: codec {self.codec.name} "
                                f"did not report execution times. "
                                f"Using wall clock instead (might be inaccurate)")
                            self._compression_results = \
                                self.codec.compression_results_from_paths(
                                    original_path=self.file_path,
                                    compressed_path=tmp_compressed_path)
                            self._compression_results.compression_time_seconds = \
                                wall_compression_time

                        measured_times.append(
                            self._compression_results.compression_time_seconds)
                        measured_memory.append(
                            self._compression_results.maximum_memory_kb)

                        if self.compressed_copy_dir and repetition_index == 0:
                            output_path = os.path.join(
                                self.compressed_copy_dir,
                                self.codec.name,
                                f"{os.path.basename(self.file_path)}.compressed")
                            os.makedirs(os.path.dirname(output_path),
                                        exist_ok=True)
                            enb.logger.debug(
                                f"Storing compressed bitstream for "
                                f"{self.file_path} and {self.codec} "
                                f"at {repr(output_path)}")
                            shutil.copyfile(tmp_compressed_path, output_path)

                        if repetition_index < options.repetitions - 1:
                            os.remove(tmp_compressed_path)

                    # The minimum time is kept, all other values are
                    # considered to have noise added by the OS
                    self._compression_results.compression_time_seconds = min(
                        measured_times)
                    # The maximum resident memory in kb is kept
                    self._compression_results.maximum_memory_kb \
                        = max(kb if kb is not None else -1
                              for kb in measured_memory)
                except Exception as ex:
                    if os.path.exists(tmp_compressed_path):
                        os.remove(tmp_compressed_path)
                    raise ex

            return self._compression_results

        @property
        def decompression_results(self) -> DecompressionResults:
            """Perform the actual decompression experiment for the selected row.
            """
            if self._decompression_results is None:
                # Assign a unique temporary path to the reconstructed file and avoid introducing spurious geometry tags
                tmp_reconstructed_path = None
                while ((tmp_reconstructed_path is None) or
                       (re.search(r"\d+x\d+x\d+.*\D\d+x\d+x\d+",
                                  os.path.basename(tmp_reconstructed_path)) is not None)):
                    fd, tmp_reconstructed_path = tempfile.mkstemp(
                        dir=options.base_tmp_dir,
                        prefix=f"compressed_{os.path.basename(self.file_path)}_")
                    os.close(fd)
                    os.remove(tmp_reconstructed_path)
                    
                try:
                    measured_times = []
                    measured_memory = []
                    with enb.logger.debug_context(
                            f"Executing decompression {self.codec.name} "
                            f"on {self.file_path} [{options.repetitions} times]"
                            + ("\n" if options.repetitions > 1 else "")):
                        for repetition_index in range(options.repetitions):
                            enb.logger.debug(
                                f"Executing decompression {self.codec.name} "
                                f"on {self.file_path} "
                                f"[rep{repetition_index + 1}/{options.repetitions}]")

                            time_before = time.time_ns()
                            self._decompression_results = self.codec.decompress(
                                compressed_path=self.compression_results.compressed_path,
                                reconstructed_path=tmp_reconstructed_path,
                                original_file_info=self.image_info_row)

                            wall_decompression_time = \
                                (time.time_ns() - time_before) / 1e9
                            if self._decompression_results is None:
                                enb.logger.debug(
                                    f"Codec {self.codec.name} did not report "
                                    f"execution times. Using wall clock "
                                    f"instead (might be inaccurate with "
                                    f"intensive I/O)")
                                self._decompression_results = \
                                    self.codec.decompression_results_from_paths(
                                        compressed_path=self.compression_results.compressed_path,
                                        reconstructed_path=tmp_reconstructed_path)
                                self._decompression_results.decompression_time_seconds = \
                                    wall_decompression_time

                            if not os.path.isfile(
                                    tmp_reconstructed_path) or os.path.getsize(
                                self._decompression_results.reconstructed_path) == 0:
                                raise CompressionException(
                                    original_path=self.compression_results.original_path,
                                    compressed_path=self.compression_results.compressed_path,
                                    file_info=self.image_info_row,
                                    output=f"Decompression didn't produce a file (or it was empty)"
                                           f" {self.compression_results.original_path}")

                            measured_times.append(
                                self._decompression_results.decompression_time_seconds)
                            measured_memory.append(
                                self._decompression_results.maximum_memory_kb)

                            if self.reconstructed_copy_dir and repetition_index == 0:
                                output_path = os.path.join(
                                    self.reconstructed_copy_dir,
                                    self.codec.name,
                                    os.path.basename(self.file_path))
                                os.makedirs(os.path.dirname(output_path),
                                            exist_ok=True)
                                enb.logger.debug(
                                    f"Storing reconstructed copy of "
                                    f"{self.file_path} with {self.codec} "
                                    f"at {repr(output_path)}")
                                shutil.copyfile(tmp_reconstructed_path,
                                                output_path)

                            if repetition_index < options.repetitions - 1:
                                os.remove(tmp_reconstructed_path)
                    # The minimum time is kept, the remaining values are
                    # assumed to contain noised added by the OS
                    self._decompression_results.decompression_time_seconds = \
                        min(measured_times)
                    self._decompression_results.maximum_memory_kb \
                        = max(kb if kb is not None else -1
                              for kb in measured_memory)
                except Exception as ex:
                    os.remove(tmp_reconstructed_path)
                    raise ex

            return self._decompression_results

        @property
        def numpy_dtype(self):
            """Get the numpy dtype corresponding to the original image's data
            format
            """

            return enb.isets.iproperties_row_to_numpy_dtype(
                self.image_info_row)

        def __del__(self):
            if self._compression_results is not None:
                try:
                    os.remove(self._compression_results.compressed_path)
                except OSError:
                    pass
            if self._decompression_results is not None:
                try:
                    os.remove(self._decompression_results.reconstructed_path)
                except OSError:
                    pass

    def __init__(self, codecs,
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table=None,
                 overwrite_file_properties=False,
                 reconstructed_dir_path=None,
                 compressed_copy_dir_path=None,
                 task_families=None):
        """
        :param codecs: list of :py:class:`AbstractCodec` instances. Note that
          codecs are compatible with the interface of :py:class:`ExperimentTask`.
        :param dataset_paths: list of paths to the files to be used as input
          for compression. If it is None, this list is obtained automatically
          from the configured base dataset dir.
        :param csv_experiment_path: if not None, path to the CSV file giving
          persistence support to this experiment. If None, it is automatically
          determined within options.persistence_dir.
        :param csv_dataset_path: if not None, path to the CSV file given
          persistence support to the dataset file properties. If None,
          it is automatically determined within options.persistence_dir.
        :param dataset_info_table: if not None, it must be a
          ImagePropertiesTable instance or subclass instance that can be used
          to obtain dataset file metainformation, and/or gather it from
          csv_dataset_path. If None, a new ImagePropertiesTable instance is
          created and used for this purpose.
        :param overwrite_file_properties: if True, file properties are
          recomputed before starting the experiment. Useful for temporary
          and/or random datasets. Note that overwrite control for the
          experiment results themselves is controlled in the call to get_df
        :param reconstructed_dir_path: if not None, a directory where
          reconstructed images are to be stored.
        :param compressed_copy_dir_path: if not None, it gives the directory
          where a copy of the compressed images. is to be stored. If may not be
          generated for images for which all columns are known
        :param task_families: if not None, it must be a list of TaskFamily
          instances. It is used to set the "family_label" column for each row.
          If the codec is not found within the families, a default label is set
          indicating so.
        """
        # pylint: disable=too-many-arguments
        table_class = type(dataset_info_table) if dataset_info_table is not None \
            else self.default_file_properties_table_class
        csv_dataset_path = csv_dataset_path if csv_dataset_path is not None \
            else os.path.join(options.persistence_dir,
                              f"persistence_{table_class.__name__}.csv")
        imageinfo_table = dataset_info_table if dataset_info_table is not None \
            else table_class(csv_support_path=csv_dataset_path)

        csv_dataset_path = csv_dataset_path if csv_dataset_path is not None \
            else f"persistence_{dataset_info_table.__class__.__name__}.csv"

        if not codecs:
            raise ValueError(
                f"{self}: no codecs were selected for this experiment. At least one is needed.")
        non_subclass_codecs = [c for c in codecs if not isinstance(c, enb.compression.codec.AbstractCodec)]
        if non_subclass_codecs:
            enb.logger.warn(
                f"Compression experiment {self.__class__.__name__} "
                f"received parameter codecs "
                f"with {len(non_subclass_codecs)} objects not inheriting from "
                f"enb.icompression.AbstractCodec: "
                f"{', '.join(repr(c) for c in non_subclass_codecs)}.\n"
                f"You can remove this warning by explicitly inheriting "
                f"from that class for "
                f"the aforementioned instances.")

        super().__init__(tasks=codecs,
                         dataset_paths=dataset_paths,
                         csv_experiment_path=csv_experiment_path,
                         csv_dataset_path=csv_dataset_path,
                         dataset_info_table=imageinfo_table,
                         overwrite_file_properties=overwrite_file_properties,
                         task_families=task_families)
        self.reconstructed_dir_path = reconstructed_dir_path
        self.compressed_copy_dir_path = compressed_copy_dir_path
        # This attribute is automatically set before running the defined
        # column-setting functions, then set back to None after that. It
        # enables lazy and at-most-once compression/decompression.
        self.codec_results: Optional[CompressionExperiment.CompressionDecompressionWrapper] = None

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

    @property
    def compression_results(self) -> CompressionResults:
        """Get the current compression results from self.codec_results.
        This property is intended to be read from functions that set columns of a row.
        It triggers the compression of that row's sample with that row's codec if it hasn't been compressed yet.
        Otherwise, None is returned.
        """
        return self.codec_results.compression_results if self.codec_results else None

    @property
    def decompression_results(self) -> DecompressionResults:
        """Get the current decompression results from self.codec_results.
        This property is intended to be read from functions that set columns of a row.
        It triggers the compression and decompression of that row's sample with that row's codec if
        they have not been compressed yet.
        Otherwise, None is returned.
        """
        return self.codec_results.decompression_results if self.codec_results else None

    def compute_one_row(self, filtered_df, index, loc, column_fun_tuples, overwrite):
        # pylint: disable=too-many-arguments
        # Prepare a new column with a self.CodecRowWrapper instance that
        # allows automatic, lazy computation of compression and decompression
        # results.
        file_path, codec_name = index
        codec = self.codecs_by_name[codec_name]
        image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]

        # A temporary attribute is created with a
        # self.CompressionDecompressionWrapper instance, which allows lazy,
        # at-most-one execution of the compression/decompression process.
        # Column-setting methods can access the wrapper with self.
        try:
            assert self.codec_results is None
        except AttributeError:
            pass
        try:
            self.codec_results = self.CompressionDecompressionWrapper(
                file_path=file_path, codec=codec,
                image_info_row=image_info_row,
                compressed_copy_dir=self.compressed_copy_dir_path or enb.config.options.compressed_copy_dir,
                reconstructed_copy_dir=self.reconstructed_dir_path or enb.config.options.reconstructed_dir)
            assert self.codec_results is not None

            processed_row = super().compute_one_row(
                filtered_df=filtered_df, index=index, loc=loc,
                column_fun_tuples=column_fun_tuples,
                overwrite=overwrite)

            if isinstance(processed_row, Exception):
                # Should not do anything beyond here if errors occurred
                return processed_row
        finally:
            del self.codec_results
            self.codec_results = None

            try:
                del self.codec_results
            except AttributeError:
                pass

        return processed_row

    @enb.atable.column_function("compressed_size_bytes",
                                label="Compressed data size (Bytes)",
                                plot_min=0)
    def set_compressed_data_size(self, index, row):
        row[_column_name] = os.path.getsize(
            self.codec_results.compression_results.compressed_path)

    @enb.atable.column_function([
        enb.atable.ColumnProperties(name="compression_ratio",
                                    label="Compression ratio", plot_min=0),
        enb.atable.ColumnProperties(name="lossless_reconstruction",
                                    label="Lossless?"),
        enb.atable.ColumnProperties(name="compression_time_seconds",
                                    label="Compression time (s)", plot_min=0),
        enb.atable.ColumnProperties(name="decompression_time_seconds",
                                    label="Decompression time (s)", plot_min=0),
        enb.atable.ColumnProperties(name="repetitions",
                                    label="Number of compression/decompression "
                                          "repetitions",
                                    plot_min=0),
        enb.atable.ColumnProperties(name="compressed_file_sha256",
                                    label="Compressed file's SHA256"),
        enb.atable.ColumnProperties(name="compression_memory_kb",
                                    label="Compression memory usage (KB)",
                                    plot_min=0),
        enb.atable.ColumnProperties(name="decompression_memory_kb",
                                    label="Decompression memory usage (KB)",
                                    plot_min=0),
    ])
    def set_comparison_results(self, index, row):
        """Perform a compression-decompression cycle and store the comparison
        results
        """
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]
        assert self.codec_results.compression_results.compressed_path \
               == self.codec_results.decompression_results.compressed_path
        try:
            assert row.image_info_row["bytes_per_sample"] * row.image_info_row["samples"] \
                   == os.path.getsize(self.codec_results.compression_results.original_path)
        except (KeyError, AssertionError) as ex:
            enb.logger.debug(f"Could not verify valid size. {repr(ex)}")
        hasher = hashlib.sha256()
        with open(self.codec_results.compression_results.compressed_path,
                  "rb") as compressed_file:
            hasher.update(compressed_file.read())
        compressed_file_sha256 = hasher.hexdigest()

        row["lossless_reconstruction"] = filecmp.cmp(
            self.codec_results.compression_results.original_path,
            self.codec_results.decompression_results.reconstructed_path)
        assert self.codec_results.compression_results.compression_time_seconds \
               is not None
        row["compression_time_seconds"] = \
            self.codec_results.compression_results.compression_time_seconds
        assert self.codec_results.decompression_results.decompression_time_seconds \
               is not None
        row["decompression_time_seconds"] = \
            self.codec_results.decompression_results.decompression_time_seconds
        row["repetitions"] = options.repetitions
        row["compression_ratio"] = os.path.getsize(
            self.codec_results.compression_results.original_path) \
                                   / row["compressed_size_bytes"]
        row["compressed_file_sha256"] = compressed_file_sha256
        row["compression_memory_kb"] = \
            self.codec_results.compression_results.maximum_memory_kb
        row["decompression_memory_kb"] = \
            self.codec_results.decompression_results.maximum_memory_kb

    @enb.atable.column_function("bpppc", label="Compressed data rate (bpppc)",
                                plot_min=0)
    def set_bpppc(self, index, row):
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]
        try:
            row[_column_name] = 8 * row["compressed_size_bytes"] / \
                                row.image_info_row["samples"]
        except KeyError as ex:
            enb.logger.debug(f"Cannot determine bpppc: {repr(ex)}")
            assert "compressed_size_bytes" in row

    @enb.atable.column_function("compression_ratio_dr",
                                label="Compression ratio",
                                plot_min=0)
    def set_compression_ratio_dr(self, index, row):
        """Set the compression ratio calculated based on the dynamic range of
        the input samples, as opposed to 8*bytes_per_sample.
        """
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]
        row[_column_name] = (row.image_info_row["dynamic_range_bits"] *
                             row.image_info_row["samples"]) \
                            / (8 * row["compressed_size_bytes"])

    @enb.atable.column_function([
        enb.atable.ColumnProperties(
            name=f"compression_efficiency_{B}byte_entropy",
            labytesel=f"Compression efficiency ({B}bytes entropy)",
            plot_min=0, plot_max=B) for B in (1, 2, 4)])
    def set_efficiency(self, index, row):
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]
        for B in (1, 2, 4):
            column_name = f"compression_efficiency_{B}byte_entropy"
            try:
                row[column_name] = \
                    (row.image_info_row[f"entropy_{B}B_bps"]
                     * (row.image_info_row["size_bytes"] / B)
                     / (row["compressed_size_bytes"] * 8))
                if row[column_name] < 0:
                    # The entropy is not known (e.g., size not multiple of B bytes)
                    row[column_name] = -1
            except KeyError as ex:
                enb.logger.warn(
                    f"Could not find a column required to compute "
                    f"{column_name}: {repr(ex)}. "
                    f"Setting to -1. This is likely due to persistence "
                    f"data produced with "
                    f"version v0.4.2 or older of enb. It is recommended "
                    f"to delete persistence "
                    f"data files and re-run the experiment.")
                row[column_name] = -1


class LosslessCompressionExperiment(CompressionExperiment):
    """Lossless data compression experiment. It fails if lossless reconstruction is not achieved.
    """

    @enb.atable.redefines_column
    def set_comparison_results(self, index, row):
        path, task = self.index_to_path_task(index)
        super().set_comparison_results(index=index, row=row)
        if not row["lossless_reconstruction"]:
            raise CompressionException(
                original_path=index[0], file_info=row,
                output="Failed to produce lossless compression for "
                       f"{path} and {task}")


class GenericFilePropertiesTable(enb.isets.ImagePropertiesTable):
    """File properties table that considers the input path as a 1D,
    u8be array.
    """
    verify_file_size = False

    @enb.atable.column_function([
        enb.atable.ColumnProperties(name="unique_sample_count",
                                    label="Number of different sample values"),
        enb.atable.ColumnProperties(name="sample_min",
                                    label="Min sample value (byte samples)"),
        enb.atable.ColumnProperties(name="sample_max",
                                    label="Max sample value (byte samples)")])
    def set_sample_stats(self, file_path, row):
        """Set basic file statistics (unique count, min, max)
        """
        with open(file_path, "rb") as input_file:
            contents = set(input_file.read())
            row["unique_sample_count"] = len(contents)
            row["sample_min"] = min(contents)
            row["sample_max"] = max(contents)

    @enb.atable.column_function("bytes_per_sample",
                                label="Bytes per sample",
                                plot_min=0)
    def set_bytes_per_sample(self, file_path, row):
        row[_column_name] = 1

    @enb.atable.column_function([
        enb.atable.ColumnProperties(name="width", label="Width",
                                    plot_min=1),
        enb.atable.ColumnProperties(name="height", label="Height",
                                    plot_min=1),
        enb.atable.ColumnProperties(name="component_count",
                                    label="Components",
                                    plot_min=1),
        enb.atable.ColumnProperties(name="big_endian"),
        enb.atable.ColumnProperties(name="float"),
    ])
    def set_image_geometry(self, file_path, row):
        """Obtain the image's geometry (width, height and number of
        components) based on the filename tags (and possibly its size)
        """
        row["height"] = 1
        row["width"] = os.path.getsize(file_path)
        row["component_count"] = 1
        row["big_endian"] = True
        row["float"] = False


class GeneralLosslessExperiment(LosslessCompressionExperiment):
    """Lossless compression experiment for general data contents.
    """
    default_file_properties_table_class = GenericFilePropertiesTable
    dataset_files_extension = ""
