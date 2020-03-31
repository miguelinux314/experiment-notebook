#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Basic tools to deal with HK/TM files
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "01/12/2019"

import os
import re
import glob
import argparse
import numpy as np

dataset_folder = os.path.join(os.path.dirname(__file__), "../datasets/")


def get_all_test_files():
    assert os.path.isdir(dataset_folder)
    return sorted(glob.glob(os.path.join(dataset_folder, "**", "*.raw"), recursive=True),
                  key=lambda p: os.path.getsize(p))


def read_fixed_length_suffix(path):
    """Read the fixed length tag of a curated file path
    """
    return int(re.search(r".FL(\d+)bytes.raw", path).group(1))


def read_packet_matrix(path):
    bytes_per_packet = read_fixed_length_suffix(path)
    packets = os.path.getsize(path) // bytes_per_packet
    assert os.path.getsize(path) == packets * bytes_per_packet
    packet_matrix = np.fromfile(path, dtype=np.uint8)
    packet_matrix.resize((packets, bytes_per_packet))
    return packet_matrix


def packet_to_bits(packet):
    """Transform a packet in a list of 0s and 1s (integerss),
    with 8 times as many elements as bytes in the packet.
    :return: a list of bits (integers equal to 0 or to 1),
    where index 0 denotes the MSB of the first byte
    of the packet.
    """
    bits = []
    for byte_index, packet_byte in enumerate(packet):
        for bit_index in range(8):
            bits.append(min(1, packet_byte & (1 << (7-bit_index))))
    assert all(b == 1 or b == 0 for b in bits)
    return bits


def parse_dict_string(cell_value, key_type=float, value_type=float):
    """Parse a cell value for a string describing a dictionary.
    Some checks are performed based on ATable cell contents, i.e.,
      - if a dict is found it is returned directly
      - a Nan (empty cell) is also returned directly
      - otherwise a string starting by '{' and ending by '}' with 'key:value' pairs
        separated by ',' (and possibly spaces) is returned
    :param key_type: if not None, the key is substituted by a instantiation
      of that type with the key as argument
  :param value_type: if not None, the value is substituted by a instantiation
      of that type with the value as argument
    """
    if isinstance(cell_value, dict):
        return cell_value
    try:
        assert cell_value[0] == "{", (cell_value[0], f">>{cell_value}<<")
        assert cell_value[-1] == "}", (cell_value[-1], f">>{cell_value}<<")
    except TypeError as ex:
        if cell_value is None or math.isnan(cell_value):
            return cell_value
        raise TypeError(f"Trying to parse a dict string '{cell_value}', "
                        f"wrong type {type(cell_value)} found instead. "
                        f"Double check the has_dict_values column property.") from ex
    cell_value = cell_value[1:-1]
    column_dict = dict()
    for pair in cell_value.split(","):
        a, b = [s.strip() for s in pair.split(":")]
        if key_type is not None:
            a = key_type(a)
        if value_type is not None:
            b = value_type(b)
        assert a not in column_dict, f"A non-unique-key ({a}) dictionary string was found {cell_value}"
        column_dict[a] = b
    return column_dict
