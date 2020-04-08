#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module to handle pgm images
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "08/04/2020"

import sys
import numpy as np
import re


def read_pgm(input_path, byteorder='>'):
    """Return image data from a raw PGM file as numpy array.
    Format specification: http://netpbm.sourceforge.net/doc/pgm.html

    (From answer: https://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm)
    """
    with open(input_path, 'rb') as input_file:
        buffer = input_file.read()
    try:
        header, width, height, maxval = re.search(
            b"(^P5\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n]\s)*)", buffer).groups()
    except AttributeError as ex:
        raise ex
        raise ValueError(f"Not a raw PGM file: '{input_path}'")
    return np.frombuffer(
        buffer,
        dtype='u1' if int(maxval) < 256 else byteorder + 'u2',
        count=int(width) * int(height),
        offset=len(header)).reshape((int(height), int(width))).swapaxes(0,1)

def write_pgm(array, bytes_per_sample, output_path, byteorder=">"):
    assert bytes_per_sample in [1,2], f"bytes_per_sample={bytes_per_sample} not supported"
    assert len(array.shape) == 2, f"Only 2D arrays can be output as PGM"
    assert (array.astype(np.int) - array < 2*sys.float_info.epsilon).all(), f"Only integer values can be stored in PGM"
    assert array.min() >= 0, f"Only positive values can be stored in PGM"
    assert array.max() <= 2**(8*bytes_per_sample) - 1, \
        f"All values should be representable in {bytes_per_sample} bytes " \
        f"(max is {array.max()}, bytes_per_sample={bytes_per_sample})"
    width, height = array.shape
    with open(output_path, "wb") as output_file:
        output_file.write(f"P5\n{width}\n{height}\n{(2**(8*bytes_per_sample))-1}\n".encode("utf-8"))
        array.swapaxes(0,1).astype(f"{byteorder}u{bytes_per_sample}").tofile(output_file)
