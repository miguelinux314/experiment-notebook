#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Image sets information tables
"""

import os
import math
import numpy as np
import re
import collections
import copy
import imageio

from enb.config import get_options

options = get_options(from_main=False)

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


def file_path_to_geometry_dict(file_path, existing_dict=None):
    """Return a dict with basic geometry dict based on the file path and the file size.

    :param existing_dict: if not None, the this dict is updated and then returned. If None,
      a new dictionary is created.
    """
    row = existing_dict if existing_dict is not None else {}
    matches = re.findall(r"(\d+)x(\d+)x(\d+)", file_path)
    if matches:
        match = matches[-1]
        if len(matches) > 1 and options.verbose:
            print(f"[W]arning: file path {file_path} contains more than one image geometry tag. "
                  f"Only the last one is considered.")
        component_count, height, width = (int(match[i]) for i in range(3))
        if any(dim < 1 for dim in (width, height, component_count)):
            raise ValueError(f"Invalid dimension tag in {file_path}")
        row["width"], row["height"], row["component_count"] = \
            width, height, component_count

        assert os.path.getsize(file_path) == width * height * component_count * row["bytes_per_sample"], \
            (file_path, os.path.getsize(file_path), width, height, component_count,
             width * height * component_count * row["bytes_per_sample"])
        assert row["samples"] == width * height * component_count
    else:
        raise ValueError("Cannot determine image geometry "
                         f"from file name {os.path.basename(file_path)}")
    return row


class ImageGeometryTable(sets.FilePropertiesTable):
    """Basic properties table for images, including geometry.
    Allows automatic handling of tags in filenames, e.g., ZxYxX_u16be.
    """

    @atable.column_function("bytes_per_sample", label="Bytes per sample", plot_min=0)
    def set_bytes_per_sample(self, file_path, row):
        if any(s in file_path for s in ("u8be", "u8le", "s8be", "s8le")):
            row[_column_name] = 1
        elif any(s in file_path for s in ("u16be", "u16le", "s16be", "s16le")):
            row[_column_name] = 2
        elif any(s in file_path for s in ("u32be", "u32le", "s32be", "s32le")):
            row[_column_name] = 4
        else:
            raise sets.UnkownPropertiesException(f"Unknown {_column_name} for {file_path}")

    @atable.column_function("signed", label="Signed samples")
    def set_signed(self, file_path, row):
        if any(s in file_path for s in ("u8be", "u16be", "u16le", "u32be", "u32le")):
            row[_column_name] = False
        elif any(s in file_path for s in ("s8be", "s16be", "s16le", "s32be", "s32le")):
            row[_column_name] = True
        else:
            raise sets.UnkownPropertiesException(f"Unknown {_column_name} for {file_path}")

    @atable.column_function("big_endian", label="Big endian?")
    def set_big_endian(self, file_path, row):
        if any(s in file_path for s in ("u8be", "u16be", "u32be", "s8be", "s16be", "s32be")):
            row[_column_name] = True
        elif any(s in file_path for s in ("u8le", "u16le", "u32le", "s8le", "s16le", "s32le")):
            row[_column_name] = False
        else:
            raise sets.UnkownPropertiesException(f"Unknown {_column_name} for {file_path}")

    @atable.column_function("samples", label="Sample count", plot_min=0)
    def set_samples(self, file_path, row):
        """Set the number of samples in the image
        """
        assert row["size_bytes"] % row["bytes_per_sample"] == 0
        row[_column_name] = row["size_bytes"] // row["bytes_per_sample"]

    @atable.column_function([
        atable.ColumnProperties(name="width", label="Width", plot_min=1),
        atable.ColumnProperties(name="height", label="Height", plot_min=1),
        atable.ColumnProperties(name="component_count", label="Components", plot_min=1),
    ])
    def set_image_geometry(self, file_path, row):
        """Obtain the image's geometry (width, height and number of components)
        based on the filename tags (and possibly its size)
        """
        file_path_to_geometry_dict(file_path=file_path, existing_dict=row)


class ImagePropertiesTable(ImageGeometryTable):
    """Properties table for images, with geometry and additional statistical information.
    Allows automatic handling of tags in filenames, e.g., ZxYxX_u16be.
    """

    @atable.column_function([
        atable.ColumnProperties(name="sample_min", label="Min sample value"),
        atable.ColumnProperties(name="sample_max", label="Max sample value")])
    def set_sample_extrema(self, file_path, row):
        array = load_array_bsq(file_or_path=file_path, image_properties_row=row).flatten()
        row["sample_min"], row["sample_max"] = array.min(), array.max()
        assert row["sample_min"] == int(row["sample_min"])
        assert row["sample_max"] == int(row["sample_max"])
        row["sample_min"] = int(row["sample_min"])
        row["sample_max"] = int(row["sample_max"])

    @atable.column_function("dynamic_range_bits", label="Dynamic range (bits)")
    def set_dynamic_range_bits(self, file_path, row):
        range_len = int(row["sample_max"]) - int(row["sample_min"])
        assert range_len >= 0, (file_path, row["sample_max"], row["sample_min"], range_len)
        row[_column_name] = max(1, math.ceil(math.log2(range_len + 1)))

    @atable.column_function(
        "entropy_1B_bps", label="Entropy (bps, 1-byte samples)", plot_min=0, plot_max=8)
    def set_file_entropy(self, file_path, row):
        """Return the zero-order entropy of the data in file_path (1-byte samples are assumed)
        """
        row[_column_name] = entropy(np.fromfile(file_path, dtype="uint8").flatten())

    @atable.column_function(
        "entropy_2B_bps", label="Entropy (bps, 2-byte samples)", plot_min=0, plot_max=16)
    def set_file_entropy(self, file_path, row):
        """Set the zero-order entropy of the data in file_path (2-byte samples are assumed)
        if bytes_per_sample is a multiple of 2, otherwise the column is set to -1
        """
        if row["bytes_per_sample"] % 2 != 0:
            row[_column_name] = -1
        else:
            row[_column_name] = entropy(np.fromfile(file_path, dtype=np.uint16).flatten())

    @atable.column_function(
        [f"byte_value_{s}" for s in ["min", "max", "avg", "std"]])
    def set_byte_value_extrema(self, file_path, row):
        contents = np.fromfile(file_path, dtype="uint8")
        row["byte_value_min"] = contents.min()
        row["byte_value_max"] = contents.max()
        row["byte_value_avg"] = contents.mean()
        row["byte_value_std"] = contents.std()


class HistogramFullnessTable1Byte(atable.ATable):
    @atable.column_function(
        "histogram_fullness_1byte", label="Histogram usage fraction (1 byte)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_1byte(self, file_path, row):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering unsigned  1-byte samples.
        """
        row[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint8)).size / (2 ** 8)
        assert 0 <= row[_column_name] <= 1

class HistogramFullnessTable2Bytes(atable.ATable):
    @atable.column_function(
        "histogram_fullness_2bytes", label="Histogram usage fraction (2 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_2bytes(self, file_path, row):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering unsigned 2-byte samples.
        """
        row[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint16)).size / (2 ** 16)
        assert 0 <= row[_column_name] <= 1

class HistogramFullnessTable4Bytes(atable.ATable):
    @atable.column_function(
        "histogram_fullness_4bytes", label="Histogram usage fraction (4 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_4bytes(self, file_path, row):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering 4-byte samples.
        """
        row[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint32)).size / (2 ** 32)
        assert 0 <= row[_column_name] <= 1


class BandEntropyTable(ImageGeometryTable):
    """Table to calculate the entropy of each band
    """

    @atable.column_function("entropy_per_band", label="Entropy per band", has_dict_values=True)
    def set_entropy_per_band(self, file_path, row):
        """Store a dictionary indexed by band index (zero-indexed) with values
        being entropy in bits per sample.
        """
        array = load_array_bsq(file_or_path=file_path, image_properties_row=row)
        row[_column_name] = {i: entropy(array[:, :, i].flatten())
                             for i in range(row["component_count"])}


def load_array_bsq(file_or_path, image_properties_row):
    """Load a numpy array indexed by [x,y,z] from file_or_path using
    the geometry information in image_properties_row.
    """

    return np.fromfile(file_or_path,
                       dtype=iproperties_row_to_numpy_dtype(image_properties_row)).reshape(
        (image_properties_row["component_count"],
         image_properties_row["height"],
         image_properties_row["width"])).swapaxes(0, 2)


def dump_array_bsq(array, file_or_path, mode="wb", dtype=None):
    """Dump an array indexed in [x,y,z] order into a band sequential (BSQ) ordering,
    i.e., the concatenation of each component (z axis), each component in raster
    order.

    :param file_or_path: It can be either a file-like object, or a string-like
      object. If it is a file, contents are writen without altering the file
      pointer beforehand. In this case, the file is not closed afterwards.
      If it is a string-like object, it will be interpreted
      as a file path, open as determined by the mode parameter.
    :param mode: if file_or_path is a path, the output file is opened in this mode
    :param dtype: if not None, the array is casted to this type before dumping

    """
    try:
        assert not file_or_path.closed, f"Cannot dump to a closed file"
        open_here = False
    except AttributeError:
        file_or_path = open(file_or_path, mode)
        open_here = True

    array = array.swapaxes(0, 2)
    if dtype is not None and array.dtype != dtype:
        array = array.astype(dtype)
    array.tofile(file_or_path)

    if open_here:
        file_or_path.close()


def iproperties_row_to_numpy_dtype(image_properties_row):
    """Return a string that identifies the most simple numpy dtype needed
    to represent an image with properties as defined in
    image_properties_row
    """
    return ((">" if image_properties_row["big_endian"] else "<")
            if image_properties_row["bytes_per_sample"] > 1 else "") \
           + ("i" if image_properties_row["signed"] else "u") \
           + str(image_properties_row["bytes_per_sample"])


def iproperties_row_to_sample_type_tag(image_properties_row):
    """Return a sample type name tag as recognized by isets (e.g., u16be),
    given an object similar to an ImageGeometryTable row.
    """
    assert image_properties_row["signed"] in [True, False]
    assert image_properties_row["bytes_per_sample"] in [1, 2, 3, 4]
    assert image_properties_row["big_endian"] in [True, False]

    return ("s" if image_properties_row["signed"] else "u") \
           + str(8 * image_properties_row["bytes_per_sample"]) \
           + ("be" if image_properties_row["big_endian"] else "le")


def iproperties_row_to_geometry_tag(image_properties_row):
    """Return an image geometry name tag recognized by isets (e.g., 3x600x800
    for an 800x600, 3 component image), 
    given an object similar to an ImageGeometryTable row.
    """
    return f"{image_properties_row['component_count']}" \
           f"x{image_properties_row['height']}" \
           f"x{image_properties_row['width']}"


def iproperties_to_name_tag(width, height, component_count, big_endian, bytes_per_sample, signed):
    """Return a full name tag (including sample type and dimension information),
    recognized by isets.
    """
    row = dict(width=width, height=height, component_count=component_count,
               big_endian=big_endian, bytes_per_sample=bytes_per_sample,
               signed=signed)
    return f"{iproperties_row_to_sample_type_tag(row)}" \
           f"-{iproperties_row_to_geometry_tag(row)}"

def raw_path_to_png(raw_path, image_properties_row, png_path):
    img = load_array_bsq(file_or_path=raw_path, image_properties_row=image_properties_row)
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    imageio.imwrite(png_path, img.swapaxes(0,1), format="png")