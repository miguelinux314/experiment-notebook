#!/usr/bin/env python3
"""Lite archiving format to write several files into a single one.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/08"

import os
import collections


class TarliteWriter:
    """Input a series of file paths and output a single file with
    all the inputs contents, plus some metainformation to reconstruct them.
    Files are stored flatly, i.e., only names are stored,
    discarding any information about their contining dirs.
    """

    def __init__(self, initial_input_paths=None):
        self.input_paths = []
        for path in (initial_input_paths if initial_input_paths else []):
            self.add_file(path)

    def add_file(self, input_path):
        """Add a file path to the list of pending ones. Note that files are
        not read until the write() method is invoked.
        """
        assert os.path.isfile(input_path), f"Input path {input_path} does not exist."
        self.input_paths.append(input_path)

    def write(self, output_path):
        """Save the current list of input paths into output_path.
        """
        assert all(os.path.isfile(p) for p in self.input_paths), \
            "All input paths must exist at the time of writing them."

        sizes_line = ",".join(str(os.path.getsize(p)) for p in self.input_paths)
        names_line = "/".join(os.path.basename(p) for p in self.input_paths)
        with open(output_path, "wb") as output_file:
            output_file.write(f"{sizes_line}\n".encode("utf-8"))
            output_file.write(f"{names_line}\n".encode("utf-8"))
            for input_path in self.input_paths:
                with open(input_path, "rb") as input_file:
                    output_file.write(input_file.read())


class TarliteReader:
    """Extract files created by :class:`TarliteWriter`.
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, tarlite_path):
        self.input_path = tarlite_path

    def extract_all(self, output_dir_path):
        """Extract all files to `output_dir_path`.
        """
        bn_count = collections.defaultdict(int)
        with open(self.input_path, "rb") as input_file:
            file_sizes = [int(e) for e in input_file.readline().decode("utf-8").split(",")]
            file_names = [e.strip() for e in input_file.readline().decode("utf-8").split("/")]
            assert len(file_sizes) == len(file_names)
            for file_size, file_name in zip(file_sizes, file_names):
                count = bn_count[file_name]
                bn_count[file_name] += 1

                output_path = os.path.join(
                    output_dir_path,
                    file_name if count == 0 else f"({count})_{file_name}")
                with open(output_path, "wb") as output_file:
                    output_file.write(input_file.read(file_size))


def tarlite_files(input_paths, output_tarlite_path):
    """Take a list of input paths and combine them into a single tarlite file.
    """
    writer = TarliteWriter(initial_input_paths=input_paths)
    writer.write(output_path=output_tarlite_path)


def untarlite_files(input_tarlite_path, output_dir_path):
    """Take a tarlite file and output the contents into the given directory.
    """
    reader = TarliteReader(tarlite_path=input_tarlite_path)
    reader.extract_all(output_dir_path=output_dir_path)
