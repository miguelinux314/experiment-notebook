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
import functools
import shutil
import math
import numpy as np
import imageio
import subprocess
import numpngw

import enb
from enb import atable
from enb import experiment
from enb import isets
from enb import tcall
from enb.atable import indices_to_internal_loc
from enb.config import get_options

options = get_options()


class CompressionResults(recordclass.RecordClass):
    """Base class that defines the minimal fields that are returned by a
    call to a coder's compress() method (or produced by
    the CompressionExperiment instance)
    """
    # codec_name: codec's reported_name
    # codec_param_dict: dictionary of parameters to the codec
    # original_path: path to the input original file
    # compressed_path: path to the output compressed file# list of file paths containing side information
    # side_info_files: list of file paths with side information
    # compression_time_seconds: effective average compression time in seconds
    codec_name: str = None
    codec_param_dict: dict = None
    original_path: str = None
    compressed_path: str = None
    side_info_files: list = None
    compression_time_seconds: float = None


class DecompressionResults(recordclass.RecordClass):
    """Base class that defines the minimal fields that are returned by a
    call to a coder's decompress() method (or produced by
    the CompressionExperiment instance)
    """
    # codec_name: codec's reported name
    # codec_param_dict: dictionary of parameters to the codec
    # compressed_path: path to the input compressed path
    # reconstructed_path: path to the output reconstructed path
    # side_info_files: list of file paths containing side information
    # decompression_time_seconds: effective average decompression time in seconds
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


class AbstractCodec(experiment.ExperimentTask):
    """Base class for all codecs
    """

    def __init__(self, param_dict=None):
        super().__init__(param_dict=param_dict)

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

    @property
    def label_with_params(self):
        return self.label + " " + ", ".join(f"{enb.aanalysis.clean_column_name(k)}"
                                            f"={self.param_dict[k]}"
                                            for k in sorted(self.param_dict.keys()))

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        """Compress original_path into compress_path using param_dict as params.
        :param original_path: path to the original file to be compressed
        :param compressed_path: path to the compressed file to be created
        :param original_file_info: a dict-like object describing original_path's properties (e.g., geometry), or None.
        :return: (optional) a CompressionResults instance, or None (see compression_results_from_paths)
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
        :return: (optional) a DecompressionResults instance, or None (see decompression_results_from_paths)
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

    def __repr__(self):
        return f"<{self.__class__.__name__}" \
               f"({', '.join(repr(param) + '=' + repr(value) for param, value in self.param_dict.items())})>"


class LosslessCodec(AbstractCodec):
    """A AbstractCodec that identifies itself as lossless
    """
    pass


class LossyCodec(AbstractCodec):
    """A AbstractCodec that identifies itself as lossy
    """
    pass


class NearLosslessCodec(LossyCodec):
    pass


class WrapperCodec(AbstractCodec):
    """A codec that uses an external process to compress and decompress.

    :param compressor_path: path to the the executable to be used for compression
    :param decompressor_path: path to the the executable to be used for decompression
    :param param_dict: name-value mapping of the parameters to be used for compression
    :param output_invocation_dir: if not None, invocation strings are stored in this directory
      with name based on the codec and the image's full path.

    """

    def __init__(self, compressor_path, decompressor_path, param_dict=None, output_invocation_dir=None):
        super().__init__(param_dict=param_dict)
        if os.path.isfile(compressor_path) and os.access(compressor_path, os.EX_OK):
            self.compressor_path = compressor_path
        else:
            self.compressor_path = shutil.which(compressor_path)
            assert os.path.isfile(self.compressor_path), f"{compressor_path} isnot available"
        if os.path.exists(decompressor_path) and os.access(decompressor_path, os.EX_OK):
            self.decompressor_path = decompressor_path
        else:
            self.decompressor_path = shutil.which(decompressor_path)
            assert os.path.isfile(self.decompressor_path), f"{decompressor_path} isnot available"
        self.output_invocation_dir = output_invocation_dir
        if self.output_invocation_dir is not None:
            os.makedirs(self.output_invocation_dir, exist_ok=True)

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
        invocation = f"{self.compressor_path} {compression_params}"
        try:
            status, output, measured_time = tcall.get_status_output_time(invocation=invocation)
            if options.verbose > 3:
                print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
        except tcall.InvocationError as ex:
            raise CompressionException(
                original_path=original_path,
                compressed_path=compressed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        compression_results = self.compression_results_from_paths(
            original_path=original_path, compressed_path=compressed_path)
        compression_results.compression_time_seconds = measured_time

        if self.output_invocation_dir is not None:
            invocation_name = "invocation_compression_" \
                              + self.name \
                              + os.path.abspath(os.path.realpath(original_file_info["file_path"])).replace(os.sep, "_")
            with open(os.path.join(self.output_invocation_dir, invocation_name), "w") as invocation_file:
                invocation_file.write(f"Original path: {original_path}\n"
                                      f"Compressed path: {compressed_path}\n"
                                      f"Codec: {self.name}\n"
                                      f"Invocation: {invocation}\n"
                                      f"Status: {status}\n"
                                      f"Output: {output}\n"
                                      f"Measured time: {measured_time}")

        return compression_results

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        decompression_params = self.get_decompression_params(
            compressed_path=compressed_path,
            reconstructed_path=reconstructed_path,
            original_file_info=original_file_info)
        invocation = f"{self.decompressor_path} {decompression_params}"
        try:
            status, output, measured_time = tcall.get_status_output_time(invocation)
            if options.verbose > 3:
                print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
        except tcall.InvocationError as ex:
            raise DecompressionException(
                compressed_path=compressed_path,
                reconstructed_path=reconstructed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        decompression_results = self.decompression_results_from_paths(
            compressed_path=compressed_path, reconstructed_path=reconstructed_path)

        decompression_results.decompression_time_seconds = measured_time

        if self.output_invocation_dir is not None:
            invocation_name = "invocation_decompression_" \
                              + self.name \
                              + os.path.abspath(os.path.realpath(
                original_file_info["file_path"] if original_file_info is not None else compressed_path)).replace(os.sep,
                                                                                                                 "_")
            with open(os.path.join(self.output_invocation_dir, invocation_name), "w") as invocation_file:
                invocation_file.write(f"Compressed path: {compressed_path}\n"
                                      f"Reconstructed path: {reconstructed_path}\n"
                                      f"Codec: {self.name}\n"
                                      f"Invocation: {invocation}\n"
                                      f"Status: {status}\n"
                                      f"Output: {output}\n"
                                      f"Measured time: {measured_time}")

        return decompression_results

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


class PNGWrapperCodec(WrapperCodec):
    """Raw images are coded into PNG before compression with the wrapper,
    and PNG is decoded to raw after decompression.
    """
    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        img = enb.isets.load_array_bsq(
            file_or_path=original_path, image_properties_row=original_file_info)
        
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
            numpngw.write_png(tmp_file.name, img)
            compression_results = super().compress(original_path=tmp_file.name,
                             compressed_path=compressed_path,
                             original_file_info=original_file_info)
            cr = self.compression_results_from_paths(
                original_path=original_path, compressed_path=compressed_path)
            cr.compression_time_seconds = max(
                0, compression_results.compression_time_seconds)
            return cr

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
            decompression_results = super().decompress(
                compressed_path=compressed_path, reconstructed_path=tmp_file.name)
            img = imageio.imread(tmp_file.name, "png")
            img.swapaxes(0, 1)
            assert len(img.shape) in [2, 3, 4]
            if len(img.shape) == 2:
                img = np.expand_dims(img, axis=2)
            enb.isets.dump_array_bsq(img, file_or_path=reconstructed_path)

            dr = self.decompression_results_from_paths(
                compressed_path=compressed_path, reconstructed_path=reconstructed_path)
            dr.decompression_time_seconds = decompression_results.decompression_time_seconds

class PGMWrapperCodec(WrapperCodec):
    """Raw images are coded into PNG before compression with the wrapper,
    and PNG is decoded to raw after decompression.
    """
    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        assert original_file_info["component_count"] == 1, "PGM only supported for 1-component images"
        assert original_file_info["bytes_per_sample"] in [1,2], "PGM only supported for 8 or 16 bit images"
        img = enb.isets.load_array_bsq(
            file_or_path=original_path, image_properties_row=original_file_info)

        with tempfile.NamedTemporaryFile(suffix=".pgm", mode="wb") as tmp_file:
            imageio.imwrite(tmp_file.name, img)
            with open(tmp_file, "rb") as raw_file:
                 contents = raw_file.read()
            os.remove(tmp_file)
            with open(tmp_file, "wb") as pgm_file:
                tmp_file.write(bytes(f"P6\n"
                                     f"{original_file_info['width']} {original_file_info['height']}\n"
                                     f"{255 if original_file_info['bytes_per_sample'] == 1 else 65535}\n"))
                tmp_file.write(contents)


            compression_results = super().compress(original_path=tmp_file.name,
                             compressed_path=compressed_path,
                             original_file_info=original_file_info)
            cr = self.compression_results_from_paths(
                original_path=original_path, compressed_path=compressed_path)
            cr.compression_time_seconds = max(
                0, compression_results.compression_time_seconds)
            return cr

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with tempfile.NamedTemporaryFile(suffix=".pgm") as tmp_file:
            decompression_results = super().decompress(
                compressed_path=compressed_path, reconstructed_path=tmp_file.name)
            img = imageio.imread(tmp_file.name, "pgm")
            img.swapaxes(0, 1)
            assert len(img.shape) in [2, 3, 4]
            if len(img.shape) == 2:
                img = np.expand_dims(img, axis=2)
            enb.isets.dump_array_bsq(img, file_or_path=reconstructed_path)

            dr = self.decompression_results_from_paths(
                compressed_path=compressed_path, reconstructed_path=reconstructed_path)
            dr.decompression_time_seconds = decompression_results.decompression_time_seconds


class CompressionExperiment(experiment.Experiment):
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
    default_file_properties_table_class = enb.isets.ImagePropertiesTable
    check_lossless = True

    class RowWrapper:
        """Rows passed as arguments to the table column functions of CompressionExperiment
        subclasses are of this type. This allows accessing the compression_results and
        decompression_results properties (see the CompressionResults and DecompressionResults classes), 
        which automatically compress and decompress
        the image with the appropriate codec. Row names are set and retrieved normally
        with a dict-like syntax.
        """

        def __init__(self, file_path, codec, image_info_row, row):
            self.file_path = file_path
            self.codec = codec
            self.image_info_row = image_info_row
            self.row = row
            self._compression_results = None
            self._decompression_results = None

        @property
        def compression_results(self):
            """Perform the actual compression experiment for the selected row.
            """
            if self._compression_results is None:
                _, tmp_compressed_path = tempfile.mkstemp(
                    dir=options.base_tmp_dir,
                    prefix=f"compressed_{os.path.basename(self.file_path)}_")
                try:
                    measured_times = []

                    if options.verbose > 1:
                        print(f"[E]xecuting compression {self.codec.name} on {self.file_path} "
                              f"[{options.repetitions} times]")
                    for repetition_index in range(options.repetitions):
                        if options.verbose > 2:
                            print(f"[E]xecuting compression {self.codec.name} on {self.file_path} "
                                  f"[rep{repetition_index + 1}/{options.repetitions}]")
                        time_before = time.time()
                        self._compression_results = self.codec.compress(original_path=self.file_path,
                                                                        compressed_path=tmp_compressed_path,
                                                                        original_file_info=self.image_info_row)

                        if not os.path.isfile(tmp_compressed_path) \
                                or os.path.getsize(tmp_compressed_path) == 0:
                            raise CompressionException(
                                original_path=self.file_path, compressed_path=tmp_compressed_path,
                                file_info=self.image_info_row,
                                output=f"Compression didn't produce a file (or it was empty) {self.file_path}")

                        wall_compression_time = time.time() - time_before
                        if self._compression_results is None:
                            if options.verbose > 2:
                                print(f"[W]arning: codec {self.codec.name} did not report execution times. "
                                      f"Using wall clock instead (might be inaccurate)")
                            self._compression_results = self.codec.compression_results_from_paths(
                                original_path=self.file_path, compressed_path=tmp_compressed_path)
                            self._compression_results.compression_time_seconds = wall_compression_time

                        measured_times.append(self._compression_results.compression_time_seconds)
                        if repetition_index < options.repetitions - 1:
                            os.remove(tmp_compressed_path)

                    self._compression_results.compression_time_seconds = sum(measured_times) / len(measured_times)
                except Exception as ex:
                    os.remove(tmp_compressed_path)
                    raise ex

            return self._compression_results

        @property
        def decompression_results(self):
            """Perform the actual decompression experiment for the selected row.
            """
            if self._decompression_results is None:
                _, tmp_reconstructed_path = tempfile.mkstemp(
                    prefix=f"reconstructed_{os.path.basename(self.file_path)}",
                    dir=options.base_tmp_dir)
                try:
                    measured_times = []
                    if options.verbose > 1:
                        print(f"[E]xecuting decompression {self.codec.name} on {self.file_path} "
                              f"[{options.repetitions} times]")
                    for repetition_index in range(options.repetitions):
                        if options.verbose > 2:
                            print(f"[E]xecuting decompression {self.codec.name} on {self.file_path} "
                                  f"[rep{repetition_index + 1}/{options.repetitions}]")

                        time_before = time.time()
                        self._decompression_results = self.codec.decompress(
                            compressed_path=self.compression_results.compressed_path,
                            reconstructed_path=tmp_reconstructed_path,
                            original_file_info=self.image_info_row)

                        wall_decompression_time = time.time() - time_before
                        if self._decompression_results is None:
                            if options.verbose > 2:
                                print(f"[W]arning: codec {self.codec.name} did not report execution times. "
                                      f"Using wall clock instead (might be inaccurate)")
                            self._decompression_results = self.codec.decompression_results_from_paths(
                                compressed_path=self.compression_results.compressed_path,
                                reconstructed_path=tmp_reconstructed_path)
                            self._decompression_results.decompression_time_seconds = wall_decompression_time

                        if not os.path.isfile(tmp_reconstructed_path) or os.path.getsize(
                                self._decompression_results.reconstructed_path) == 0:
                            raise CompressionException(
                                original_path=self.compression_results.file_path,
                                compressed_path=self.compression_results.compressed_path,
                                file_info=self.image_info_row,
                                output=f"Decompression didn't produce a file (or it was empty)"
                                       f" {self.compression_results.file_path}")

                        measured_times.append(self._decompression_results.decompression_time_seconds)
                        if repetition_index < options.repetitions - 1:
                            os.remove(tmp_reconstructed_path)
                    self._decompression_results.decompression_time_seconds = sum(measured_times) / len(measured_times)
                except Exception as ex:
                    os.remove(tmp_reconstructed_path)
                    raise ex

            return self._decompression_results

        @property
        def numpy_dtype(self):
            """Get the numpy dtype corresponding to the original image's data format
            """
            return isets.iproperties_row_to_numpy_dtype(self.image_info_row)

        def __getitem__(self, item):
            return self.row[item]

        def __setitem__(self, key, value):
            self.row[key] = value

        def __delitem__(self, key):
            del self.row[key]

        def __contains__(self, item):
            return item in self.row

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
                 parallel_dataset_property_processing=None,
                 reconstructed_dir_path=None,
                 compressed_copy_dir_path=None):
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
        :param parallel_dataset_property_processing: if not None, it determines whether file properties
          are to be obtained in parallel. If None, it is given by not options.sequential.
        :param reconstructed_dir_path: if not None, a directory where reconstructed images are
          to be stored.
        :param compressed_copy_dir_path: if not None, it gives the directory where a copy of the compressed images.
          is to be stored. If may not be generated for images for which all columns are known
        """
        table_class = type(dataset_info_table) if dataset_info_table is not None \
            else self.default_file_properties_table_class
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
        self.reconstructed_dir_path = reconstructed_dir_path
        self.compressed_copy_dir_path = compressed_copy_dir_path

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

    def process_row(self, index, column_fun_tuples, row, overwrite, fill):
        file_path, codec_name = index
        codec = self.codecs_by_name[codec_name]
        image_info_row = self.dataset_table_df.loc[indices_to_internal_loc(file_path)]
        row_wrapper = self.RowWrapper(
            file_path=file_path, codec=codec,
            image_info_row=image_info_row,
            row=row)
        result = super().process_row(index=index, column_fun_tuples=column_fun_tuples,
                                     row=row_wrapper, overwrite=overwrite, fill=fill)

        if isinstance(result, Exception):
            return result

        if self.compressed_copy_dir_path:
            output_compressed_path = os.path.join(
                self.compressed_copy_dir_path,
                codec.name,
                os.path.basename(os.path.dirname(file_path)), os.path.basename(file_path))
            os.makedirs(os.path.dirname(output_compressed_path), exist_ok=True)
            if options.verbose > 1:
                print(f"[C]opying {file_path} into {output_compressed_path}")
            shutil.copy(row_wrapper.compression_results.compressed_path, output_compressed_path)

        if self.reconstructed_dir_path is not None:
            output_reconstructed_path = os.path.join(
                self.reconstructed_dir_path,
                codec.name,
                os.path.basename(os.path.dirname(file_path)), os.path.basename(file_path))
            os.makedirs(os.path.dirname(output_reconstructed_path), exist_ok=True)
            if options.verbose > 1:
                print(f"[C]opying {row_wrapper.compression_results.compressed_path} into {output_reconstructed_path}")
            shutil.copy(row_wrapper.decompression_results.reconstructed_path,
                        output_reconstructed_path)

            if image_info_row["component_count"] == 3:
                rendered_path = f"{output_reconstructed_path}.png"
                if not os.path.exists(rendered_path) or options.force:
                    array = isets.load_array_bsq(file_or_path=row_wrapper.decompression_results.reconstructed_path,
                                                 image_properties_row=image_info_row).astype(np.int)
                    if options.reconstructed_size is not None:
                        width, height, _ = array.shape
                        array = array[
                                width // 2 - options.reconstructed_size // 2:width // 2 + options.reconstructed_size // 2,
                                height // 2 - options.reconstructed_size // 2:height // 2 + options.reconstructed_size // 2,
                                :]
                    cmin = array.min()
                    cmax = array.max()
                    array = np.round((255 * (array.astype(np.int) - cmin) / (cmax - cmin))).astype("uint8")
                    if options.verbose > 1:
                        print(f"[R]endering {rendered_path}")

                    imageio.imwrite(rendered_path, array.swapaxes(0, 1))

            else:
                full_array = isets.load_array_bsq(
                    file_or_path=row_wrapper.decompression_results.reconstructed_path,
                    image_properties_row=image_info_row).astype(np.int)
                if options.reconstructed_size is not None:
                    width, height, _ = full_array.shape
                    full_array = full_array[
                                 width // 2 - options.reconstructed_size // 2:width // 2 + options.reconstructed_size // 2,
                                 height // 2 - options.reconstructed_size // 2:height // 2 + options.reconstructed_size // 2,
                                 :]
                for i, rendered_path in enumerate(f"{output_reconstructed_path}_component{i}.png"
                                                  for i in range(image_info_row['component_count'])):
                    if not os.path.exists(rendered_path) or options.force:
                        array = full_array[:, :, i].squeeze().swapaxes(0, 1)
                        cmin = array.min()
                        cmax = array.max()
                        array = np.round((255 * (array - cmin) / (cmax - cmin))).astype("uint8")
                        if options.verbose > 1:
                            print(f"[R]endering {rendered_path}")
                        imageio.imwrite(rendered_path, array)

        return row

    @atable.column_function("compressed_size_bytes", label="Compressed data size (Bytes)", plot_min=0)
    def set_compressed_data_size(self, index, row):
        row[_column_name] = os.path.getsize(row.compression_results.compressed_path)

    @atable.column_function([
        atable.ColumnProperties(name="compression_ratio", label="Compression ratio", plot_min=0),
        atable.ColumnProperties(name="lossless_reconstruction", label="Lossless?"),
        atable.ColumnProperties(name="compression_time_seconds", label="Compression time (s)", plot_min=0),
        atable.ColumnProperties(name="decompression_time_seconds", label="Decompression time (s)", plot_min=0),
        atable.ColumnProperties(name="repetitions", label="Number of compression/decompression repetitions",
                                plot_min=0),
        atable.ColumnProperties(name="compressed_file_sha256", label="Compressed file's SHA256")
    ])
    def set_comparison_results(self, index, row):
        """Perform a compression-decompression cycle and store the comparison results
        """
        file_path, codec_name = index
        row.image_info_row = self.dataset_table_df.loc[indices_to_internal_loc(file_path)]
        assert row.compression_results.compressed_path == row.decompression_results.compressed_path
        assert row.image_info_row["bytes_per_sample"] * row.image_info_row["samples"] \
               == os.path.getsize(row.compression_results.original_path)
        hasher = hashlib.sha256()
        with open(row.compression_results.compressed_path, "rb") as compressed_file:
            hasher.update(compressed_file.read())
        compressed_file_sha256 = hasher.hexdigest()

        row["lossless_reconstruction"] = filecmp.cmp(row.compression_results.original_path,
                                                     row.decompression_results.reconstructed_path)
        assert row.compression_results.compression_time_seconds is not None
        row["compression_time_seconds"] = row.compression_results.compression_time_seconds
        assert row.decompression_results.decompression_time_seconds is not None
        row["decompression_time_seconds"] = row.decompression_results.decompression_time_seconds
        row["repetitions"] = options.repetitions
        row["compression_ratio"] = os.path.getsize(row.compression_results.original_path) / row["compressed_size_bytes"]
        row["compressed_file_sha256"] = compressed_file_sha256

    @atable.column_function("bpppc", label="Compressed data rate (bpppc)", plot_min=0)
    def set_bpppc(self, index, row):
        row[_column_name] = 8 * row["compressed_size_bytes"] / row.image_info_row["samples"]

    @atable.column_function("compression_ratio_dr", label="Compression ratio", plot_min=0)
    def set_compression_ratio_dr(self, index, row):
        """Set the compression ratio calculated based on the dynamic range of the
        input samples, as opposed to 8*bytes_per_sample.
        """
        row[_column_name] = (row.image_info_row["dynamic_range_bits"] * row.image_info_row["samples"]) \
                            / (8 * row["compressed_size_bytes"])

    @atable.column_function(
        [atable.ColumnProperties(name="compression_efficiency_1byte_entropy",
                                 label="Compression efficiency (1B entropy)", plot_min=0),
         atable.ColumnProperties(name="compression_efficiency_2byte_entropy",
                                 label="Compression efficiency (2B entropy)", plot_min=0)])
    def set_efficiency(self, index, row):
        compression_efficiency_1byte_entropy = \
            row.image_info_row["entropy_1B_bps"] * row.image_info_row["size_bytes"] \
            / (row["compressed_size_bytes"] * 8)
        compression_efficiency_2byte_entropy = \
            row.image_info_row["entropy_2B_bps"] * (row.image_info_row["size_bytes"] / 2) \
            / (row["compressed_size_bytes"] * 8)
        row["compression_efficiency_1byte_entropy"] = compression_efficiency_1byte_entropy
        row["compression_efficiency_2byte_entropy"] = compression_efficiency_2byte_entropy


class LosslessCompressionExperiment(CompressionExperiment):
    @atable.redefines_column
    def set_comparison_results(self, index, row):
        super().set_comparison_results(index=index, row=row)
        if not row["lossless_reconstruction"]:
            raise CompressionException(
                original_path=index[0], file_info=row,
                output="Failed to produce lossless compression for "
                       f"{index[0]} and {index[1]}")


class LossyCompressionExperiment(CompressionExperiment):
    @atable.column_function("mse", label="MSE", plot_min=0)
    def set_MSE(self, index, row):
        """Set the mean squared error of the reconstructed image.
        """
        original_array = np.fromfile(row.compression_results.original_path,
                                     dtype=row.numpy_dtype).astype(np.int64)

        reconstructed_array = np.fromfile(row.decompression_results.reconstructed_path,
                                          dtype=row.numpy_dtype).astype(np.int64)
        row[_column_name] = np.average(((original_array - reconstructed_array) ** 2))

    @atable.column_function("pae", label="PAE", plot_min=0)
    def set_PAE(self, index, row):
        """Set the peak absolute error (maximum absolute pixelwise difference)
        of the reconstructed image.
        """
        original_array = np.fromfile(row.compression_results.original_path,
                                     dtype=row.numpy_dtype).astype(np.int64)

        reconstructed_array = np.fromfile(row.decompression_results.reconstructed_path,
                                          dtype=row.numpy_dtype).astype(np.int64)
        row[_column_name] = np.max(np.abs(original_array - reconstructed_array))

    @atable.column_function("psnr_bps", label="PSNR (dB)", plot_min=0)
    def set_PSNR_nominal(self, index, row):
        """Set the PSNR assuming nominal dynamic range given by bytes_per_sample.
        """
        max_error = (2 ** (8 * row.image_info_row["bytes_per_sample"])) - 1
        row[_column_name] = 10 * math.log10((max_error ** 2) / row["mse"]) \
            if row["mse"] > 0 else float("inf")

    @atable.column_function("psnr_dr", label="PSNR (dB)", plot_min=0)
    def set_PSNR_dynamic_range(self, index, row):
        """Set the PSNR assuming dynamic range given by dynamic_range_bits.
        """
        max_error = (2 ** row.image_info_row["dynamic_range_bits"]) - 1
        row[_column_name] = 10 * math.log10((max_error ** 2) / row["mse"]) \
            if row["mse"] > 0 else float("inf")


class SpectralAngleTable(LossyCompressionExperiment):
    """Lossy compression experiment that computes spectral angle "distance" 
    measures between the compressed and the reconstructed images.
    
    Subclasses of LossyCompressionExperiment may inherit from this one to
    automatically add the data columns defined here
    """

    def get_spectral_angles_deg(self, index, row):
        """Return a sequence of spectral angles (in degrees), 
        one per (x,y) position in the image, flattened in raster order.
        """
        # Read original and reconstructed images
        original_file_path, task_name = index
        image_properties_row = self.get_dataset_info_row(original_file_path)
        decompression_results = row.decompression_results
        original_array = isets.load_array_bsq(
            file_or_path=original_file_path, image_properties_row=image_properties_row)
        reconstructed_array = isets.load_array_bsq(
            file_or_path=decompression_results.reconstructed_path, image_properties_row=image_properties_row)

        # Reshape flattening the x,y axes, and maintaining the z axis for each (x,y) position
        original_array = np.reshape(
            original_array.swapaxes(0, 1),
            (image_properties_row["width"] * image_properties_row["height"], image_properties_row["component_count"]),
            "F").astype("i8")
        reconstructed_array = np.reshape(
            reconstructed_array.swapaxes(0, 1),
            (image_properties_row["width"] * image_properties_row["height"], image_properties_row["component_count"]),
            "F").astype("i8")

        dots = np.einsum("ij,ij->i", original_array, reconstructed_array)
        magnitude_a = np.linalg.norm(original_array, axis=1)
        magnitude_b = np.linalg.norm(reconstructed_array, axis=1)

        for i in range(magnitude_a.shape[0]):
            # Avoid division by zero
            magnitude_a[i] = max(1e-4, magnitude_a[i])
            magnitude_b[i] = max(1e-4, magnitude_b[i])

        # Clip, because the dot product can slip past 1 or -1 due to rounding
        cosines = np.clip(dots / (magnitude_a * magnitude_b), -1, 1)
        angles = np.degrees(np.arccos(cosines))
        # Round because two identical images should return an angle of exactly 0
        angles = np.round(angles, 5)

        return angles.tolist()

    @atable.column_function([
        enb.atable.ColumnProperties("mean_spectral_angle_deg", label="Mean spectral angle (deg)",
                                    plot_min=0, plot_max=None),
        enb.atable.ColumnProperties("max_spectral_angle_deg", label="Max spectral angle (deg)",
                                    plot_min=0, plot_max=None)])
    def set_spectral_distances(self, index, row):
        spectral_angles = self.get_spectral_angles_deg(index=index, row=row)

        for angle in spectral_angles:
            assert not np.isnan(angle), f"Error calculating an angle for {index}: {angle}"

        row["mean_spectral_angle_deg"] = sum(spectral_angles) / len(spectral_angles)
        row["max_spectral_angle_deg"] = max(spectral_angles)
