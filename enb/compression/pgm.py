#!/usr/bin/env python3
"""Module to handle PGM (P5) and PPM (P6) images
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/08"

import os
import sys
import re
import tempfile

import imageio
import numpngw
import numpy as np

import enb
import enb.isets


class PGMWrapperCodec(enb.icompression.WrapperCodec):
    """Raw images are coded into PNG before compression with the wrapper,
    and PNG is decoded to raw after decompression.
    """

    # pylint: disable=abstract-method

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        assert original_file_info["component_count"] == 1, \
            "PGM only supported for 1-component images"
        assert original_file_info["bytes_per_sample"] in [1, 2], \
            "PGM only supported for 8 or 16 bit images"
        img = enb.isets.load_array_bsq(
            file_or_path=original_path, image_properties_row=original_file_info)

        with tempfile.NamedTemporaryFile(suffix=".pgm", mode="wb") as tmp_file:
            numpngw.imwrite(tmp_file.name, img)  # pylint: disable=no-member
            with open(tmp_file, "rb") as raw_file:
                contents = raw_file.read()
            os.remove(tmp_file)
            with open(tmp_file.name, "wb") as pgm_file:
                pgm_file.write(bytes(
                    f"P6\n"
                    f"{original_file_info['width']} "
                    f"{original_file_info['height']}\n"
                    f"{255 if original_file_info['bytes_per_sample'] == 1 else 65535}\n"))
                pgm_file.write(contents)

            compression_results = super().compress(
                original_path=tmp_file.name,
                compressed_path=compressed_path,
                original_file_info=original_file_info)
            crs = self.compression_results_from_paths(
                original_path=original_path, compressed_path=compressed_path)
            crs.compression_time_seconds = max(
                0, compression_results.compression_time_seconds)
            crs.maximum_memory_kb = compression_results.maximum_memory_kb
            return crs

    def decompress(self, compressed_path, reconstructed_path,
                   original_file_info=None):
        with tempfile.NamedTemporaryFile(suffix=".pgm") as tmp_file:
            decompression_results = super().decompress(
                compressed_path=compressed_path,
                reconstructed_path=tmp_file.name)
            img = imageio.imread(tmp_file.name, "pgm")
            img.swapaxes(0, 1)
            assert len(img.shape) in [2, 3, 4]
            if len(img.shape) == 2:
                img = np.expand_dims(img, axis=2)
            enb.isets.dump_array_bsq(img, file_or_path=reconstructed_path)

            drs = self.decompression_results_from_paths(
                compressed_path=compressed_path,
                reconstructed_path=reconstructed_path)
            drs.decompression_time_seconds = \
                decompression_results.decompression_time_seconds

class PGMCurationTable(enb.png.PNGCurationTable):
    """Given a directory tree containing PGM images, copy those images into
    a new directory tree in raw BSQ format adding geometry information tags to
    the output names recognized by `enb.isets.load_array_bsq`.
    """
    dataset_files_extension = "pgm"


def read_pgm(input_path, byteorder='>'):
    """Return image data from a raw PGM file as numpy array.
    Format specification: http://netpbm.sourceforge.net/doc/pgm.html

    (From answer:
    https://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm)
    """
    with open(input_path, 'rb') as input_file:
        buffer = input_file.read()
    try:
        header, width, height, maxval = re.search(
            br"(^P5\s(?:\s*#.*[\r\n])*"
            br"(\d+)\s(?:\s*#.*[\r\n])*"
            br"(\d+)\s(?:\s*#.*[\r\n])*"
            br"(\d+)\s)", buffer).groups()
    except AttributeError as ex:
        raise ValueError(f"Not a raw PGM file: '{input_path}'") from ex

    return np.frombuffer(
        buffer,
        dtype='u1' if int(maxval) < 256 else byteorder + 'u2',
        count=int(width) * int(height),
        offset=len(header)).reshape((int(width), int(height)), order="F")


def write_pgm(array, bytes_per_sample, output_path, byteorder=">"):
    """Write a 2D array indexed with [x,y] into output_path with PGM format.
    """
    assert bytes_per_sample in [1, 2], \
        f"bytes_per_sample={bytes_per_sample} not supported"
    assert len(array.shape) == 2, "Only 2D arrays can be output as PGM"
    assert (array.astype(int) - array < 2 * sys.float_info.epsilon).all(), \
        "Only integer values can be stored in PGM"
    assert array.min() >= 0, "Only positive values can be stored in PGM"
    assert array.max() <= 2 ** (8 * bytes_per_sample) - 1, \
        f"All values should be representable in {bytes_per_sample} bytes " \
        f"(max is {array.max()}, bytes_per_sample={bytes_per_sample})"
    width, height = array.shape
    with open(output_path, "wb") as output_file:
        output_file.write(
            f"P5\n{width}\n{height}\n"
            f"{(2 ** (8 * bytes_per_sample)) - 1}\n".encode("utf-8"))
        array.swapaxes(0, 1).astype(f"{byteorder}u{bytes_per_sample}").tofile(
            output_file)


def read_ppm(input_path, byteorder='>'):
    """Return image data from a raw PGM file as numpy array.
    Format specification: http://netpbm.sourceforge.net/doc/pgm.html

    (From answer:
    https://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm)
    """
    with open(input_path, 'rb') as input_file:
        buffer = input_file.read()
    try:
        header, width, height, maxval = re.search(
            rb"(^P6\s(?:\s*#.*[\r\n])*"
            rb"(\d+)\s(?:\s*#.*[\r\n])*"
            rb"(\d+)\s(?:\s*#.*[\r\n])*"
            rb"(\d+)\s)", buffer).groups()
    except AttributeError as ex:
        raise ValueError(f"Not a raw PGM file: '{input_path}'") from ex

    return np.frombuffer(
        buffer,
        dtype='u1' if int(maxval) < 256 else byteorder + 'u2',
        count=int(width) * int(height) * 3,
        offset=len(header)).reshape((3, int(width), int(height)),
                                    order="F").swapaxes(0, 2).swapaxes(0, 1)


def write_ppm(array, bytes_per_sample, output_path):
    """Write a 3-component 3D array indexed with [x,y,z] into output_path
    with PPM format.
    """
    assert bytes_per_sample in [1], \
        f"bytes_per_sample={bytes_per_sample} not supported"
    assert len(array.shape) == 3, \
        f"Only 3D arrays can be output as PPM ({array.shape=})"
    assert (array.astype(int) - array < 2 * sys.float_info.epsilon).all(), \
        "Only integer values can be stored in PPM"
    assert array.min() >= 0, "Only positive values can be stored in PPM"
    assert array.max() <= 2 ** (8 * bytes_per_sample) - 1, \
        f"All values should be representable in {bytes_per_sample} bytes " \
        f"(max is {array.max()}, bytes_per_sample={bytes_per_sample})"
    width, height, component_count = array.shape
    assert component_count == 3, \
        f"Only 3D arrays can be output as PPM ({array.shape=})"

    with open(output_path, "wb") as output_file:
        output_file.write(
            f"P6\n{width}\n{height}\n"
            f"{(2 ** (8 * bytes_per_sample)) - 1}\n".encode("utf-8"))
        enb.isets.dump_array_bip(
            array=array, file_or_path=output_file, dtype=np.uint8)


def pgm_to_raw(input_path, output_path):
    """Read a file in PGM format and write its contents in raw format,
    which does not include any geometry or data type information.
    """
    enb.isets.dump_array_bsq(array=read_pgm(input_path),
                             file_or_path=output_path)

def ppm_to_raw(input_path, output_path):
    """Read a file in PPM format and write its contents in raw format,
    which does not include any geometry or data type information.
    """
    enb.isets.dump_array_bsq(array=read_ppm(input_path),
                             file_or_path=output_path)
