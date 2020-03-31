#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base classes to define codecs with an homogeneous interface
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "19/09/2019"

import os
import shutil
import functools
import hashlib
import subprocess
import recordclass


class FileInfo(recordclass.RecordClass):
    """Base class that defines the minimal fields to be included as the metainfo
    parameter in codecs' compress() and decompress() methods.

    :note: rows from sets.ImagePropertiesTAble contain at least these fields
    """
    # file_path: path to the file
    # original_size_bytes: number of bytes in the original file
    file_path: str = None
    original_size_bytes: int = None

    @staticmethod
    def from_path(path):
        return FileInfo(file_path=path, original_size_bytes=os.path.getsize(path))


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


class CompressionException(BaseException):
    """Base class for exceptions occurred during a compression instance
    """

    def __init__(self, original_path, compressed_path, file_info, status, output):
        super().__init__(output)
        self.original_path = original_path
        self.compressed_path = compressed_path
        self.file_info = file_info
        self.status = status
        self.output = output


class DecompressionException(BaseException):
    """Base class for exceptions occurred during a decompression instance
    """

    def __init__(self, compressed_path, reconstructed_path, file_info, status, output):
        super().__init__(output)
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

    def compress(self, original_path: str, compressed_path: str, original_file_info: FileInfo = None):
        """Compress original_path into compress_path using param_dict as params.
        :param original_path: path to the original file to be compressed
        :param compressed_path: path to the compressed file to be created
        :param original_file_info: FileInfo-like instance corresponding to original_path,
          or None
        :return: (optional) a CompressionResults instance, or None
          (see compression_results_from_paths)
        """
        raise NotImplementedError()

    def decompress(self, compressed_path, reconstructed_path, original_file_info: FileInfo = None):
        """Decompress compressed_path into reconstructed_path using param_dict
        as params (if needed).
        :param compressed_path: path to the input compressed file
        :param reconstructed_path: path to the output reconstructed file
        :param original_file_info: FileInfo-like instance corresponding to original_path,
          or None. Should only be used in special cases, but codecs should include all
          needed side information.
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

    def get_compression_params(self, original_path, compressed_path, original_file_info: FileInfo):
        """Return a string (shell style) with the parameters
        to be passed to the compressor.
        Same parameter semantics as AbstractCodec.compress().
        """
        raise NotImplementedError()

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info: FileInfo):
        """Return a string (shell style) with the parameters
        to be passed to the decompressor.
        Same parameter semantics as AbstractCodec.decompress().
        """
        raise NotImplementedError()

    def compress(self, original_path: str, compressed_path: str, original_file_info: FileInfo = None):
        compression_params = self.get_compression_params(
            original_path=original_path,
            compressed_path=compressed_path,
            original_file_info=original_file_info)
        status, output = subprocess.getstatusoutput(f"{self.compressor_path} {compression_params}")
        if status != 0:
            raise CompressionException(
                original_path=original_path,
                compressed_path=compressed_path,
                file_info=original_file_info,
                status=status,
                output=output)

    def decompress(self, compressed_path, reconstructed_path, original_file_info: FileInfo = None):
        decompression_params = self.get_decompression_params(
            compressed_path=compressed_path,
            reconstructed_path=reconstructed_path,
            original_file_info=original_file_info)
        status, output = subprocess.getstatusoutput(f"{self.decompressor_path} {decompression_params}")
        if status != 0:
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


def get_lossless_codec_classes():
    from enb.codec_implementations import all_lossless_codec_classes
    return all_lossless_codec_classes


def get_lossy_codec_classes():
    from codec_implementations import all_lossy_codec_classes
    return all_lossy_codec_classes


if __name__ == '__main__':
    print("Available lossless codecs:")
    print("\n".join(f"\t- {c.__name__}" for c in get_lossless_codec_classes())
          if get_lossless_codec_classes() else "\t(none)")
    print()
    print("Available lossy codecs:")
    print("\n".join(f"\t- {c.__name__}" for c in get_lossy_codec_classes())
          if get_lossy_codec_classes() else "\t(none)")
