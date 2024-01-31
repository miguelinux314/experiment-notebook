#!/usr/bin/env python3
"""Image sets information tables
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/01"

import os
import math
import re
import numpy as np
import enb
from enb import atable
from enb import sets


# pylint: disable=no-self-use

def entropy(data):
    """Compute the zero-order entropy of the provided data
    """
    values, count = np.unique(data.flatten(), return_counts=True)
    total_sum = sum(count)
    probabilities = (count / total_sum for value, count in zip(values, count))
    return -sum(p * math.log2(p) for p in probabilities)


def mutual_information(data1, data2):
    """Compute the mutual information between two vectors of identical length
    after flattening. Implemented following
    https://en.wikipedia.org/wiki/Mutual_information#Definition
    """
    # pylint: disable=too-many-locals
    # x: data1
    values1, counts1 = np.unique(data1.flatten(), return_counts=True)
    total_sum1 = counts1.sum()
    probabilities1 = (c / total_sum1 for v, c in zip(values1, counts1))
    entropy_x = -sum(p * math.log2(p) for p in probabilities1)

    # y: data1
    values2, counts2 = np.unique(data2.flatten(), return_counts=True)
    total_sum2 = counts2.sum()
    assert total_sum1 == total_sum2
    probabilities2 = (c / total_sum2 for v, c in zip(values2, counts2))
    entropy_y = -sum(p * math.log2(p) for p in probabilities2)

    # joint (x,y)
    bin_count = max(max(v) for v in (values1, values2)) - min(
        min(v) for v in (values1, values2)) + 1
    count_xy = np.histogram2d(data1.flatten(), data2.flatten(), bin_count)[
        0].flatten()
    total_sum_xy = count_xy.sum()
    assert total_sum_xy == total_sum1
    probabilities_xy = count_xy / total_sum_xy
    entropy_xy = -sum(p * math.log2(p) for p in probabilities_xy if p != 0)

    return entropy_x + entropy_y - entropy_xy


def kl_divergence(data1, data2):
    """Return KL(P||Q), KL(Q||P) KL is the KL divergence in bits per sample,
    P is the sample probability distribution of data1, Q is the sample
    probability distribution of data2.

    If both P and Q contain the same values (even if with different counts),
    both returned values are identical and as defined in
    https://en.wikipedia.org/wiki/Kullback%E2%80%93Leibler_divergence#Definition.

    Otherwise, the formula is modified so that whenever p or q is 0,
    the factor is skipped from the count. In this case, the two values most
    likely differ and they should be carefully interpreted.
    """
    # x: data1
    values1, counts1 = np.unique(data1.flatten(), return_counts=True)
    total_sum1 = counts1.sum()
    probabilities1 = {v: c / total_sum1 for v, c in zip(values1, counts1)}

    # y: data1
    values2, counts2 = np.unique(data2.flatten(), return_counts=True)
    total_sum2 = counts2.sum()
    assert total_sum1 == total_sum2
    probabilities2 = {v: c / total_sum2 for v, c in zip(values2, counts2)}

    kl_pq = sum(
        probabilities1[k] * math.log(probabilities1[k] / probabilities2[k])
        if k in probabilities2 and probabilities1[k] != 0 and probabilities2[
            k] != 0 else 0
        for k in probabilities1.keys())
    kl_qp = sum(
        probabilities2[k] * math.log(probabilities2[k] / probabilities1[k])
        if k in probabilities1 and probabilities1[k] != 0 and probabilities2[
            k] != 0 else 0
        for k in probabilities2.keys())

    return kl_pq, kl_qp


def file_path_to_geometry_dict(file_path, existing_dict=None,
                               verify_file_size=True):
    """Return a dict with basic geometry dict based on the file path and the
    file size. The basename of the file should contain something like
    u8be-3x1000x2000, where u8be is the data format (unsigned, 8 bits per
    sample, big endian) and the dimensions are ZxYxX (Z=3, Y=1000 and X=2000
    in this example).

    :param file_path: file path whose basename is used to determine the image geometry.
    :param existing_dict: if not None, the this dict is updated and then returned. If None,
      a new dictionary is created.
    :param verify_file_size: if True, file_path is expected to be exactly
      Z*X*Y*byte_per_samples bytes.
      Otherwise an exception is thrown.
    """
    row = existing_dict if existing_dict is not None else {}
    matches = re.findall(r"(\d+)x(\d+)x(\d+)", os.path.basename(file_path))
    if matches:
        if len(matches) > 1:
            raise ValueError(
                f"File path {file_path} contains more than one image geometry tag. "
                f"Matches: {repr(matches)}.")
        match = matches[0]
        component_count, height, width = (int(match[i]) for i in range(3))
        if any(dim < 1 for dim in (width, height, component_count)):
            raise ValueError(f"Invalid dimension tag in {file_path}")
        row["width"], row["height"], row["component_count"] = \
            width, height, component_count

        _file_path_to_datatype_dict(file_path, row)

        if verify_file_size:
            if os.path.getsize(file_path) != width * height * component_count * row["bytes_per_sample"]:
                raise ValueError(f"Found invalid file size {os.path.getsize(file_path)} bytes. Expected "
                                 f"{width * height * component_count * row['bytes_per_sample']} bytes "
                                 f"for {width=}, {height=}, {component_count=}, "
                                 f"bytes_per_sample={row['bytes_per_sample']}")
            assert row["samples"] == width * height * component_count
    elif any(c not in row for c in ("width", "height", "component_count", "samples")):
        enb.logger.debug(
            "Cannot determine image geometry (X, Y, Z dimensions; number of samples) "
            f"from file name {os.path.basename(file_path)}.")
        return {}
    return row


def _file_path_to_datatype_dict(file_path, existing_dict=None):
    """Given a file path, try to extract the data type properties from
    the name tag."""
    # pylint: disable=too-many-statements,too-many-branches
    existing_dict = existing_dict if existing_dict is not None else {}

    base_name = os.path.basename(file_path)

    # pylint: disable=too-many-branches
    if "u8be" in base_name:
        existing_dict["bytes_per_sample"] = 1
        existing_dict["big_endian"] = True
        existing_dict["signed"] = False
        existing_dict["float"] = False
    elif "u16be" in base_name:
        existing_dict["bytes_per_sample"] = 2
        existing_dict["big_endian"] = True
        existing_dict["signed"] = False
        existing_dict["float"] = False
    elif "u32be" in base_name:
        existing_dict["bytes_per_sample"] = 4
        existing_dict["big_endian"] = True
        existing_dict["signed"] = False
        existing_dict["float"] = False
    elif "u16le" in base_name:
        existing_dict["bytes_per_sample"] = 2
        existing_dict["big_endian"] = False
        existing_dict["signed"] = False
        existing_dict["float"] = False
    elif "u32le" in base_name:
        existing_dict["bytes_per_sample"] = 4
        existing_dict["big_endian"] = False
        existing_dict["signed"] = False
        existing_dict["float"] = False
    elif "s8be" in base_name:
        existing_dict["bytes_per_sample"] = 1
        existing_dict["big_endian"] = True
        existing_dict["signed"] = True
        existing_dict["float"] = False
    elif "s16be" in base_name:
        existing_dict["bytes_per_sample"] = 2
        existing_dict["big_endian"] = True
        existing_dict["signed"] = True
        existing_dict["float"] = False
    elif "s32be" in base_name:
        existing_dict["bytes_per_sample"] = 4
        existing_dict["big_endian"] = True
        existing_dict["signed"] = True
        existing_dict["float"] = False
    elif "s16le" in base_name:
        existing_dict["bytes_per_sample"] = 2
        existing_dict["big_endian"] = False
        existing_dict["signed"] = True
        existing_dict["float"] = False
    elif "s32le" in base_name:
        existing_dict["bytes_per_sample"] = 4
        existing_dict["big_endian"] = False
        existing_dict["signed"] = True
        existing_dict["float"] = False
    elif "f16" in base_name:
        existing_dict["bytes_per_sample"] = 2
        existing_dict["big_endian"] = False
        existing_dict["signed"] = True
        existing_dict["float"] = True
    elif "f32" in base_name:
        existing_dict["bytes_per_sample"] = 4
        existing_dict["big_endian"] = False
        existing_dict["signed"] = True
        existing_dict["float"] = True
    elif "f64" in base_name:
        existing_dict["bytes_per_sample"] = 8
        existing_dict["big_endian"] = False
        existing_dict["signed"] = True
        existing_dict["float"] = True
    else:
        enb.logger.warn(f"Warning: cannot find valid data type tag in {base_name=}.")
    assert os.path.getsize(file_path) % existing_dict["bytes_per_sample"] == 0
    existing_dict["samples"] = os.path.getsize(file_path) // existing_dict[
        "bytes_per_sample"]
    return existing_dict


class ImageGeometryTable(sets.FilePropertiesTable):
    """Basic properties table for images, including geometry.
    Allows automatic handling of tags in filenames, e.g., u16be-ZxYxX.
    """
    dataset_files_extension = "raw"
    verify_file_size = True

    # Data type columns
    @atable.column_function("bytes_per_sample", label="Bytes per sample",
                            plot_min=0)
    def set_bytes_per_sample(self, file_path, row):
        """Infer the number of bytes per sample based from the file path.
        """
        if any(s in file_path for s in ("u8be", "u8le", "s8be", "s8le")):
            row[_column_name] = 1
        elif any(s in file_path for s in
                 ("u16be", "u16le", "s16be", "s16le", "f16")):
            row[_column_name] = 2
        elif any(s in file_path for s in
                 ("u32be", "u32le", "s32be", "s32le", "f32")):
            row[_column_name] = 4
        elif any(s in file_path for s in ("f64")):
            row[_column_name] = 8
        else:
            raise Exception(
                f"{self.__class__.__name__}: "
                f"unknown column {repr(_column_name)} for file {repr(file_path)}")

    @atable.column_function("float", label="Floating point data?")
    def set_float(self, file_path, row):
        """Infer whether the data are floating point from the file path.
        """
        if any(s in os.path.basename(file_path) for s in
               ("u8be", "u8le", "s8be", "s8le", "u16be", "u16le", "s16be",
                "s16le", "u32be", "u32le", "s32be", "s32le")):
            row[_column_name] = False
        elif any(s in os.path.basename(file_path) for s in
                 ("f16", "f32", "f64")):
            row[_column_name] = True
        else:
            enb.logger.debug(
                f"Unknown {_column_name} from {file_path}. Setting to False.")
            row[_column_name] = False

    @atable.column_function("signed", label="Signed samples")
    def set_signed(self, file_path, row):
        """Infer whether the data are signed from the file path.
        """
        if any(s in file_path for s in
               ("u8be", "u16be", "u16le", "u32be", "u32le")):
            row[_column_name] = False
        elif any(s in file_path for s in (
                "s8be", "s16be", "s16le", "s32be", "s32le", "f16", "f32",
                "f64")):
            row[_column_name] = True
        else:
            enb.logger.debug(
                f"Unknown {_column_name} for {file_path}. Setting to False.")
            row[_column_name] = False

    @atable.column_function("big_endian", label="Big endian?")
    def set_big_endian(self, file_path, row):
        """Infer whether the data are big endian from the file path.
        """
        if any(s in file_path for s in
               ("u8be", "u16be", "u32be", "s8be", "s16be", "s32be")):
            row[_column_name] = True
        elif any(s in file_path for s in
                 ("u8le", "u16le", "u32le", "s8le", "s16le", "s32le")):
            row[_column_name] = False
        elif any(s in file_path for s in ("f16", "f32", "f64")):
            row[_column_name] = True
        else:
            enb.logger.debug(
                f"Unknown {_column_name} for {file_path}. Setting to False.")
            row[_column_name] = False

    @atable.column_function("dtype", label="Numpy dtype")
    def set_column_dtype(self, file_path, row):
        """Infer numpy's data type from the file path.
        """
        # pylint: disable=unused-argument
        if row["float"]:
            row[_column_name] = f"f{row['bytes_per_sample']}"
        else:
            row[
                _column_name] = f"{'>' if row['big_endian'] else '<'}" \
                                f"{'i' if row['signed'] else 'u'}" \
                                f"{row['bytes_per_sample']}"

    @atable.column_function("type_name", label="Type name usable in file names")
    def set_type_name(self, file_path, row):
        """Set the type name usable in file names
        """
        # pylint: disable=unused-argument
        if row["float"]:
            row[_column_name] = f"f{8 * row['bytes_per_sample']}"
        else:
            row[
                _column_name] = f"{'s' if row['signed'] else 'u'}" \
                                f"{8 * row['bytes_per_sample']}" \
                                f"{'be' if row['big_endian'] else 'le'}"

    # Image dimension columns
    @atable.column_function("samples", label="Sample count", plot_min=0)
    def set_samples(self, file_path, row):
        """Set the number of samples in the image
        """
        # pylint: disable=unused-argument
        assert row["size_bytes"] % row["bytes_per_sample"] == 0
        row[_column_name] = row["size_bytes"] // row["bytes_per_sample"]

    @atable.column_function([
        atable.ColumnProperties(name="width", label="Width", plot_min=1),
        atable.ColumnProperties(name="height", label="Height", plot_min=1),
        atable.ColumnProperties(name="component_count", label="Components",
                                plot_min=1),
    ])
    def set_image_geometry(self, file_path, row):
        """Obtain the image's geometry (width, height and number of components)
        based on the filename tags (and possibly its size)
        """
        file_path_to_geometry_dict(file_path=file_path, existing_dict=row,
                                   verify_file_size=self.verify_file_size)


class ImagePropertiesTable(ImageGeometryTable):
    """Properties table for images, with geometry and additional statistical
    information. Allows automatic handling of tags in filenames, e.g.,
    ZxYxX_u16be.
    """
    dataset_files_extension = "raw"

    @atable.column_function([
        atable.ColumnProperties(name="sample_min", label="Min sample value"),
        atable.ColumnProperties(name="sample_max", label="Max sample value")])
    def set_sample_extrema(self, file_path, row):
        """Set the minimum and maximum values stored in file_path.
        """
        array = load_array_bsq(file_or_path=file_path,
                               image_properties_row=row).flatten()
        row["sample_min"], row["sample_max"] = array.min(), array.max()
        if row["float"] == False:  # pylint: disable=singleton-comparison
            assert row["sample_min"] == int(row["sample_min"])
            assert row["sample_max"] == int(row["sample_max"])
            row["sample_min"] = int(row["sample_min"])
            row["sample_max"] = int(row["sample_max"])

    @atable.column_function("dynamic_range_bits", label="Dynamic range (bits)")
    def set_dynamic_range_bits(self, file_path, row):
        """Set minimum number of bits per sample that can be used to store
        the data (without compression). Until v0.4.4, this value was obtained
        based on the number of bits needed to represent max-min (where min and max
        are the minimum and maximum sample values). From version v0.4.5 onwards, the
        dynamic range B is the minimum integer so that all data samples lie in
        `[0, 2^B-1]` for unsigned data and in `[-2^(B-1), 2^(B-1)-1]` for signed data.
        The calculation for floating point data is not changed, and is always `8*bytes_per_sample`.
        """
        if row["float"] is True:
            return 8 * row["bytes_per_sample"]
        if not row["signed"]:
            return math.ceil(math.log2(row["sample_max"] + 1))
        else:
            B = 1
            while not -(2 ** (B - 1)) <= row["sample_min"] <= row["sample_max"] <= 2 ** (B - 1) - 1:
                B += 1
            return B

    @atable.column_function([
        atable.ColumnProperties(f"entropy_{bytes_per_sample}B_bps",
                                label=f"Entropy (bits, {bytes_per_sample}-byte samples)",
                                plot_min=0, plot_max=8 * bytes_per_sample)
        for bytes_per_sample in (1, 2)])
    def set_file_entropy(self, file_path, row):
        """Set the zero-order entropy of the data in file_path for 1, 2 and 4
        bytes per sample in entropy_1B_bps, entropy_2B_bps and
        entropy_4B_bps, respectively. If the file is not a multiple of those
        bytes per sample, -1 is stored instead.
        """
        for bytes_per_sample in (1, 2, 4):
            if row["bytes_per_sample"] % bytes_per_sample != 0:
                row[f"entropy_{bytes_per_sample}B_bps"] = -1
            else:
                row[f"entropy_{bytes_per_sample}B_bps"] = entropy(
                    np.fromfile(file_path,
                                dtype=f"uint{8 * bytes_per_sample}").flatten())


class SampleDistributionTable(ImageGeometryTable):
    """Compute the data probability distributions.
    """

    @enb.atable.column_function(
        [enb.atable.ColumnProperties("sample_distribution",
                                     label="Sample probability distribution",
                                     plot_min=0, plot_max=1,
                                     has_dict_values=True)])
    def set_sample_distribution(self, file_path, row):
        """Compute the data probability distribution of the data in file_path.
        """
        image = enb.isets.load_array_bsq(file_or_path=file_path,
                                         image_properties_row=row)
        unique, counts = np.unique(image, return_counts=True)
        row[_column_name] = dict(zip(unique, counts / image.size))


class HistogramFullnessTable1Byte(atable.ATable):
    """Compute an histogram of usage assuming 1-byte samples.
    """
    dataset_files_extension = "raw"

    @atable.column_function(
        "histogram_fullness_1byte", label="Histogram usage fraction (1 byte)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_1byte(self, file_path, row):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering
        unsigned 1-byte samples.
        """
        row[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint8)).size / (2 ** 8)
        assert 0 <= row[_column_name] <= 1


class HistogramFullnessTable2Bytes(atable.ATable):
    """Compute an histogram of usage assuming 2-byte samples.
    """
    dataset_files_extension = "raw"

    @atable.column_function(
        "histogram_fullness_2bytes", label="Histogram usage fraction (2 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_2bytes(self, file_path, row):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering
        unsigned 2-byte samples.
        """
        row[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint16)).size / (2 ** 16)
        assert 0 <= row[_column_name] <= 1


class HistogramFullnessTable4Bytes(atable.ATable):
    """Compute an histogram of usage assuming 4-byte samples.
    """
    dataset_files_extension = "raw"

    @atable.column_function(
        "histogram_fullness_4bytes", label="Histogram usage fraction (4 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_4bytes(self, file_path, row):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering 4-byte
        samples.
        """
        row[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint32)).size / (2 ** 32)
        assert 0 <= row[_column_name] <= 1


class BandEntropyTable(ImageGeometryTable):
    """Table to calculate the entropy of each band
    """

    @atable.column_function("entropy_per_band", label="Entropy per band",
                            has_dict_values=True)
    def set_entropy_per_band(self, file_path, row):
        """Store a dictionary indexed by band index (zero-indexed) with values
        being entropy in bits per sample.
        """
        array = load_array_bsq(file_or_path=file_path, image_properties_row=row)
        row[_column_name] = {i: entropy(array[:, :, i].flatten())
                             for i in range(row["component_count"])}


class ImageVersionTable(sets.FileVersionTable, ImageGeometryTable):
    """Transform all images and save the transformed versions.
    """
    # pylint: disable=abstract-method
    dataset_files_extension = "raw"

    def __init__(self, version_base_dir, version_name,
                 original_base_dir=None, csv_support_path=None,
                 check_generated_files=True,
                 original_properties_table=None):
        # pylint: disable=too-many-arguments
        original_properties_table = ImageGeometryTable(
            base_dir=original_base_dir) if original_properties_table is None \
            else original_properties_table

        super().__init__(version_base_dir=version_base_dir,
                         version_name=version_name,
                         original_properties_table=original_properties_table,
                         original_base_dir=original_base_dir,
                         csv_support_path=csv_support_path,
                         check_generated_files=check_generated_files)


class BIPToBSQ(ImageVersionTable):
    """Convert raw images (no header) from band-interleaved pixel order (BIP)
    to band-sequential order (BSQ).
    """
    dataset_files_extension = "bip"
    array_order = "bip"

    def __init__(self, version_base_dir,
                 original_base_dir=None, csv_support_path=None,
                 original_properties_table=None):
        super().__init__(version_base_dir=version_base_dir,
                         version_name=self.__class__.__name__,
                         original_base_dir=original_base_dir,
                         csv_support_path=csv_support_path,
                         check_generated_files=False,
                         original_properties_table=original_properties_table)

    def version(self, input_path, output_path, row):
        if input_path.endswith(f".{self.dataset_files_extension}"):
            output_path = output_path[:-4] + ".raw"
        dump_array_bsq(load_array(file_or_path=input_path,
                                  image_properties_row=row,
                                  order=self.array_order),
                       file_or_path=output_path)


class BILToBSQ(BIPToBSQ):
    """Convert raw images (no header) from band-interleaved line order (BIL)
    to band-sequential order (BSQ).
    """
    dataset_files_extension = "bil"
    array_order = "bil"


class QuantizedImageVersion(ImageVersionTable):
    """Apply uniform quantization and store the results.
    """
    dataset_files_extension = "raw"

    def __init__(self, version_base_dir, qstep,
                 original_base_dir=None, csv_support_path=None,
                 check_generated_files=True,
                 original_properties_table=None):
        """
        :param version_base_dir: path to the versioned base directory
          (versioned directories preserve names and structure within
          the base dir)
        :param qstep: quantization step of the uniform quantizer.
        :param version_name: arbitrary name of this file version
        :param original_base_dir: path to the original directory
          (it must contain all indices requested later with self.get_df()).
          If None, options.base_dataset_dir is used
        :param original_properties_table: instance of the file properties subclass
          to be used when reading the original data to be versioned.
          If None, a FilePropertiesTable is instanced automatically.
        :param csv_support_path: path to the file where results (of the
          versioned data) are to be long-term stored. If None, one is assigned
          by default based on options.persistence_dir.
        :param check_generated_files: if True, the table checks that
          each call to version() produces
          a file to output_path. Set to false to create arbitrarily named output files.
        """
        # pylint: disable=too-many-arguments
        assert qstep == int(qstep)
        assert 1 <= qstep <= 65535
        qstep = int(qstep)
        ImageVersionTable.__init__(self, version_base_dir=version_base_dir,
                                   version_name=f"{self.__class__.__name__}_qstep{qstep}",
                                   original_base_dir=original_base_dir,
                                   csv_support_path=csv_support_path,
                                   check_generated_files=check_generated_files,
                                   original_properties_table=original_properties_table)
        self.qstep = qstep

    def version(self, input_path, output_path, row):
        """Apply uniform quantization and store the results.
        """
        img = load_array_bsq(file_or_path=input_path, image_properties_row=row)
        if math.log2(self.qstep) == int(math.log2(self.qstep)):
            img >>= int(math.log2(self.qstep))
        else:
            img //= self.qstep
        dump_array_bsq(array=img, file_or_path=output_path)


class DivisibleSizeVersion(ImageVersionTable):
    """Crop the spatial dimensions of all (raw) images in a directory so that they are
    all multiple of a given number. Useful for quickly curating datasets that can be divided
    into blocks of a given size.
    """

    def __init__(self,
                 version_base_dir,
                 dimension_size_multiple,
                 original_base_dir=None,
                 csv_support_path=None,
                 original_properties_table=None):
        """
        :param version_base_dir: path to the versioned base directory
          (versioned directories preserve names and structure within
          the base dir)
        :param dimension_size_multiple: the x and y dimensions of each image are cropped so that
          they become a multiple of this value, which must be strictly positive.
          If the image is smaller than this value in either
          the x dimension, the y dimension, or both, a ValueError is raised.
        :param original_base_dir: path to the original directory
          (it must contain all indices requested later with self.get_df()).
          If None, `enb.config.options.base_dataset_dir` is used
        :param original_properties_table: instance of the file properties
          subclass to be used when reading the original data to be versioned.
          If None, an enb.isets.ImageGeometryTable is instanced automatically.
        :param csv_support_path: path to the file where results (of the
          versioned data) are to be long-term stored. If None, one is assigned
          by default based on options.persistence_dir.
      """
        super().__init__(version_base_dir=version_base_dir,
                         version_name="CropDimensionsMultiple",
                         original_base_dir=original_base_dir,
                         csv_support_path=csv_support_path,
                         check_generated_files=False,
                         original_properties_table=original_properties_table)
        assert dimension_size_multiple > 0, dimension_size_multiple
        self.dimension_size_multiple = dimension_size_multiple

    def version(self, input_path, output_path, row):
        img = enb.isets.load_array_bsq(file_or_path=input_path)
        width, height, component_count = img.shape
        if min(height, width) < self.dimension_size_multiple:
            raise ValueError(f"Image {input_path} is too small ({self.dimension_size_multiple=})")

        cropped_width = self.dimension_size_multiple * (width // self.dimension_size_multiple)
        cropped_height = self.dimension_size_multiple * (height // self.dimension_size_multiple)
        output_path = os.path.join(
            os.path.dirname(output_path),
            os.path.basename(output_path).replace(
                f"{component_count}x{height}x{width}",
                f"{component_count}x{cropped_height}x{cropped_width}"))

        enb.isets.dump_array_bsq(array=img[:cropped_width, :cropped_height, :],
                                 file_or_path=output_path)


def load_array(file_or_path, image_properties_row=None,
               width=None, height=None, component_count=None, dtype=None,
               order="bsq"):
    """Load a numpy array indexed by [x,y,z] from file_or_path using
    the geometry information in image_properties_row.

    Data in the file can be presented in BSQ or BIL order.

    :param file_or_path: either a string with the path to the input file,
      or a file open for reading (typically with "b" mode).
    :param image_properties_row: if not None, it shall be a dict-like object. The
      width, height, component_count, bytes_per_sample, signed, big_endian and float
      keys should be present to determine the read parameters. If dtype is provided, then
      bytes_per_sample, big_endian and float are not used.
      The remaining arguments overwrite
      those defined in image_properties_row (if image_properties_row
      is not None and if present).

      If image_properties_row is None and any of
      (width, height, component_count, dtype) is None,
      the image geometry is required to be in the filename as a name tag.
      These tags, *e.g.,* `u8be-3x600x800` inform `enb` of all the required geometry.
      The format of these tags (which can appear anywhere in the filename) is:

         - `u` or `s` for unsigned and signed, respectively
         - the number of bits per sample (typically, 8, 16, 32 or 64)
         - `be` or `le` for big-endian and little-endian formats, respectively
         - `ZxYxX`, where `Z` is the number of spectral compoments (3 in the example),
           `X` the width (number of columns, 800 in the example)
           and `Y` the height (number of rows, 600 in the example).

      If image_properties_row is not None, then the following parameters must
      not be None:

    :param width: if not None, force the read to assume this image width
    :param height: if not None, force the read to assume this image height
    :param component_count: if not None, force the read to assume this
      number of components (bands)
    :param dtype: if not None, it must by a valid argument for dtype in numpy,
      and will be used for reading. In
      this case, the bytes_per_sample, signed, big_endian and float keys
      are not accessed in image_properties_row.
    :param order: "bsq" for band sequential order, or "bil" for band
      interleaved.
    :return: a 3-D numpy array with the image data, which can be indexed as [x,y,z].
    """
    # pylint: disable=too-many-arguments
    if image_properties_row is None:
        try:
            image_properties_row = file_path_to_geometry_dict(file_or_path)
        except ValueError:
            assert not any(
                v is None for v in (width, height, component_count, dtype)), \
                f"image_properties_row={image_properties_row} but some None in " \
                f"(width, height, component_count, dtype): " \
                f"{(width, height, component_count, dtype)}."
    width = width if width is not None else image_properties_row["width"]
    height = height if height is not None else image_properties_row["height"]
    component_count = component_count if component_count is not None else \
        image_properties_row["component_count"]
    dtype = dtype if dtype is not None else image_properties_row[
        "dtype"] if "dtype" in image_properties_row else None
    dtype = dtype if dtype is not None else iproperties_row_to_numpy_dtype(
        image_properties_row)

    order = order.lower()
    if order == "bsq":
        return np.fromfile(file_or_path, dtype=dtype).reshape(
            (component_count, height, width)).swapaxes(0, 2)
    if order == "bip":
        return np.fromfile(file_or_path, dtype=dtype).reshape(
            (component_count, width, height), order="F") \
            .swapaxes(0, 2).swapaxes(0, 1)
    if order == "bil":
        input_array = np.fromfile(file_or_path, dtype=dtype).reshape(
            (1, height * component_count, width)).swapaxes(0, 2)
        output_array = np.zeros((width, height, component_count), dtype=dtype)
        for z_index in range(component_count):
            output_array[:, :, z_index] = input_array[:,
                                          z_index::component_count, 0]
        return output_array
    raise ValueError(
        f"Invalid order {repr(order)}. It must be 'bsq', 'bil' or 'bip'.")


def load_array_bsq(file_or_path, image_properties_row=None,
                   width=None, height=None, component_count=None, dtype=None):
    """Load an array in BSQ order. See `enb.isets.load_array`.
    """
    # pylint: disable=too-many-arguments
    return load_array(file_or_path=file_or_path,
                      image_properties_row=image_properties_row,
                      width=width, height=height,
                      component_count=component_count,
                      dtype=dtype, order="bsq")


def load_array_bil(file_or_path, image_properties_row=None,
                   width=None, height=None, component_count=None, dtype=None):
    """Load an array in BIL order. See `enb.isets.load_array`.
    """
    # pylint: disable=too-many-arguments
    return load_array(file_or_path=file_or_path,
                      image_properties_row=image_properties_row,
                      width=width, height=height,
                      component_count=component_count,
                      dtype=dtype, order="bil")


def load_array_bip(file_or_path, image_properties_row=None,
                   width=None, height=None, component_count=None, dtype=None):
    """Load an array in BIP order. See `enb.isets.load_array`.
    """
    # pylint: disable=too-many-arguments
    return load_array(file_or_path=file_or_path,
                      image_properties_row=image_properties_row,
                      width=width, height=height,
                      component_count=component_count,
                      dtype=dtype, order="bip")


def dump_array(array, file_or_path, mode="wb", dtype=None, order="bsq"):
    """Dump a raw array array indexed in [x,y,z] order into BSQ, BIL or BIP
    order. BSQ is the concatenation of each component (z axis),
    each component in raster order. Parent folders are created if not already
    existing. BIL contains the first row of each of the bands, in order,
    the the second row of each row, and so forth. BIP contains all components
    of a pixel, in oder, then the next pixel (in raster order), etc.

    :param file_or_path: It can be either a file-like object, or a string-like
      object. If it is a file, contents are writen without altering the file
      pointer beforehand. In this case, the file is not closed afterwards.
      If it is a string-like object, it will be interpreted
      as a file path, open as determined by the mode parameter.
    :param mode: if file_or_path is a path, the output file is opened in this mode
    :param dtype: if not None, the array is casted to this type before dumping
    :param force_big_endian: if True, a copy of the array is made and its bytes
    are swapped before outputting
      data to file. This parameter is ignored if dtype is provided.
    :param order: "bsq" for band sequential order, or "bil" for band interleaved.
    """
    if isinstance(file_or_path, str) and os.path.dirname(file_or_path):
        os.makedirs(os.path.dirname(file_or_path), exist_ok=True)
    try:
        assert not file_or_path.closed, "Cannot dump to a closed file"
        was_open_here = False
    except AttributeError:
        # pylint: disable=unspecified-encoding,consider-using-with
        file_or_path = open(file_or_path, mode)
        was_open_here = True

    if dtype is not None and array.dtype != dtype:
        array = array.astype(dtype)

    # Expand 2D arrays to 3D trivially
    if len(array.shape) == 2:
        array = np.expand_dims(array, 2)

    if order == "bsq":
        array = array.swapaxes(0, 2)
        array.tofile(file_or_path)
    elif order == "bip":
        array = array.swapaxes(0, 1).swapaxes(0, 2).flatten(order="F")
        array.tofile(file_or_path)
    elif order == "bil":
        for y_index in range(array.shape[1]):
            for z_index in range(array.shape[2]):
                array[:, y_index, z_index].tofile(file_or_path)
    else:
        raise ValueError(f"Invalid order {repr(order)}. "
                         f"It must be 'bsq', 'bil' or 'bip'.")

    if was_open_here:
        file_or_path.close()


def dump_array_bsq(array, file_or_path, mode="wb", dtype=None):
    """Dump an image array into raw format using band sequential (BSQ)
    sample ordering. See :meth:`enb.isets.dump_array` for more details.
    """
    return dump_array(array=array, file_or_path=file_or_path,
                      mode=mode, dtype=dtype, order="bsq")


def dump_array_bil(array, file_or_path, mode="wb", dtype=None):
    """Dump an image array into raw format using band interleaved line (BIL)
    sample ordering. See :meth:`enb.isets.dump_array` for more details.
    """
    return dump_array(array=array, file_or_path=file_or_path,
                      mode=mode, dtype=dtype, order="bil")


def dump_array_bip(array, file_or_path, mode="wb", dtype=None):
    """Dump an image array into raw format using band interleaved pixel (BIP)
    sample ordering. See :meth:`enb.isets.dump_array` for more details.
    """
    return dump_array(array=array, file_or_path=file_or_path,
                      mode=mode, dtype=dtype, order="bip")


def iproperties_row_to_numpy_dtype(image_properties_row):
    """Return a string that identifies the most simple numpy dtype needed
    to represent an image with properties as defined in
    image_properties_row
    """
    if "float" in image_properties_row and image_properties_row[
        "float"] is True:
        return "f" + str(image_properties_row["bytes_per_sample"])
    return ((">" if image_properties_row["big_endian"] else "<")
            if image_properties_row["bytes_per_sample"] > 1 else "") \
        + ("i" if image_properties_row["signed"] else "u") \
        + str(image_properties_row["bytes_per_sample"])


def iproperties_row_to_sample_type_tag(image_properties_row):
    """Return a sample type name tag as recognized by isets (e.g., u16be),
    given an object similar to an ImageGeometryTable row.
    """
    assert image_properties_row["signed"] in [True, False]
    assert image_properties_row["bytes_per_sample"] in [1, 2, 3, 4, 8]
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


def iproperties_to_name_tag(width, height, component_count, big_endian,
                            bytes_per_sample, signed):
    """Return a full name tag (including sample type and dimension information),
    recognized by isets.
    """
    # pylint: disable=too-many-arguments
    row = dict(width=width, height=height, component_count=component_count,
               big_endian=big_endian, bytes_per_sample=bytes_per_sample,
               signed=signed)
    return f"{iproperties_row_to_sample_type_tag(row)}" \
           f"-{iproperties_row_to_geometry_tag(row)}"
