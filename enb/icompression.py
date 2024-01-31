#!/usr/bin/env python3
"""Image compression experiment module.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/01"

import filecmp
import hashlib
import os
import tempfile
import time
import collections
import functools
import shutil
import math
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
                 compressed_path=None, side_info_files=None,
                 compression_time_seconds=None,
                 maximum_memory_kb=None):
        """
        :param codec_name: codec's reported_name
        :param codec_param_dict: dictionary of parameters to the codec
        :param original_path: path to the input original file
        :param compressed_path: path to the output compressed file
        :param side_info_files: list of file paths with side information
        :param compression_time_seconds: effective average compression time in
          seconds
        :param maximum_memory_kb: maximum resident memory in kilobytes
        """
        # pylint: disable=too-many-arguments
        side_info_files = side_info_files \
            if side_info_files is not None else []

        self.codec_name = codec_name
        self.codec_param_dict = codec_param_dict
        self.original_path = original_path
        self.compressed_path = compressed_path
        self.side_info_files = list(side_info_files)
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
                 reconstructed_path=None, side_info_files=None,
                 decompression_time_seconds=None,
                 maximum_memory_kb=None):
        """
        :param codec_name: codec's reported_name
        :param codec_param_dict: dictionary of parameters to the codec
        :param compressed_path: path to the output compressed file
        :param reconstructed_path: path to the reconstructed file after
          decompression
        :param side_info_files: list of file paths with side information
        :param decompression_time_seconds: effective decompression time in
          seconds
        :param maximum_memory_kb: maximum resident memory in kilobytes
        """
        # pylint: disable=too-many-arguments
        side_info_files = side_info_files \
            if side_info_files is not None else []
        self.codec_name = codec_name
        self.codec_param_dict = codec_param_dict
        self.compressed_path = compressed_path
        self.reconstructed_path = reconstructed_path
        self.side_info_files = side_info_files
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


class AbstractCodec(enb.experiment.ExperimentTask):
    """Base class for all codecs
    """

    def __init__(self, param_dict=None):
        super().__init__(param_dict=param_dict)

    @property
    def name(self):
        """Name of the codec. Subclasses are expected to yield different
        values when different parameters are used. By default, the class name
        is folled by all elements in self.param_dict sorted alphabetically
        are included in the name.
        """
        name = f"{self.__class__.__name__}"
        if self.param_dict:
            name += "__" + "_".join(
                f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name

    @property
    def label(self):
        """Label to be displayed for the codec. May not be strictly unique
        nor fully informative. By default, self's class name is returned.
        """
        return self.__class__.__name__

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        """Compress original_path into compress_path using param_dict as params.
        :param original_path: path to the original file to be compressed
        :param compressed_path: path to the compressed file to be created
        :param original_file_info: a dict-like object describing
          original_path's properties (e.g., geometry), or None.
        :return: (optional) a CompressionResults instance, or None
          (see compression_results_from_paths)
        """
        raise NotImplementedError()

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        """Decompress compressed_path into reconstructed_path using param_dict
        as params (if needed).

        :param compressed_path: path to the input compressed file
        :param reconstructed_path: path to the output reconstructed file
        :param original_file_info: a dict-like object describing
          original_path's properties (e.g., geometry), or None. Should only be
          actually used in special cases, since codecs are expected to store
          all needed metainformation in the compressed file.
        :return: (optional) a DecompressionResults instance, or None (see
        decompression_results_from_paths)
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

    def decompression_results_from_paths(
            self, compressed_path, reconstructed_path):
        """Return a enb.icompression.DecompressionResults instance given
        the compressed and reconstructed paths.
        """
        return DecompressionResults(
            codec_name=self.name,
            codec_param_dict=self.param_dict,
            compressed_path=compressed_path,
            reconstructed_path=reconstructed_path,
            side_info_files=[],
            decompression_time_seconds=None)

    def __repr__(self):
        return f"<{self.__class__.__name__}(" \
            + ', '.join(repr(param) + '=' + repr(value)
                        for param, value in self.param_dict.items()) \
            + ")>"


class LosslessCodec(AbstractCodec):  # pylint: disable=abstract-method
    """An AbstractCodec that identifies itself as lossless.
    """


class LossyCodec(AbstractCodec):  # pylint: disable=abstract-method
    """An AbstractCodec that identifies itself as lossy.
    """


class NearLosslessCodec(LossyCodec):  # pylint: disable=abstract-method
    """An AbstractCodec that identifies itself as near lossless.
    """


class WrapperCodec(AbstractCodec):
    """A codec that uses an external process to compress and decompress.
    """

    def __init__(self, compressor_path, decompressor_path, param_dict=None,
                 output_invocation_dir=None,
                 signature_in_name=False):
        """
        :param compressor_path: path to the executable to be used for
          compression
        :param decompressor_path: path to the executable to be used for
          decompression
        :param param_dict: name-value mapping of the parameters to be used
          for compression
        :param output_invocation_dir: if not None, invocation strings are
          stored in this directory with name based on the codec and the image's
          full path.
        :pram signature_in_name: if True, the default codec name includes
          part of the hexdigest of the compressor and decompressor binaries
          being used
        """
        # Set relative paths so that local and remote workers can use the same command line
        if os.path.abspath(compressor_path).startswith(os.path.abspath(options.project_root)):
            compressor_path = enb.atable.get_canonical_path(compressor_path)
        if os.path.abspath(decompressor_path).startswith(os.path.abspath(options.project_root)):
            decompressor_path = enb.atable.get_canonical_path(decompressor_path)

        # pylint: disable=too-many-arguments
        super().__init__(param_dict=param_dict)
        self.signature_in_name = False
        if os.path.isfile(compressor_path):
            self.compressor_path = compressor_path
        else:
            self.compressor_path = shutil.which(compressor_path)
        if os.path.exists(decompressor_path):
            self.decompressor_path = decompressor_path
        else:
            self.decompressor_path = shutil.which(decompressor_path)

        if not self.compressor_path or not os.path.isfile(self.compressor_path):
            raise FileNotFoundError(
                f"Compressor path {repr(compressor_path)} is not available "
                f"for {self.__class__.__name__}")
        if not self.decompressor_path or not os.path.isfile(
                self.decompressor_path):
            raise FileNotFoundError(
                f"Decompressor path {repr(compressor_path)} is not available "
                f"for {self.__class__.__name__}")
        self.output_invocation_dir = output_invocation_dir

    def get_compression_params(self, original_path, compressed_path,
                               original_file_info):
        """Return a string (shell style) with the parameters to be passed to
        the compressor.

        Same parameter semantics as :meth:`AbstractCodec.compress`.

        :param original_file_info: a dict-like object describing
          original_path's properties (e.g., geometry), or None
        """
        raise NotImplementedError()

    def get_decompression_params(self, compressed_path, reconstructed_path,
                                 original_file_info):
        """Return a string (shell style) with the parameters to be passed to
        the decompressor. Same parameter semantics as
        :meth:`AbstractCodec.decompress()`.

        :param original_file_info: a dict-like object describing
          original_path's properties (e.g., geometry), or None
        """
        raise NotImplementedError()

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        compression_params = self.get_compression_params(
            original_path=original_path,
            compressed_path=compressed_path,
            original_file_info=original_file_info)
        invocation = f"{self.compressor_path} {compression_params}"
        enb.logger.debug(f"[{self.name}] Invocation: '{invocation}'")
        try:
            enb.logger.debug(f"[{self.name}] executing: {repr(invocation)}")
            status, output, measured_time, memory_kb = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            enb.logger.debug(
                f"[{self.name}] Compression OK; "
                f"invocation={invocation} - status={status}; "
                f"output={output}; memory={memory_kb} KB")
        except enb.tcall.InvocationError as ex:
            raise CompressionException(
                original_path=original_path,
                compressed_path=compressed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        compression_results = self.compression_results_from_paths(
            original_path=original_path, compressed_path=compressed_path)
        compression_results.compression_time_seconds = measured_time
        compression_results.maximum_memory_kb = memory_kb

        if self.output_invocation_dir is not None:
            os.makedirs(self.output_invocation_dir, exist_ok=True)
            invocation_name = "invocation_compression_" \
                              + self.name \
                              + os.path.abspath(
                os.path.realpath(original_file_info["file_path"])).replace(
                os.sep, "_")
            with open(os.path.join(self.output_invocation_dir, invocation_name),
                      "w") as invocation_file:
                invocation_file.write(
                    f"Original path: {original_path}\n"
                    f"Compressed path: {compressed_path}\n"
                    f"Codec: {self.name}\n"
                    f"Invocation: {invocation}\n"
                    f"Status: {status}\n"
                    f"Output: {output}\n"
                    f"Measured time: {measured_time} s\n"
                    f"Maximum resident memory: {memory_kb} kb")

        return compression_results

    def decompress(self, compressed_path, reconstructed_path,
                   original_file_info=None):
        decompression_params = self.get_decompression_params(
            compressed_path=compressed_path,
            reconstructed_path=reconstructed_path,
            original_file_info=original_file_info)
        invocation = f"{self.decompressor_path} {decompression_params}"
        enb.logger.debug(
            f"WrapperCodec({self.__class__.__name__}:decompress invocation={invocation}")
        try:
            status, output, measured_time, memory_kb \
                = enb.tcall.get_status_output_time_memory(invocation)
            enb.logger.debug(
                f"[{self.name}] Compression OK; "
                f"invocation={invocation} - status={status}; "
                f"output={output}; memory={memory_kb} kb")
        except enb.tcall.InvocationError as ex:
            raise DecompressionException(
                compressed_path=compressed_path,
                reconstructed_path=reconstructed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        decompression_results = self.decompression_results_from_paths(
            compressed_path=compressed_path,
            reconstructed_path=reconstructed_path)
        decompression_results.decompression_time_seconds = measured_time
        decompression_results.maximum_memory_kb = memory_kb

        if self.output_invocation_dir is not None:
            invocation_name = "invocation_decompression_" \
                              + self.name \
                              + os.path.abspath(os.path.realpath(
                original_file_info["file_path"] \
                    if original_file_info is not None \
                    else compressed_path)).replace(os.sep, "_")
            with open(os.path.join(self.output_invocation_dir, invocation_name),
                      "w") as invocation_file:
                invocation_file.write(
                    f"Compressed path: {compressed_path}\n"
                    f"Reconstructed path: {reconstructed_path}\n"
                    f"Codec: {self.name}\n"
                    f"Invocation: {invocation}\n"
                    f"Status: {status}\n"
                    f"Output: {output}\n"
                    f"Measured time: {measured_time} s\n"
                    f"Maximum resident size: {memory_kb} kb")

        return decompression_results

    @staticmethod
    @functools.lru_cache(maxsize=2)
    def get_binary_signature(binary_path):
        """Return a string with a (hopefully) unique signature for the
        contents of binary_path. By default, the first 5 digits of the
        sha-256 hexdigest are returned.
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
        signature = None
        if self.signature_in_name:
            compressor_signature = self.get_binary_signature(
                self.compressor_path)
            decompressor_signature = self.get_binary_signature(
                self.decompressor_path)
            if compressor_signature and decompressor_signature:
                if compressor_signature == decompressor_signature:
                    signature = f"{compressor_signature}"
                else:
                    signature = f"{compressor_signature}_{compressor_signature}"

        name = f"{self.__class__.__name__}_{signature}" \
            if signature is not None else self.__class__.__name__
        if self.param_dict:
            name += "__" + "_".join(
                f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name


class QuantizationWrapperCodec(NearLosslessCodec):
    """Perform uniform scalar quantization before compressing and after decompressing with
    a wrapped codec instance. Midpoint reconstruction is used in the dequantization stage.
    """

    def __init__(self, codec: AbstractCodec, qstep: int):
        """
        :param codec: The codec instance used to compress and decompress the quantized data.
        :param qstep: The quantization interval length
        """
        if qstep < 1 or int(qstep) != qstep:
            raise ValueError("The quantization step must be an integer no smaller than 1")
        super().__init__(param_dict=dict(codec_name=codec.name, qstep=qstep))
        self.codec = codec

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        with tempfile.TemporaryDirectory(dir=enb.config.options.base_tmp_dir) as tmp_dir:
            # Read image data
            image_array = enb.isets.load_array_bsq(original_path)

            # Apply quantization
            if not (self.param_dict["qstep"] & (self.param_dict["qstep"] - 1)):
                # Efficiently way to execute image_array // self.param_dict["qstep"]
                # When qstep is a power of 2
                image_array >>= self.param_dict["qstep"].bit_length() - 1
            else:
                image_array //= self.param_dict["qstep"]

            # Apply compression to the quantized data
            output_quantized_path = os.path.join(tmp_dir, os.path.basename(original_path))
            enb.isets.dump_array_bsq(image_array, output_quantized_path)
            self.codec.compress(output_quantized_path, compressed_path, original_file_info)

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with tempfile.TemporaryDirectory(dir=enb.config.options.base_tmp_dir) as tmp_dir:
            output_quantized_path = os.path.join(tmp_dir, os.path.basename(reconstructed_path))
            self.codec.decompress(compressed_path, output_quantized_path, original_file_info)
            image_array = enb.isets.load_array_bsq(output_quantized_path)

            if not (self.param_dict["qstep"] & (self.param_dict["qstep"] - 1)):
                # Efficiently way to execute image_array * self.param_dict["qstep"]
                # When qstep is a power of 2
                image_array <<= self.param_dict["qstep"].bit_length() - 1
            else:
                image_array *= self.param_dict["qstep"]

            min_val, max_val = np.iinfo(image_array.dtype).min, np.iinfo(image_array.dtype).max
            image_array = np.clip((image_array.astype(np.int64) + (self.param_dict["qstep"] // 2)),
                                  min_val, max_val).astype(image_array.dtype)
            enb.isets.dump_array_bsq(image_array, reconstructed_path)

    @property
    def name(self):
        """Return the original codec name and the quantization parameter
        """
        return f"{self.codec.name}_qstep={self.param_dict['qstep']}"

    @property
    def label(self):
        """Return the original codec label and the quantization parameter.
        """
        return f"{self.codec.label}, Q$_\\mathrm{{step}}=${self.param_dict['qstep']}"


class JavaWrapperCodec(WrapperCodec):
    """Wrapper for `*.jar` codecs. The compression and decompression
    parameters are those that need to be passed to the 'java' command.

    The `compressor_jar` and `decompressor_jar` attributes are added upon
    initialization based on the params to `__init__`.
    """

    def __init__(self, compressor_jar, decompressor_jar, param_dict=None):
        assert shutil.which("java") is not None, \
            f"The 'java' program was not found in the path, but is required by " \
            f"{self.__class__.__name__}. " \
            f"Please (re)install a JRE in the path and try again."
        super().__init__(compressor_path=shutil.which("java"),
                         decompressor_path=shutil.which("java"),
                         param_dict=param_dict)
        self.compressor_jar = enb.atable.get_canonical_path(compressor_jar)
        self.decompressor_jar = enb.atable.get_canonical_path(decompressor_jar)


class GiciLibHelper:
    """Definition of helper methods that can be used with software based on
    the GiciLibs (see gici.uab.cat/GiciWebPage/downloads.php).
    """

    def file_info_to_data_str(self, original_file_info):
        if original_file_info["bytes_per_sample"] == 1:
            data_type_str = "1"
        elif original_file_info["bytes_per_sample"] == 2:
            if original_file_info["signed"]:
                data_type_str = "3"
            else:
                data_type_str = "2"
        elif original_file_info["bytes_per_sample"] == 4:
            if original_file_info["signed"]:
                return "4"
            else:
                raise ValueError(
                    "32-bit samples are supported, but they must be signed.")
        else:
            raise ValueError(
                f"Invalid data type, not supported by "
                f"{self.__class__.__name__}: {original_file_info}")
        return data_type_str

    def file_info_to_endianness_str(self, original_file_info):
        return "0" if original_file_info["big_endian"] else "1"

    def get_gici_geometry_str(self, original_file_info):
        """Get a string to be passed to the -ig or -og parameters. The '-ig'
        or '-og' part is not included in the returned string.
        """
        return f"{original_file_info['component_count']} " \
               f"{original_file_info['height']} " \
               f"{original_file_info['width']} " \
               f"{self.file_info_to_data_str(original_file_info=original_file_info)} " \
               f"{self.file_info_to_endianness_str(original_file_info=original_file_info)} " \
               f"0 "


class LittleEndianWrapper(WrapperCodec):
    """Wrapper with identical semantics as WrapperCodec, but performs a big
    endian to little endian conversion for (big-endian) 2-byte and 4-byte
    samples. If the input is flagged as little endian, e.g., if -u16le- is in
    the original file name, then no transformation is performed.

    Codecs inheriting from this class automatically receive little-endian
    samples, and are expected to reconstruct little-endian files (which are
    then translated back to big endian if and only if the original image was
    flagged as big endian.
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        if original_file_info["big_endian"] and original_file_info["bytes_per_sample"] > 1:
            with tempfile.NamedTemporaryFile(
                    dir=options.base_tmp_dir,
                    suffix=f"-u{8 * original_file_info['bytes_per_sample']}le"
                           f"-{original_file_info['component_count']}"
                           f"x{original_file_info['height']}"
                           f"x{original_file_info['width']}.raw") \
                    as reversed_endian_file:
                be_img = enb.isets.load_array_bsq(
                    file_or_path=original_path,
                    image_properties_row=original_file_info)
                reversed_file_info = dict(original_file_info)
                reversed_file_info["big_endian"] = False
                sign_str = "i" if original_file_info["signed"] else "u"
                enb.isets.dump_array_bsq(array=be_img.astype(
                    f"<{sign_str}{original_file_info['bytes_per_sample']}"),
                    file_or_path=reversed_endian_file.name)
                compression_results = super().compress(
                    original_path=reversed_endian_file.name,
                    compressed_path=compressed_path,
                    original_file_info=reversed_file_info)
                compression_results.original_path = original_path
                return compression_results
        else:
            return super().compress(
                original_path=original_path,
                compressed_path=compressed_path,
                original_file_info=original_file_info)

    def decompress(self, compressed_path, reconstructed_path,
                   original_file_info=None):
        if original_file_info["big_endian"] and original_file_info["bytes_per_sample"] > 1:
            with tempfile.NamedTemporaryFile(
                    dir=options.base_tmp_dir,
                    suffix=f"-u{8 * original_file_info['bytes_per_sample']}le"
                           f"-{original_file_info['component_count']}"
                           f"x{original_file_info['height']}"
                           f"x{original_file_info['width']}.raw") as reversed_endian_file:
                reversed_file_info = dict(original_file_info)
                reversed_file_info["big_endian"] = True
                decompression_results = super().decompress(
                    compressed_path=compressed_path,
                    reconstructed_path=reversed_endian_file.name,
                    original_file_info=reversed_file_info)
                le_img = enb.isets.load_array_bsq(
                    file_or_path=reversed_endian_file.name,
                    image_properties_row=reversed_file_info)
                sign_str = "i" if original_file_info["signed"] else "u"
                # Store with < (le) instead of > (be) to undo the byte reversal during compression
                enb.isets.dump_array_bsq(array=le_img.astype(
                    f"<{sign_str}{original_file_info['bytes_per_sample']}"),
                    file_or_path=reconstructed_path)
                decompression_results.reconstructed_path = reconstructed_path
                
                return decompression_results
        else:
            return super().decompress(compressed_path=compressed_path,
                                      reconstructed_path=reconstructed_path,
                                      original_file_info=original_file_info)


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
        def compression_results(self):
            """Perform the actual compression experiment for the selected row.
            """
            if self._compression_results is None:
                os.makedirs(options.base_tmp_dir, exist_ok=True)
                # Assign a unique temporary path to the compressed file
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
        def decompression_results(self):
            """Perform the actual decompression experiment for the selected row.
            """
            if self._decompression_results is None:
                # Assign a unique temporary name to the reconstructed file
                fd, tmp_reconstructed_path = tempfile.mkstemp(
                    prefix=f"reconstructed_{os.path.basename(self.file_path)}",
                    dir=options.base_tmp_dir,
                    suffix=".raw")
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
                              f"{table_class.__name__}_persistence.csv")
        imageinfo_table = dataset_info_table if dataset_info_table is not None \
            else table_class(csv_support_path=csv_dataset_path)

        csv_dataset_path = csv_dataset_path if csv_dataset_path is not None \
            else f"{dataset_info_table.__class__.__name__}_persistence.csv"

        if not codecs:
            raise ValueError(
                f"{self}: no codecs were selected for this experiment. At least one is needed.")
        non_subclass_codecs = [c for c in codecs if not isinstance(c,
                                                                   enb.icompression.AbstractCodec)]
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
        self.codec_results = None

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
                compressed_copy_dir=self.compressed_copy_dir_path,
                reconstructed_copy_dir=self.reconstructed_dir_path)
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
            assert row.image_info_row["bytes_per_sample"] * row.image_info_row[
                "samples"] \
                   == os.path.getsize(
                self.codec_results.compression_results.original_path)
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

    @enb.atable.column_function(
        [enb.atable.ColumnProperties(
            name="compression_efficiency_1byte_entropy",
            label="Compression efficiency (1B entropy)",
            plot_min=0),
            enb.atable.ColumnProperties(
                name="compression_efficiency_2byte_entropy",
                label="Compression efficiency (2B entropy)",
                plot_min=0),
        ])
    def set_efficiency(self, index, row):
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]
        for bytes in (1, 2):
            column_name = f"compression_efficiency_{bytes}byte_entropy"
            try:
                row[column_name] = \
                    row.image_info_row[f"entropy_{bytes}B_bps"] * (
                            row.image_info_row["size_bytes"] / bytes) \
                    / (row["compressed_size_bytes"] * 8)
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
    """Lossless compression of raw image files. The experiment fails if
    lossless compression is not attained.
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


class LossyCompressionExperiment(CompressionExperiment):
    """Lossy compression of raw image files.
    """

    @enb.atable.column_function("mse", label="MSE", plot_min=0)
    def set_MSE(self, index, row):
        """Set the mean squared error of the reconstructed image.
        """
        original_array = np.fromfile(
            self.codec_results.compression_results.original_path,
            dtype=self.codec_results.numpy_dtype).astype(np.int64)

        reconstructed_array = np.fromfile(
            self.codec_results.decompression_results.reconstructed_path,
            dtype=self.codec_results.numpy_dtype).astype(np.int64)
        row[_column_name] = np.average(
            ((original_array - reconstructed_array) ** 2))

    @enb.atable.column_function("pae", label="PAE", plot_min=0)
    def set_PAE(self, index, row):
        """Set the peak absolute error (maximum absolute pixelwise
        difference) of the reconstructed image.
        """
        original_array = np.fromfile(
            self.codec_results.compression_results.original_path,
            dtype=self.codec_results.numpy_dtype).astype(np.int64)

        reconstructed_array = np.fromfile(
            self.codec_results.decompression_results.reconstructed_path,
            dtype=self.codec_results.numpy_dtype).astype(np.int64)
        row[_column_name] = np.max(np.abs(original_array - reconstructed_array))

    @enb.atable.column_function("psnr_bps", label="PSNR (dB)", plot_min=0)
    def set_PSNR_nominal(self, index, row):
        """Set the PSNR assuming nominal dynamic range given by
        bytes_per_sample.
        """
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]
        if row.image_info_row["float"]:
            row[_column_name] = float("inf")
        else:
            max_error = (2 ** (8 * row.image_info_row["bytes_per_sample"])) - 1
            row[_column_name] = (
                    20 * math.log10((max_error) / math.sqrt(row["mse"]))) \
                if row["mse"] > 0 else float("inf")

    @enb.atable.column_function("psnr_dr", label="PSNR (dB)", plot_min=0)
    def set_PSNR_dynamic_range(self, index, row):
        """Set the PSNR assuming dynamic range given by dynamic_range_bits.
        """
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]
        max_error = (2 ** row.image_info_row["dynamic_range_bits"]) - 1
        row[_column_name] = 20 * math.log10(max_error / math.sqrt(row["mse"])) \
            if row["mse"] > 0 else float("inf")


class GeneralLosslessExperiment(LosslessCompressionExperiment):
    """Lossless compression experiment for general data contents.
    """

    class GenericFilePropertiesTable(enb.isets.ImagePropertiesTable):
        """File properties table that considers the input path as a 1D,
        u8be array.
        """
        verify_file_size = False

        @enb.atable.column_function([
            enb.atable.ColumnProperties(name="sample_min",
                                        label="Min sample value (byte samples)"),
            enb.atable.ColumnProperties(name="sample_max",
                                        label="Max sample value (byte samples)")])
        def set_sample_extrema(self, file_path, row):
            """Set the minimum and maximum byte value extrema.
            """
            with open(file_path, "rb") as input_file:
                contents = input_file.read()
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

    default_file_properties_table_class = GenericFilePropertiesTable
    dataset_files_extension = ""


class StructuralSimilarity(CompressionExperiment):
    """Set the Structural Similarity (SSIM) and Multi-Scale Structural
    Similarity metrics (MS-SSIM) to measure the similarity between two images.

    Authors:
        - http://www.cns.nyu.edu/~lcv/ssim/msssim.zip
        - https://github.com/dashayushman/TAC-GAN/blob/master/msssim.py
    """

    @enb.atable.column_function([
        enb.atable.ColumnProperties(name="ssim", label="SSIM", plot_max=1),
        enb.atable.ColumnProperties(name="ms_ssim", label="MS-SSIM",
                                    plot_max=1)])
    def set_StructuralSimilarity(self, index, row):
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            enb.atable.indices_to_internal_loc(file_path)]
        original_array = np.fromfile(
            self.codec_results.compression_results.original_path,
            dtype=self.codec_results.numpy_dtype)
        original_array = np.reshape(original_array,
                                    (row.image_info_row["width"],
                                     row.image_info_row["height"],
                                     row.image_info_row["component_count"]))

        reconstructed_array = np.fromfile(
            self.codec_results.decompression_results.reconstructed_path,
            dtype=self.codec_results.numpy_dtype)
        reconstructed_array = np.reshape(reconstructed_array,
                                         (row.image_info_row["width"],
                                          row.image_info_row["height"],
                                          row.image_info_row[
                                              "component_count"]))

        row["ssim"] = self.compute_SSIM(original_array, reconstructed_array)
        row["ms_ssim"] = self.cumpute_MSSIM(original_array, reconstructed_array)

    def cumpute_MSSIM(self, img1, img2, max_val=255, filter_size=11,
                      filter_sigma=1.5, k1=0.01, k2=0.03, weights=None):
        """Return the MS-SSIM score between `img1` and `img2`.

        This function implements Multi-Scale Structural Similarity (MS-SSIM) Image
        Quality Assessment according to Zhou Wang's paper, "Multi-scale structural
        similarity for image quality assessment" (2003).
        Link: https://ece.uwaterloo.ca/~z70wang/publications/msssim.pdf

        Author's MATLAB implementation:
        http://www.cns.nyu.edu/~lcv/ssim/msssim.zip

        Author's Python implementation:
        https://github.com/dashayushman/TAC-GAN/blob/master/msssim.py

        Authors documentation:

        :param img1: Numpy array holding the first RGB image batch.
        :param img2: Numpy array holding the second RGB image batch.
        :param max_val: the dynamic range of the images (i.e., the difference
          between the maximum the and minimum allowed values).
        :param filter_size: Size of blur kernel to use (will be reduced for
          small images).
        :param filter_sigma: Standard deviation for Gaussian blur kernel (
          will be reduced for small images).
        :param k1: Constant used to maintain stability in the SSIM
          calculation (0.01 in the original paper).
        :param k2: Constant used to maintain stability in the SSIM
          calculation (0.03 in the original paper).
        """
        # pylint: disable=too-many-arguments
        if img1.shape != img2.shape:
            raise RuntimeError(
                'Input images must have the same shape (%s vs. %s).',
                img1.shape, img2.shape)
        if img1.ndim != 3:
            raise RuntimeError("Input images must have four dimensions, "
                               f"not {img1.ndim}")

        weights = np.array(weights if weights else
                           [0.0448, 0.2856, 0.3001, 0.2363, 0.1333])
        levels = weights.size
        downsample_filter = np.ones((2, 2, 1)) / 4.0
        im1, im2 = [x.astype(np.float64) for x in [img1, img2]]
        mssim = np.array([])
        mcs = np.array([])
        for _ in range(levels):
            ssim, cs = self.compute_SSIM(
                im1, im2, max_val=max_val, filter_size=filter_size,
                filter_sigma=filter_sigma, k1=k1, k2=k2, full=True)
            mssim = np.append(mssim, ssim)
            mcs = np.append(mcs, cs)
            filtered = [convolve(im, downsample_filter, mode='reflect')
                        for im in [im1, im2]]
            im1, im2 = [x[::2, ::2, :] for x in filtered]

        return np.prod(mcs[0:levels - 1] ** weights[0:levels - 1]) * (
                mssim[levels - 1] ** weights[levels - 1])

    def compute_SSIM(self, img1, img2, max_val=255, filter_size=11,
                     filter_sigma=1.5, k1=0.01, k2=0.03, full=False):
        """Return the Structural Similarity Map between `img1` and `img2`.

        This function attempts to match the functionality of ssim_index_new.m
        by Zhou Wang: http://www.cns.nyu.edu/~lcv/ssim/msssim.zip

        Author's Python implementation:
        https://github.com/dashayushman/TAC-GAN/blob/master/msssim.py

        :param img1: Numpy array holding the first RGB image batch.
        :param img2: Numpy array holding the second RGB image batch.

        :param max_val: the dynamic range of the images (i.e., the difference
          between the maximum the and minimum allowed values).

        :param filter_size: Size of blur kernel to use (will be reduced for
          small images). :param filter_sigma: Standard deviation for Gaussian
          blur kernel (will be reduced for small images). :param k1: Constant
          used to maintain stability in the SSIM calculation (0.01 in the
          original paper). :param k2: Constant used to maintain stability in
          the SSIM calculation (0.03 in the original paper).
        """
        # pylint: disable=too-many-arguments
        if img1.shape != img2.shape:
            raise RuntimeError(
                'Input images must have the same shape (%s vs. %s).',
                img1.shape, img2.shape)
        if img1.ndim != 3:
            raise RuntimeError(
                f"Input images must have four dimensions, not {img1.ndim}")
        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)
        height, width, bytes = img1.shape

        # Filter size can't be larger than height or width of images.
        size = min(filter_size, height, width)

        # Scale down sigma if a smaller filter size is used.
        sigma = size * filter_sigma / filter_size if filter_size else 0

        if filter_size:
            window = np.reshape(self._FSpecialGauss(size, sigma),
                                (size, size, 1))
            mu1 = signal.fftconvolve(img1, window, mode='valid')
            mu2 = signal.fftconvolve(img2, window, mode='valid')
            sigma11 = signal.fftconvolve(img1 * img1, window, mode='valid')
            sigma22 = signal.fftconvolve(img2 * img2, window, mode='valid')
            sigma12 = signal.fftconvolve(img1 * img2, window, mode='valid')
        else:
            # Empty blur kernel so no need to convolve.
            mu1, mu2 = img1, img2
            sigma11 = img1 * img1
            sigma22 = img2 * img2
            sigma12 = img1 * img2

        mu11 = mu1 * mu1
        mu22 = mu2 * mu2
        mu12 = mu1 * mu2
        sigma11 -= mu11
        sigma22 -= mu22
        sigma12 -= mu12

        # Calculate intermediate values used by both ssim and cs_map.
        c1 = (k1 * max_val) ** 2
        c2 = (k2 * max_val) ** 2
        v1 = 2.0 * sigma12 + c2
        v2 = sigma11 + sigma22 + c2
        ssim = np.mean((((2.0 * mu12 + c1) * v1) / ((mu11 + mu22 + c1) * v2)))
        cs = np.mean(v1 / v2)
        if full:
            return ssim, cs
        return ssim

    def _FSpecialGauss(self, size, sigma):

        radius = size // 2
        offset = 0.0
        start, stop = -radius, radius + 1
        if size % 2 == 0:
            offset = 0.5
            stop -= 1
        x, y = np.mgrid[offset + start:stop, offset + start:stop]
        assert len(x) == size
        g = np.exp(-((x ** 2 + y ** 2) / (2.0 * sigma ** 2)))
        return g / g.sum()


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
        decompression_results = self.codec_results.decompression_results
        original_array = enb.isets.load_array_bsq(
            file_or_path=original_file_path,
            image_properties_row=image_properties_row)
        reconstructed_array = enb.isets.load_array_bsq(
            file_or_path=decompression_results.reconstructed_path,
            image_properties_row=image_properties_row)

        # Reshape flattening the x,y axes, and maintaining the z axis for
        # each (x,y) position
        original_array = np.reshape(
            original_array.swapaxes(0, 1),
            (image_properties_row["width"] * image_properties_row["height"],
             image_properties_row["component_count"]),
            "F").astype("i8")
        reconstructed_array = np.reshape(
            reconstructed_array.swapaxes(0, 1),
            (image_properties_row["width"] * image_properties_row["height"],
             image_properties_row["component_count"]),
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

    @enb.atable.column_function([
        enb.atable.ColumnProperties("mean_spectral_angle_deg",
                                    label="Mean spectral angle (deg)",
                                    plot_min=0, plot_max=None),
        enb.atable.ColumnProperties("max_spectral_angle_deg",
                                    label="Max spectral angle (deg)",
                                    plot_min=0, plot_max=None)])
    def set_spectral_distances(self, index, row):
        spectral_angles = self.get_spectral_angles_deg(index=index, row=row)

        for angle in spectral_angles:
            assert not np.isnan(
                angle), f"Error calculating an angle for {index}: {angle}"

        row["mean_spectral_angle_deg"] = sum(spectral_angles) / len(
            spectral_angles)
        row["max_spectral_angle_deg"] = max(spectral_angles)
