#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prototypes of entropy codecs for HK/TM based on XORing of consecutive packets
and run-length encoding of the zero-runs.
"""

import os
import sys
import numpy as np
import pandas as pd
import collections
import math
import re
import contextlib

import codec
from codec import FileInfo
from codec_implementations import hktm
from codec_implementations import bitstream

class Trivial_XOR_Codec(codec.LosslessCodec):
    """Trivial copy-only codec to test {Input,Output}BitStream
    """

    def compress(self, original_path: str, compressed_path: str, original_file_info: codec.FileInfo = None):
        packet_matrix = hktm.read_packet_matrix(path=original_path)
        bytes_per_packet = hktm.read_fixed_length_suffix(path=original_path)
        packet_matrix[1:] ^= packet_matrix[:-1]
        with bitstream.OutputBitStream(path=compressed_path) as obs:
            obs.put_unsigned_value(value=bytes_per_packet, nbits=32)
            for packet in packet_matrix:
                for byte in packet:
                    obs.put_unsigned_value(value=byte, nbits=8)

    def decompress(self, compressed_path: str, reconstructed_path: str, original_file_info: codec.FileInfo = None):
        with bitstream.InputBitStream(path=compressed_path) as ibs:
            bytes_per_packet = ibs.get_unsigned_value(nbits=32)
            read_bytes = bytearray()
            try:
                while True:
                    read_bytes.append(ibs.get_unsigned_value(nbits=8))
            except bitstream.EmptyStreamError:
                pass

            output_file = open(reconstructed_path, "wb")
            output_file.write(read_bytes)
            output_file.close()
            packet_matrix = np.fromfile(reconstructed_path, dtype=np.uint8).reshape(
                (os.path.getsize(reconstructed_path) // bytes_per_packet,
                 bytes_per_packet))
            for packet_index in range(1, packet_matrix.shape[0]):
                for byte_index in range(bytes_per_packet):
                    packet_matrix[packet_index][byte_index] ^= \
                        packet_matrix[packet_index - 1][byte_index]
            packet_matrix.tofile(reconstructed_path)


class XOR_HKTM_VLC(codec.AbstractCodec):
    """Generic variable-length entropy codec for HK/TM packets in the XOR domain
    """

    class Node:
        """A node in the decoding tree of a Variable Length Codec
        """

        def __init__(self, value=None, child_0=None, child_1=None):
            self.value = value
            self.child_0 = child_0
            self.child_1 = child_1

    value_to_word_nbits = None
    decoding_root_node = None

    def get_value_to_word_nbits_table(self):
        raise NotImplementedError(f"Subclasses must implement a method to create a value to word table")

    def compress(self, original_path: str, compressed_path: str, original_file_info: codec.FileInfo = None):
        if self.value_to_word_nbits is None:
            self.value_to_word_nbits = self.get_value_to_word_nbits_table()
            self.decoding_root_node = self.generate_decoding_root()

        packet_matrix = hktm.read_packet_matrix(path=original_path)
        bytes_per_packet = hktm.read_fixed_length_suffix(path=original_path)
        packet_matrix[1:] ^= packet_matrix[:-1]
        with bitstream.OutputBitStream(path=compressed_path) as obs:
            # 2 bytes with the number of bytes per packet
            obs.put_unsigned_value(value=bytes_per_packet, nbits=16)
            # 4 bytes for the number of packets
            obs.put_unsigned_value(value=packet_matrix.shape[0], nbits=64)

            for packet_index, packet in enumerate(packet_matrix):
                packet_bits = hktm.packet_to_bits(packet)
                current_length = 0
                for bit in packet_bits:
                    if bit == 1:
                        self.write_values_codeword(value=current_length + 1, obs=obs)
                        current_length = 0
                    else:
                        current_length += 1
                if current_length > 0:
                    # Emit zeros until end of packet
                    self.write_values_codeword(value=0, obs=obs)

    def decompress(self, compressed_path, reconstructed_path, original_file_info: codec.FileInfo = None):
        if self.decoding_root_node is None:
            self.value_to_word_nbits = self.get_value_to_word_nbits_table()
            self.decoding_root_node = self.generate_decoding_root()

        with bitstream.InputBitStream(path=compressed_path) as ibs, \
                bitstream.OutputBitStream(path=reconstructed_path) as obs:
            bytes_per_packet = ibs.get_unsigned_value(nbits=16)
            bits_per_packet = 8 * bytes_per_packet
            total_packets = ibs.get_unsigned_value(nbits=64)
            packets_written = 0
            while packets_written < total_packets:
                current_bits = []
                try:
                    while len(current_bits) < bits_per_packet:
                        run_length = self.read_next_value(ibs=ibs)
                        if run_length == 0:
                            current_bits.extend([0] * (bits_per_packet - len(current_bits)))
                        else:
                            current_bits.extend([0] * (run_length - 1))
                            current_bits.append(1)
                    if len(current_bits) != bits_per_packet:
                        raise bitstream.CorruptedStreamError(
                            f"Run lengths for the current packet summed {len(current_bits)} bits, "
                            f"but packet length is {bits_per_packet} bits")
                    obs.put_bits(current_bits)
                    packets_written += 1
                except bitstream.EmptyStreamError as ex:
                    if packets_written != total_packets:
                        raise bitstream.CorruptedStreamError(
                            f"written ({packets_written}) != total ({total_packets}) packets") \
                            from ex
                    else:
                        # Compression ended when expected
                        break
            if ibs.current_bit_position < bits_per_packet + 16:
                raise bitstream.CorruptedStreamError(
                    f"ibs@{ibs.current_bit_position}? expected at least {bits_per_packet} bits + header")

        packet_matrix = np.fromfile(reconstructed_path, dtype=np.uint8).reshape(
            (os.path.getsize(reconstructed_path) // bytes_per_packet,
             bytes_per_packet))
        for packet_index in range(1, packet_matrix.shape[0]):
            for byte_index in range(bytes_per_packet):
                packet_matrix[packet_index][byte_index] ^= \
                    packet_matrix[packet_index - 1][byte_index]
        packet_matrix.tofile(reconstructed_path)

    def generate_decoding_root(self):
        """Genenerate the decoding tree for the current codetable
        """

        def word_to_bits(value, max_bits):
            return reversed([min(1, value & (1 << i)) for i in range(max_bits)])

        root_node = self.Node()
        for value, (word, nbits) in self.value_to_word_nbits.items():
            current_node = root_node
            for bit in word_to_bits(value=word, max_bits=nbits):
                assert current_node.value is None
                if bit == 0:
                    if current_node.child_0 is None:
                        current_node.child_0 = self.Node()
                    current_node = current_node.child_0
                else:
                    if current_node.child_1 is None:
                        current_node.child_1 = self.Node()
                    current_node = current_node.child_1
            current_node.value = value
        return root_node

    def read_next_value(self, ibs: bitstream.InputBitStream):
        """Read the next value at the current position of ibs using the current table
        """
        current_node = self.decoding_root_node
        while current_node.value is None:
            if ibs.get_bit() == 1:
                current_node = current_node.child_1
            else:
                current_node = current_node.child_0
        return current_node.value

    def write_values_codeword(self, value, obs: bitstream.OutputBitStream):
        word, nbits = self.value_to_word_nbits[value]
        obs.put_unsigned_value(value=word, nbits=nbits)


class XOR_RLE_PocketTable(XOR_HKTM_VLC, codec.LosslessCodec):
    def get_value_to_word_nbits_table(self):
        """Build the VLC table described in the POCKET+ algorithm
        """
        value_to_word_nbits = collections.OrderedDict({0: (0b10, 2), 1: (0b0, 1)})
        for value in range(2, 34):
            value_to_word_nbits[value] = (0b11000000 + (value - 2), 8)
        for value in range(34, 25000):
            S = 2 * math.floor(math.log2(value - 2) + 1) - 6
            value_to_word_nbits[value] = ((0b111 << S) + (value - 2), S + 3)

        assert value_to_word_nbits[7][0] == 0b11000101
        assert value_to_word_nbits[33][0] == 0b11011111
        assert value_to_word_nbits[34][0] == 0b111100000
        assert value_to_word_nbits[67][0] == 0b11101000001

        return value_to_word_nbits


def geometric_distribution(x, p):
    assert x >= 1, x
    assert 0 < p < 1, p
    return (1 - p) ** (x - 1) * p


class XOR_RLE_HuffmanTable(XOR_HKTM_VLC, codec.LosslessCodec):

    class HuffmanNode:
        def __init__(self, prob, value=None, child_0=None, child_1=None):
            self.prob = prob
            self.value = value
            self.bits = []
            self.child_0 = child_0
            self.child_1 = child_1

        def show(self, level=0):
            print("  " * level + f" : {self.value}(p={self.prob}) {self.bits if self.value is not None else ''}")
            if self.child_0 is not None:
                self.child_0.show(level=level + 1)
            if self.child_1 is not None:
                self.child_1.show(level=level + 1)

        def bits_to_word(self, bits):
            word = 0
            for bit in bits:
                word <<= 1
                word += bit
            return word

        def word_to_bits(self, word, nbits):
            assert 0 <= word < 2**nbits
            bits = []
            for i in range(nbits):
                bits.append(min(1, word & (1 << (nbits - 1 - i))))
            return bits

        def process_into_v2w_dict(self, v2wn_dict):
            """Recursively process this node and all its children adding words to the dictionary
            """
            if self.child_0 is not None:
                self.child_0.process_into_v2w_dict(v2wn_dict=v2wn_dict)
            if self.child_1 is not None:
                self.child_1.process_into_v2w_dict(v2wn_dict=v2wn_dict)
            if self.value is not None:
                assert self.child_0 is None
                assert self.child_1 is None
                assert self.bits
                if isinstance(self.value, str):
                    k = int(re.fullmatch(r"range\(k=(\d+)\)", self.value).group(1))
                    for v in range(2 ** k, 2 ** (k + 1)):
                        offset = v - 2 ** k
                        value_bits = list(self.bits) + self.word_to_bits(offset, nbits=k)
                        assert v+1 not in v2wn_dict
                        v2wn_dict[v+1] = (self.bits_to_word(value_bits), len(value_bits))
                else:
                    assert self.value + 1 not in v2wn_dict
                    v2wn_dict[self.value + 1] = (self.bits_to_word(self.bits), len(self.bits))

    def get_value_to_word_nbits_table(self):
        """Compute a RLE table adapted to the probabilitites found in the curated dataset,
        assuming constant probability within ranges (2^{2+k}, 2^{
        """
        df = pd.read_csv(os.path.join(os.path.dirname(__file__), "saved_dataset_properties.csv"),
                         usecols=["xored_zero_run_length_counts"])
        dict_list = df["xored_zero_run_length_counts"].apply(hktm.parse_dict_string)
        global_length_to_probs = collections.defaultdict(list)
        for length_to_count in dict_list:
            local_sum = sum(length_to_count.values())
            for l, c in length_to_count.items():
                global_length_to_probs[l].append(c / local_sum)
        global_length_to_prob_sum = {l: sum(probs) for l, probs in global_length_to_probs.items()}
        total_prob_sum = sum(global_length_to_prob_sum.values())
        length_to_avg_prob = {l: prob_sum / total_prob_sum for l, prob_sum in global_length_to_prob_sum.items()}

        nodes = []
        for v in [-1, 0, 1, 2, 3]:
            nodes.append(self.HuffmanNode(prob=length_to_avg_prob[v], value=v))
        for k in range(2, 14):
            min_v, max_v = 2 ** k, 2 ** (k + 1)
            range_psum = sum(length_to_avg_prob[v] if v in length_to_avg_prob else 0
                             for v in range(min_v, max_v + 1))
            nodes.append(self.HuffmanNode(prob=range_psum, value=f"range(k={k})"))
        for n in nodes:
            n.prob = round(n.prob, 2)

        while len(nodes) > 1:
            nodes = sorted(nodes, key=lambda n: n.prob, reverse=True)
            child_0, child_1, nodes = nodes[-2], nodes[-1], nodes[:-2]
            nodes.append(self.HuffmanNode(prob=child_0.prob + child_1.prob,
                                          child_0=child_0, child_1=child_1))
        huffman_root = nodes[0]
        value_to_word_nbits = {}
        huffman_root.bits = []
        remaining_nodes = [huffman_root]
        while remaining_nodes:
            current_node = remaining_nodes.pop()
            if current_node.child_0 is not None:
                current_node.child_0.bits = list(current_node.bits) + [0]
                remaining_nodes.append(current_node.child_0)
            if current_node.child_0 is not None:
                current_node.child_1.bits = list(current_node.bits) + [1]
                remaining_nodes.append(current_node.child_1)
            if current_node.value is not None:
                assert current_node.child_0 is None and current_node.child_1 is None
        huffman_root.process_into_v2w_dict(v2wn_dict=value_to_word_nbits)

        with contextlib.redirect_stdout(
                open(os.path.join(os.path.dirname(__file__), "huffman_tree.txt"), "w")):
            huffman_root.show()
            for v, (word, nbits) in sorted(value_to_word_nbits.items()):
                print(f"{v-1}: {bin(word)} ({nbits} bits)")

        return value_to_word_nbits