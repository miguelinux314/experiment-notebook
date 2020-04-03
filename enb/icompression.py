#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Image compression experiment module
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "01/04/2020"

import filecmp
import hashlib
import os
import tempfile
import time
import collections
import recordclass
import subprocess
import functools
import shutil

import enb
from enb import atable
from enb import experiment
from enb.atable import indices_to_internal_loc
from enb.isets import ImagePropertiesTable
from enb.config import get_options

options = get_options()


class CompressionResults(recordclass.RecordClass):
    """Base class that defines the minimal fields that are returned by a
    call to a coder's compress() method.
    """
    # codec_name: codec's reported_name
    # codec_param_dict: dictionary of parameters to the codec
    # original_path: path to the input original file
    # compressed_path: path to the output compressed file# list of file paths containing side information
    # side_info_files: list of file paths with side information
    # compression_time_seconds: effective compression time in seconds
    codec_name: str = None
    codec_param_dict: dict = None
    original_path: str = None
    compressed_path: str = None
    side_info_files: list = None
    compression_time_seconds: float = None


class DecompressionResults(recordclass.RecordClass):
    """Base class that defines the minimal fields that are returned by a
    call to a coder's decompress() method.
    """
    # codec_name: codec's reported name
    # codec_param_dict: dictionary of parameters to the codec
    # compressed_path: path to the input compressed path
    # reconstructed_path: path to the output reconstructed path
    # side_info_files: list of file paths containing side information
    # decompression_time_seconds: effective decompression time in seconds
    codec_name: str = None
    codec_param_dict: dict = None
    compressed_path: str = None
    reconstructed_path: str = None
    side_info_files: list = []
    decompression_time_seconds: float = None


class CompressionException(Exception):
    """Base class for exceptions occurred during a compression instance
    """

    def __init__(self, original_path=None, compressed_path=None, file_info=None,
                 status=None, output=None):
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
        super().__init__(f"status={status}, output={output}")
        self.reconstructed_path = reconstructed_path
        self.compressed_path = compressed_path
        self.file_info = file_info
        self.status = status
        self.output = output


class AbstractCodec:
    """Base class for all codecs
    """

    def __init__(self, param_dict=None):
        self.param_dict = dict(param_dict) if param_dict is not None else {}

    @property
    def name(self):
        """Name of the codec. Subclasses are expected to yield different values
        when different parameters are used. By default, the class name is folled
        by all elements in self.param_dict sorted alphabetically are included
        in the name."""
        name = f"{self.__class__.__name__}"
        if self.param_dict:
            name += "__" + "_".join(f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name

    @property
    def label(self):
        """Label to be displayed for the codec. May not be strictly unique nor fully informative.
        By default, the original name is returned
        """
        return self.name

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        """Compress original_path into compress_path using param_dict as params.
        :param original_path: path to the original file to be compressed
        :param compressed_path: path to the compressed file to be created
        :param original_file_info: a dict-like object describing original_path's properties
          (e.g., geometry), or None
        :return: (optional) a CompressionResults instance, or None
          (see compression_results_from_paths)
        """
        raise NotImplementedError()

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        """Decompress compressed_path into reconstructed_path using param_dict
        as params (if needed).
        :param compressed_path: path to the input compressed file
        :param reconstructed_path: path to the output reconstructed file
        :param original_file_info: a dict-like object describing original_path's properties
          (e.g., geometry), or None. Should only be actually used in special cases,
          since codecs are expected to store all needed metainformation in the compressed file.
        :return: (optional) a DecompressionResults instance, or None
          (see decompression_results_from_paths)
        """
        raise NotImplementedError()

    def compression_results_from_paths(self, original_path, compressed_path):
        """Get the default CompressionResults instance corresponding to
        the compression of original_path into compressed_path
        """
        return CompressionResults(
            codec_name=self.name,
            codec_param_dict=self.param_dict,
            original_path=original_path,
            compressed_path=compressed_path,
            side_info_files=[],
            compression_time_seconds=None)

    def decompression_results_from_paths(self, compressed_path, reconstructed_path):
        return DecompressionResults(
            codec_name=self.name,
            codec_param_dict=self.param_dict,
            compressed_path=compressed_path,
            reconstructed_path=reconstructed_path,
            side_info_files=[],
            decompression_time_seconds=None)

    @property
    def is_lossless(self):
        """:return True if this codec identifies itself as purely is_lossless.

        """
        raise NotImplementedError()

    def __repr__(self):
        return f"<{self.__class__.__name__}" \
               f"({', '.join(repr(param) + '=' + repr(value) for param, value in self.param_dict.items())})>"


class LosslessCodec(AbstractCodec):
    """A AbstractCodec that identifies itself as purely is_lossless
    """

    @property
    def is_lossless(self):
        return True


class LossyCodec(AbstractCodec):
    """A AbstractCodec that identifies itself as purely is_lossless
    """

    @property
    def is_lossless(self):
        return False


class WrapperCodec(AbstractCodec):
    """A codec that uses an external process to compress and decompress
    :param compressor_path: path to the the executable to be used for compression
    :param decompressor_path: path to the the executable to be used for decompression
    :param param_dict: name-value mapping of the parameters to be used for compression
    """

    def __init__(self, compressor_path, decompressor_path, param_dict=None):
        super().__init__(param_dict=param_dict)
        if os.path.exists(compressor_path):
            self.compressor_path = compressor_path
        else:
            self.compressor_path = shutil.which(compressor_path)
            assert os.path.exists(self.compressor_path), f"{compressor_path} isnot available"
        if os.path.exists(decompressor_path):
            self.decompressor_path = decompressor_path
        else:
            self.decompressor_path = shutil.which(decompressor_path)
            assert os.path.exists(self.decompressor_path), f"{decompressor_path} isnot available"

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

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        compression_params = self.get_compression_params(
            original_path=original_path,
            compressed_path=compressed_path,
            original_file_info=original_file_info)
        status, output = subprocess.getstatusoutput(f"{self.compressor_path} {compression_params}")
        if status != 0:
            if options.verbose:
                print(f"Error compressing {original_path} with {self.name}. "
                      f"Status={status}. Output={output}")
            raise CompressionException(
                original_path=original_path,
                compressed_path=compressed_path,
                file_info=original_file_info,
                status=status,
                output=output)

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        decompression_params = self.get_decompression_params(
            compressed_path=compressed_path,
            reconstructed_path=reconstructed_path,
            original_file_info=original_file_info)
        status, output = subprocess.getstatusoutput(f"{self.decompressor_path} {decompression_params}")
        if status != 0:
            if options.verbose:
                print(f"Error decompressing {original_path} with {self.name}. "
                      f"Status={status}. Output={output}")
            raise DecompressionException(
                compressed_path=compressed_path,
                reconstructed_path=reconstructed_path,
                file_info=original_file_info,
                status=status,
                output=output)

    @staticmethod
    @functools.lru_cache(maxsize=2)
    def get_binary_signature(binary_path):
        """Return a string with a (hopefully) unique signature for
        the contents of binary_path. By default, the first 5 digits
        of the sha-256 hexdigest are returned.
        """
        hasher = hashlib.sha256()
        with open(binary_path, "rb") as open_file:
            hasher.update(open_file.read())
        return hasher.hexdigest()[:5]

    @property
    def name(self):
        """Return the codec's name and parameters, also including the encoder
        and decoder hash summaries (so that changes in the reference binaries
        can be easily detected)
        """
        compressor_signature = self.get_binary_signature(self.compressor_path)
        decompressor_signature = self.get_binary_signature(self.decompressor_path)
        if compressor_signature == decompressor_signature:
            signature = f"{compressor_signature}"
        else:
            signature = f"c{compressor_signature}_d{compressor_signature}"
        name = f"{self.__class__.__name__}_{signature}"
        if self.param_dict:
            name += "__" + "_".join(f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name


class LosslessCompressionExperiment(experiment.Experiment):
    def __init__(self, codecs,
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table: enb.isets.ImagePropertiesTable = None,
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
        table_class = type(dataset_info_table) if dataset_info_table is not None \
            else enb.isets.ImagePropertiesTable
        csv_dataset_path = csv_dataset_path if csv_dataset_path is not None \
            else os.path.join(options.persistence_dir, f"{table_class.__name__}_persistence.csv")
        imageinfo_table = dataset_info_table if dataset_info_table is not None \
            else table_class(csv_support_path=csv_dataset_path)

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


class LosslessCompressionExperiment(LosslessCompressionExperiment):

    @LosslessCompressionExperiment.column_function([
        atable.ColumnProperties(name="compression_ratio", label="Compression ratio", plot_min=0),
        atable.ColumnProperties(name="compression_efficiency_1byte_entropy",
                                label="Compression efficiency (1B entropy)", plot_min=0),
        atable.ColumnProperties(name="lossless_reconstruction", label="Lossless?"),
        atable.ColumnProperties(name="compression_time_seconds", label="Compression time (s)", plot_min=0),
        atable.ColumnProperties(name="decompression_time_seconds", label="Decompression time (s)", plot_min=0),
        atable.ColumnProperties(name="compressed_size_bytes", label="Compressed size (bytes)", plot_min=0),
        atable.ColumnProperties(name="compressed_file_sha256", label="Compressed file's SHA256")
    ])
    def set_comparison_results(self, index, file_info):
        """Perform a compression-decompression cycle and store the comparison results
        """
        original_file_path, codec_name = index
        if not os.path.isfile(original_file_path):
            raise CompressionException(original_path=original_file_path, compressed_path=None,
                                       file_info=file_info, output=f"File not found: {original_file_path}")

        image_info_series = self.dataset_table_df.loc[indices_to_internal_loc(original_file_path)]
        codec = self.codecs_by_name[codec_name]
        with tempfile.NamedTemporaryFile(mode="w", dir=options.base_tmp_dir) \
                as compressed_file, tempfile.NamedTemporaryFile(mode="w", dir=options.base_tmp_dir) \
                as reconstructed_file:
            if options.verbose > 1:
                print(f"[E]xecuting compression {codec.name} on {index}")
            time_before = time.process_time()
            cr = codec.compress(original_path=original_file_path,
                                compressed_path=compressed_file.name,
                                original_file_info=image_info_series)
            if not os.path.isfile(compressed_file.name) or os.path.getsize(compressed_file.name) == 0:
                raise CompressionException(
                    original_path=original_file_path, compressed_path=compressed_file.name,
                    file_info=file_info,
                    output=f"Compression didn't produce a file (or it was empty) {original_file_path}")

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
            if not os.path.isfile(reconstructed_file.name) or os.path.getsize(compressed_file.name) == 0:
                raise CompressionException(
                    original_path=original_file_path, compressed_path=compressed_file.name,
                    file_info=file_info,
                    output=f"Decompression didn't produce a file (or it was empty) {original_file_path}")
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

            file_info["lossless_reconstruction"] = filecmp.cmp(cr.original_path, dr.reconstructed_path)
            file_info["compression_efficiency_1byte_entropy"] = compression_efficiency_1byte_entropy
            file_info["compressed_size_bytes"] = os.path.getsize(cr.compressed_path)
            file_info["compression_time_seconds"] = cr.compression_time_seconds \
                if cr.compression_time_seconds is not None \
                else process_compression_time
            file_info["decompression_time_seconds"] = dr.decompression_time_seconds \
                if dr.decompression_time_seconds is not None \
                else process_decompression_time
            file_info["compression_ratio"] = os.path.getsize(cr.original_path) / os.path.getsize(cr.compressed_path)
            file_info["compressed_file_sha256"] = compressed_file_sha256

            if not file_info["lossless_reconstruction"]:
                raise CompressionException(
                    original_path=original_file_path,
                    file_info=file_info,
                    output="Failed to produce lossless compression for "
                           f"{original_file_path} and {codec.name}")
