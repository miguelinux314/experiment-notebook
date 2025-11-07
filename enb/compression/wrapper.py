"""Wrapper codec classes. 

Existing codec implementations (including non-python binaries) can be easily added to enb
via WrapperCodec (sub)classes. 
"""
import ast
import os
import functools
import shutil
import tempfile
import time
import json
import numpy as np

import enb
from enb import logger, tcall
from enb import isets
from enb.config import options
from enb.atable import get_canonical_path
from enb.compression import CompressionResults, DecompressionResults, CompressionException, DecompressionException
from enb.compression.codec import AbstractCodec, NearLosslessCodec
from enb.compression import tarlite


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
          stored in this directory with name based on the codec and the sample's
          full path.
        :pram signature_in_name: if True, the default codec name includes
          part of the hexdigest of the compressor and decompressor binaries
          being used
        """
        # Set relative paths so that local and remote workers can use the same command line
        if os.path.abspath(compressor_path).startswith(os.path.abspath(options.project_root)):
            compressor_path = get_canonical_path(compressor_path)
        if os.path.abspath(decompressor_path).startswith(os.path.abspath(options.project_root)):
            decompressor_path = get_canonical_path(decompressor_path)

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
        logger.debug(f"[{self.name}] Invocation: '{invocation}'")
        try:
            logger.debug(f"[{self.name}] executing: {repr(invocation)}")
            status, output, measured_time, memory_kb = \
                tcall.get_status_output_time_memory(invocation=invocation)
            logger.debug(
                f"[{self.name}] Compression OK; "
                f"invocation={invocation} - status={status}; "
                f"output={output}; memory={memory_kb} KB")
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
        logger.debug(
            f"WrapperCodec({self.__class__.__name__}:decompress invocation={invocation}")
        try:
            status, output, measured_time, memory_kb \
                = tcall.get_status_output_time_memory(invocation)
            logger.debug(
                f"[{self.name}] Compression OK; "
                f"invocation={invocation} - status={status}; "
                f"output={output}; memory={memory_kb} kb")
        except tcall.InvocationError as ex:
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
                f"{k}={v}" for k, v in sorted(self.param_dict.items())
                if not k.startswith("_"))
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
        with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
            # Read original data
            array = isets.load_array_bsq(original_path)

            # Apply quantization
            if not (self.param_dict["qstep"] & (self.param_dict["qstep"] - 1)):
                # Efficiently way to execute image_array // self.param_dict["qstep"]
                # When qstep is a power of 2
                array >>= self.param_dict["qstep"].bit_length() - 1
            else:
                array //= self.param_dict["qstep"]

            # Apply compression to the quantized data
            output_quantized_path = os.path.join(tmp_dir, os.path.basename(original_path))
            isets.dump_array_bsq(array, output_quantized_path)
            self.codec.compress(output_quantized_path, compressed_path, original_file_info)

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
            output_quantized_path = os.path.join(tmp_dir, os.path.basename(reconstructed_path))
            self.codec.decompress(compressed_path, output_quantized_path, original_file_info)
            array = isets.load_array_bsq(output_quantized_path)

            if not (self.param_dict["qstep"] & (self.param_dict["qstep"] - 1)):
                # Efficiently way to execute image_array * self.param_dict["qstep"]
                # When qstep is a power of 2
                array <<= self.param_dict["qstep"].bit_length() - 1
            else:
                array *= self.param_dict["qstep"]

            min_val, max_val = np.iinfo(array.dtype).min, np.iinfo(array.dtype).max
            array = np.clip((array.astype(np.int64) + (self.param_dict["qstep"] // 2)),
                            min_val, max_val).astype(array.dtype)
            isets.dump_array_bsq(array, reconstructed_path)

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
        self.compressor_jar = get_canonical_path(compressor_jar)
        self.decompressor_jar = get_canonical_path(decompressor_jar)


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
                be_img = isets.load_array_bsq(
                    file_or_path=original_path,
                    image_properties_row=original_file_info)
                reversed_file_info = dict(original_file_info)
                reversed_file_info["big_endian"] = False
                sign_str = "i" if original_file_info["signed"] else "u"
                isets.dump_array_bsq(array=be_img.astype(
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
                le_img = isets.load_array_bsq(
                    file_or_path=reversed_endian_file.name,
                    image_properties_row=reversed_file_info)
                sign_str = "i" if original_file_info["signed"] else "u"
                # Store with < (le) instead of > (be) to undo the byte reversal during compression
                isets.dump_array_bsq(array=le_img.astype(
                    f"<{sign_str}{original_file_info['bytes_per_sample']}"),
                    file_or_path=reconstructed_path)
                decompression_results.reconstructed_path = reconstructed_path

                return decompression_results
        else:
            return super().decompress(compressed_path=compressed_path,
                                      reconstructed_path=reconstructed_path,
                                      original_file_info=original_file_info)


class ReindexWrapper(AbstractCodec):
    """Input samples are first reindexed to a contiguous support preserving the ordering 
    (If x and y are two sample values present in the input file, then
    x < y <=> reindex(x) < reindex(y)).
    
    Reindexed data are stored as unsigned, big-endian samples of the width configured
    on initialization. After reindexing, the codec passed to the initializer is used for compression.
    
    The user is responsible for using a codec compatible with the type of the reindexed data,
    and a data type that can hold the number of unique samples present in the input file.
    
    Note that only integer input samples are currently supported.
    """

    def __init__(self, codec: AbstractCodec, width_bytes: int):
        super().__init__(param_dict={"width_bytes": width_bytes})
        self.codec = codec

    def compress(self, original_path: str, compressed_path: str, original_file_info=None) -> CompressionResults:
        with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
            # Find the unique values and store them as side information
            array = enb.isets.load_array_bsq(original_path)
            time_before = time.process_time() if not enb.config.options.report_wall_time else time.time()
            unique_values = np.unique(array)
            if len(unique_values) > 2 ** (8 * self.param_dict['width_bytes']):
                raise ValueError(
                    f"Trying to reindex into a {self.param_dict['width_bytes']}-byte file "
                    f"but there are {len(unique_values)} (too many) unique values.")
            side_info_path = os.path.join(tmp_dir, "side_info")
            with open(side_info_path, "w") as side_info_file:
                side_info_file.write(json.dumps(
                    obj=dict(original_dtype=str(array.dtype),
                             unique_values=str([int(x) for x in unique_values]))))

            # Reindex keeping the value sorting
            reindex_array = np.zeros(shape=array.shape, dtype=f">u{self.param_dict['width_bytes']}")
            for i, val in enumerate(unique_values):
                reindex_array[array == val] = i

            time_after = time.process_time() if not enb.config.options.report_wall_time else time.time()
            reindex_time = time_after - time_before

            # Store the reindexed data
            reindexed_path = os.path.join(tmp_dir, f"reindexed_{os.path.basename(original_path)}")
            for tag in enb.isets.dtype_tags:
                reindexed_path = os.path.join(
                    os.path.dirname(reindexed_path),
                    os.path.basename(reindexed_path).replace(tag, f"u{8 * self.param_dict['width_bytes']}be"))
            enb.isets.dump_array_bsq(array=reindex_array, file_or_path=reindexed_path)

            # Compress the reindexed data
            reindexed_compressed_path = os.path.join(tmp_dir, f"data")
            time_before = time.process_time() if not enb.config.options.report_wall_time else time.time()
            reindex_file_info = dict(original_file_info) if original_file_info is not None else None
            if reindex_file_info is not None:
                reindex_file_info["signed"] = False
                reindex_file_info["big_endian"] = True
                reindex_file_info["bytes_per_sample"] = 2
            compression_results = self.codec.compress(reindexed_path, reindexed_compressed_path, reindex_file_info)
            time_after = time.process_time() if not enb.config.options.report_wall_time else time.time()
            compression_time = time_after - time_before

            # Update the reported compression results
            if compression_results is None:
                compression_results = self.codec.compression_results_from_paths(
                    original_path=reindexed_path,
                    compressed_path=compressed_path)
            compression_results.original_path = original_path
            compression_results.compressed_path = compressed_path
            if compression_results.compression_time_seconds is None \
                    or compression_results.compression_time_seconds < 0:
                compression_results.compression_time_seconds = compression_time
            compression_results.compression_time_seconds += reindex_time

            # Store the side information and reindexed data into a tarlite package
            tarlite.tarlite_files([side_info_path, reindexed_compressed_path], compressed_path)

            return compression_results

    def decompress(self, compressed_path: str, reconstructed_path: str,
                   original_file_info=None) -> DecompressionResults:
        with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
            # Extract the tarlite package
            tarlite.untarlite_files(input_tarlite_path=compressed_path, output_dir_path=tmp_dir)
            reindexed_compressed_path = os.path.join(tmp_dir, "data")
            side_info_path = os.path.join(tmp_dir, "side_info")

            # Read and complete the side information
            with open(side_info_path, "r") as side_info_file:
                side_info = json.load(side_info_file)
                unique_values = np.array(ast.literal_eval(side_info["unique_values"]))
                original_width_bytes = int(side_info["original_dtype"][-1])

            # Decompress the reindexed data
            reindexed_path = os.path.join(tmp_dir, f"reindexed")
            self.codec.decompress(reindexed_compressed_path, reindexed_path, original_file_info)

            # Invert the reindexing
            assert os.path.getsize(reindexed_path) % original_width_bytes == 0, \
                ("Invalid output file size", os.path.getsize(reindexed_path), original_width_bytes)

            reindexed_data = enb.isets.load_array(
                file_or_path=reindexed_path,
                width=os.path.getsize(reindexed_path) // self.param_dict['width_bytes'],
                height=1,
                component_count=1,
                dtype=f">u{self.param_dict['width_bytes']}")

            data = np.zeros(shape=reindexed_data.shape, dtype=np.int64)
            np.take(unique_values, reindexed_data, out=data)
            enb.isets.dump_array_bsq(array=data.astype(side_info["original_dtype"]), file_or_path=reconstructed_path)

    @property
    def name(self):
        """Return the original codec name and the quantization parameter
        """
        return f"{self.codec.name}_reindex{self.param_dict['width_bytes']}B"

    @property
    def label(self):
        """Return the original codec label and the quantization parameter.
        """
        return f"Reindex {self.param_dict['width_bytes']}B + {self.codec.label}"
