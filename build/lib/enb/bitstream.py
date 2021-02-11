#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tools to handle binary streams at the bit level
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "01/12/2019"

import os
import collections

class OutputBitStream:
    """Class that allows writing individual bits to a file.
    """
    pending_bit_buffer_size = 1024

    def __init__(self, path, append=False):
        self.path = path
        self.append = append
        self.file = open(self.path, "wb" if self.append is False else "ab")
        self.pending_bits = []  # Bits to be flushed, in that order
        self._put_bit_count = 0

    @property
    def current_bit_position(self):
        return self._put_bit_count

    def put_bit(self, bit):
        """Put a single bit in the stream
        """
        self.pending_bits.append(bit)
        if len(self.pending_bits) > self.pending_bit_buffer_size:
            self.flush_complete_bytes()
        self._put_bit_count += 1

    def put_bits(self, bits):
        self.pending_bits.extend(bits)
        if len(self.pending_bits) > self.pending_bit_buffer_size:
            self.flush_complete_bytes()
        self._put_bit_count += len(bits)

    def put_unsigned_value(self, value, nbits):
        """Put an unsigned value represented in nbits, from MSB to LSB.
        """
        assert 0 <= value <= 2 ** nbits - 1
        for i in reversed(range(nbits)):
            self.pending_bits.append(min(1, value & (1 << i)))
        if len(self.pending_bits) > self.pending_bit_buffer_size:
            self.flush_complete_bytes()
        self._put_bit_count += nbits

    def close(self):
        """Close and flush any remaining bits
        """
        self.flush()
        self.file.close()
        self.file = None

    def flush(self):
        """Flush all data put in self (but don't close)
        """
        self.flush_complete_bytes()
        if self.pending_bits:
            assert len(self.pending_bits) < 8, len(self.pending_bits)
            byte = sum(bit << (7 - i) for i, bit in enumerate(self.pending_bits[:8]))
            output_bytes = bytearray()
            output_bytes.append(byte)
            self.file.write(output_bytes)
            self.pending_bits = []

    def flush_complete_bytes(self):
        """Flush only complete bytes stored
        """
        assert self.file is not None
        assert not any(b != 0 and b != 1 for b in self.pending_bits)
        output_bytes = bytearray()
        while len(self.pending_bits) >= 8:
            output_byte = sum(bit << (7 - i) for i, bit in enumerate(self.pending_bits[:8]))
            output_bytes.append(output_byte)
            self.pending_bits = self.pending_bits[8:]
        self.file.write(output_bytes)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        if self.file is not None:
            self.close()

class EmptyStreamError(Exception):
    pass

class CorruptedStreamError(Exception):
    pass

class InputBitStream:
    def __init__(self, path):
        self.path = path
        file = open(self.path, "rb")
        self.contents = file.read()
        file.close()
        self.current_bit_position = 0

    def get_bit(self):
        """Read the next bit in the stream

        :raises EmptyStreamError if trying to read beyond the file limit
        """
        try:
            current_byte = self.contents[self.current_bit_position >> 3]
        except IndexError:
            raise EmptyStreamError(f"Attempting read at bit position {self.current_bit_position} "
                                   f"(byte {self.current_bit_position >> 3})")
        bit = min(1, current_byte & (1 << (7 - (self.current_bit_position % 8))))
        self.current_bit_position += 1
        return bit

    def get_unsigned_value(self, nbits):
        """Read the next nbit unsigned representation
        """
        next_bits = (self.get_bit() for _ in range(nbits))
        return sum(bit << (nbits - 1 - i) for i, bit in enumerate(next_bits))

    def peek_unsigned_value(self, nbits):
        original_bit_position = self.current_bit_position
        try:
            return self.get_unsigned_value(nbits=nbits)
        finally:
            self.current_bit_position = original_bit_position

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass



