#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Image sets information tables
"""

import os
import math
import numpy as np
import re
import collections

from enb import atable
from enb import sets

__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "01/04/2020"


def entropy(data):
    """Compute the zero-order entropy of the provided data
    """
    counter = collections.Counter(np.array(data, copy=False).flatten())
    total_sum = sum(counter.values())
    probabilities = (count / total_sum for value, count in counter.items())
    return -sum(p * math.log2(p) for p in probabilities)


class ImagePropertiesTable(sets.FilePropertiesTable):
    """Properties table for images. Allows automatic handling of tags in
    filenames, e.g., ZxYxX_u16be.
    """

    @atable.column_function("bytes_per_sample", label="Bytes per sample", plot_min=0)
    def set_bytes_per_sample(self, file_path, series):
        if any(s in file_path for s in ("u8be", "u8le", "s8be", "s8le")):
            series[_column_name] = 1
        elif any(s in file_path for s in ("u16be", "u16le", "s16be", "s16le")):
            series[_column_name] = 2
        elif any(s in file_path for s in ("u32be", "u32le", "s32be", "s32le")):
            series[_column_name] = 4
        else:
            raise sets.UnkownPropertiesException(f"Unknown {_column_name} for {file_path}")

    @atable.column_function("signed", label="Signed samples")
    def set_signed(self, file_path, series):
        if any(s in file_path for s in ("u8be", "u16be", "u16le", "u32be", "u32le")):
            series[_column_name] = False
        elif any(s in file_path for s in ("s8be", "s16be", "s16le", "s32be", "s32le")):
            series[_column_name] = True
        else:
            raise sets.UnkownPropertiesException(f"Unknown {_column_name} for {file_path}")

    @atable.column_function("big_endian", label="Big endian?")
    def set_big_endian(self, file_path, series):
        if any(s in file_path for s in ("u8be", "u16be", "u32be", "s8be", "s16be", "s32be")):
            series[_column_name] = True
        elif any(s in file_path for s in ("u8le", "u16le", "u32le", "s8le", "s16le", "s32le")):
            series[_column_name] = False
        else:
            raise sets.UnkownPropertiesException(f"Unknown {_column_name} for {file_path}")

    @atable.column_function("samples", label="Sample count", plot_min=0)
    def set_samples(self, file_path, series):
        """Set the number of samples in the image
        """
        assert series["size_bytes"] % series["bytes_per_sample"] == 0
        series[_column_name] = series["size_bytes"] // series["bytes_per_sample"]

    @atable.column_function([
        atable.ColumnProperties(name="width", label="Width", plot_min=1),
        atable.ColumnProperties(name="height", label="Height", plot_min=1),
        atable.ColumnProperties(name="component_count", label="Components", plot_min=1),
    ])
    def set_image_geometry(self, file_path, series):
        """Obtain the image's geometry (width, height and number of components)
        based on the filename tags (and possibly its size)
        """
        match = re.search(r"(\d+)x(\d+)x(\d+)", file_path)
        if match:
            component_count, height, width = (int(match.group(i)) for i in range(1, 3 + 1))
            if any(dim < 1 for dim in (width, height, component_count)):
                raise ValueError(f"Invalid dimension tag in {file_path}")
            series["width"], series["height"], series["component_count"] = \
                width, height, component_count
            assert os.path.getsize(file_path) == width * height * component_count * series["bytes_per_sample"]
            assert series["samples"] == width*height*component_count
            return

        raise ValueError("Cannot determine image geometry "
                         f"from file name {os.path.basename(file_path)}")

    @atable.column_function(
        atable.ColumnProperties(name="1B_value_counts",
                                label="1-byte value counts",
                                semilog_y=True, has_dict_values=True))
    def set_1B_value_counts(self, file_path, series):
        """Calculate a dict with the counts for each (unsigned) byte value
        found in file_path
        """
        series[_column_name] = dict(collections.Counter(
            np.fromfile(file_path, dtype="uint8").flatten()))

    @atable.column_function(
        "entropy_1B_bps", label="Entropy (bps, 1-byte samples)", plot_min=0, plot_max=8)
    def set_file_entropy(self, file_path, series):
        """Return the zero-order entropy of the data in file_path (1-byte samples are assumed)
        """
        value_count_dict = series["1B_value_counts"]
        total_sum = sum(value_count_dict.values())
        probabilities = [count / total_sum for count in value_count_dict.values()]
        series[_column_name] = - sum(p * math.log2(p) for p in probabilities)
        assert abs(series[_column_name] - entropy(np.fromfile(file_path, dtype="uint8"))) < 1e-12

    @atable.column_function(
        [f"byte_value_{s}" for s in ["min", "max", "avg", "std"]])
    def set_byte_value_extrema(self, file_path, series):
        contents = np.fromfile(file_path, dtype="uint8")
        series["byte_value_min"] = contents.min()
        series["byte_value_max"] = contents.max()
        series["byte_value_avg"] = contents.mean()
        series["byte_value_std"] = contents.std()

    @atable.column_function(
        "histogram_fullness_1byte", label="Histogram usage fraction (1 byte)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_1byte(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering unsigned  1-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint8)).size / (2 ** 8)
        assert 0 <= series[_column_name] <= 1

    @atable.column_function(
        "histogram_fullness_2bytes", label="Histogram usage fraction (2 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_2bytes(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering unsigned 2-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint16)).size / (2 ** 16)
        assert 0 <= series[_column_name] <= 1

    @atable.column_function(
        "histogram_fullness_4bytes", label="Histogram usage fraction (4 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_4bytes(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering 4-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint32)).size / (2 ** 32)
        assert 0 <= series[_column_name] <= 1
