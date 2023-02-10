#!/usr/bin/env python3
"""Module to handle PGM (P5) and PPM (P6) images
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/08"

import sys
import re
import numpy as np
import enb.isets


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


def read_ppm(input_path, byteorder='>'):
    """Return image data from a raw PGM file as numpy array.
    Format specification: http://netpbm.sourceforge.net/doc/pgm.html

    (From answer: https://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm)
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


def write_ppm(array, bytes_per_sample, output_path):
    """Write a 3-component 3D array indexed with [x,y,z] into output_path
    with PPM format.
    """
    assert bytes_per_sample in [
        1], f"bytes_per_sample={bytes_per_sample} not supported"
    assert len(
        array.shape) == 3, f"Only 3D arrays can be output as PPM ({array.shape=})"
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
        values = []
        # pylint: disable=invalid-name
        for y in range(array.shape[1]):
            for x in range(array.shape[0]):
                for z in range(array.shape[2]):
                    values.append(array[x, y, z])
        output_file.write(bytes(values))


def pgm_to_raw(input_path, output_path):
    """Read a file in PGM format and write its contents in raw format,
    which does not include any geometry or data type information.
    """
    enb.isets.dump_array_bsq(array=read_pgm(input_path),
                             file_or_path=output_path)
