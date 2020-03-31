#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classes describing sets of images
"""
import collections
import math

__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "31/03/2020"

import numpy as np
import enb.atable as atable
import enb.sets as sets


class ImagePropertiesTable(sets.FilePropertiesTable):
    """Properties table for images
    """
    pass


class ImagePropertiesTable(ImagePropertiesTable):
    @ImagePropertiesTable.column_function("bytes_per_sample", label="Bytes per sample", plot_min=0)
    def set_bytes_per_sample(self, file_path, series):
        if any(s in file_path for s in ("u8be", "u8le")):
            series[_column_name] = 1
        elif any(s in file_path for s in ("u16be", "u16le", "s16be", "s16le")):
            series[_column_name] = 2
        elif any(s in file_path for s in ("u32be", "u32le", "s32be", "s32le")):
            series[_column_name] = 4
        else:
            raise sets.UnkownPropertiesException(f"Unknown {_column_name} for {file_path}")

    @ImagePropertiesTable.column_function("signed", label="Signed samples")
    def set_signed(self, file_path, series):
        if any(s in file_path for s in ("u8be", "u16be", "u16le", "u32be", "u32le")):
            series[_column_name] = False
        elif any(s in file_path for s in ("s8be", "s16be", "s16le", "s32be", "s32le")):
            series[_column_name] = True
        else:
            raise sets.UnkownPropertiesException(f"Unknown {_column_name} for {file_path}")

    @ImagePropertiesTable.column_function("samples", label="Sample count", plot_min=0)
    def set_samples(self, file_path, series):
        """Set the number of samples in the image
        """
        assert series["size_bytes"] % series["bytes_per_sample"] == 0
        series[_column_name] = series["size_bytes"] // series["bytes_per_sample"]

    @ImagePropertiesTable.column_function(
        atable.ColumnProperties(name="1B_value_counts",
                                label="1-byte value counts",
                                semilog_y=True, has_dict_values=True))
    def set_1B_value_counts(self, file_path, series):
        """Calculate a dict with the counts for each (unsigned) byte value
        found in file_path
        """
        series[_column_name] = dict(collections.Counter(
            np.fromfile(file_path, dtype="uint8").flatten()))

    @ImagePropertiesTable.column_function(
        "entropy_1B_bps", label="Entropy (bps, 1-byte samples)", plot_min=0, plot_max=8)
    def set_file_entropy(self, file_path, series):
        """Return the zero-order entropy of the data in file_path (1-byte samples are assumed)
        """
        value_count_dict = series["1B_value_counts"]
        total_sum = sum(value_count_dict.values())
        probabilities = [count / total_sum for count in value_count_dict.values()]
        series[_column_name] = - sum(p * math.log2(p) for p in probabilities)
        assert abs(series[_column_name] - entropy(np.fromfile(file_path, dtype="uint8"))) < 1e-12

    @ImagePropertiesTable.column_function(
        [f"byte_value_{s}" for s in ["min", "max", "avg", "std"]])
    def set_byte_value_extrema(self, file_path, series):
        contents = np.fromfile(file_path, dtype="uint8")
        series["byte_value_min"] = contents.min()
        series["byte_value_max"] = contents.max()
        series["byte_value_avg"] = contents.mean()
        series["byte_value_std"] = contents.std()

    @ImagePropertiesTable.column_function(
        "histogram_fullness_1byte", label="Histogram usage fraction (1 byte)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_1byte(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering unsigned  1-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint8)).size / (2 ** 8)
        assert 0 <= series[_column_name] <= 1

    @ImagePropertiesTable.column_function(
        "histogram_fullness_2bytes", label="Histogram usage fraction (2 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_2bytes(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering unsigned 2-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint16)).size / (2 ** 16)
        assert 0 <= series[_column_name] <= 1

    @ImagePropertiesTable.column_function(
        "histogram_fullness_4bytes", label="Histogram usage fraction (4 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_4bytes(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering 4-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint32)).size / (2 ** 32)
        assert 0 <= series[_column_name] <= 1


def entropy(data):
    """Compute the zero-order entropy of the provided data
    """
    counter = collections.Counter(np.array(data, copy=False).flatten())
    total_sum = sum(counter.values())
    probabilities = (count / total_sum for value, count in counter.items())
    return -sum(p * math.log2(p) for p in probabilities)
