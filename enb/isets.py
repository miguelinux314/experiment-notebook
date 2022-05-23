#!/usr/bin/env python3
"""Image sets information tables
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/01"

import os
import math
import numpy as np
import re
import imageio
import enb
from enb.config import options
from enb import atable
from enb import sets


def entropy(data):
    """Compute the zero-order entropy of the provided data
    """
    values, count = np.unique(data.flatten(), return_counts=True)
    total_sum = sum(count)
    probabilities = (count / total_sum for value, count in zip(values, count))
    return -sum(p * math.log2(p) for p in probabilities)


def mutual_information(data1, data2):
    """Compute the mutual information between two vectors of identical length
    after flattening. Implemented following https://en.wikipedia.org/wiki/Mutual_information#Definition
    """
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
    bin_count = max(max(v) for v in (values1, values2)) - min(min(v) for v in (values1, values2)) + 1
    count_xy = np.histogram2d(data1.flatten(), data2.flatten(), bin_count)[0].flatten()
    total_sum_xy = count_xy.sum()
    assert total_sum_xy == total_sum1
    probabilities_xy = count_xy / total_sum_xy
    entropy_xy = -sum(p * math.log2(p) for p in probabilities_xy if p != 0)

    return entropy_x + entropy_y - entropy_xy


def kl_divergence(data1, data2):
    """Return KL(P||Q), KL(Q||P) KL is the KL divergence in bits per sample,
    P is the sample probability distribution of data1, Q is the sample probability distribution of data2.
    
    If both P and Q contain the same values (even if with different counts), both returned values 
    are identical and as defined in https://en.wikipedia.org/wiki/Kullback%E2%80%93Leibler_divergence#Definition.
    
    Otherwise, the formula is modified so that whenever p or q is 0, the factor is skipped from the count.
    In this case, the two values most likely differ and they should be carefully interpreted.
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

    kl_pq = sum(probabilities1[k] * math.log(probabilities1[k] / probabilities2[k])
                if k in probabilities2 and probabilities1[k] != 0 and probabilities2[k] != 0 else 0
                for k in probabilities1.keys())
    kl_qp = sum(probabilities2[k] * math.log(probabilities2[k] / probabilities1[k])
                if k in probabilities1 and probabilities1[k] != 0 and probabilities2[k] != 0 else 0
                for k in probabilities2.keys())

    return kl_pq, kl_qp


def file_path_to_geometry_dict(file_path, existing_dict=None):
    """Return a dict with basic geometry dict based on the file path and the file size.

    :param existing_dict: if not None, the this dict is updated and then returned. If None,
      a new dictionary is created.
    """
    row = existing_dict if existing_dict is not None else {}
    matches = re.findall(r"(\d+)x(\d+)x(\d+)", file_path)
    if matches:
        if len(matches) > 1:
            raise ValueError(f"File path {file_path} contains more than one image geometry tag. "
                            f"Matches: {repr(matches)}.")
        match = matches[0]
        component_count, height, width = (int(match[i]) for i in range(3))
        if any(dim < 1 for dim in (width, height, component_count)):
            raise ValueError(f"Invalid dimension tag in {file_path}")
        row["width"], row["height"], row["component_count"] = \
            width, height, component_count

        _file_path_to_datatype_dict(file_path, row)

        assert os.path.getsize(file_path) == width * height * component_count * row["bytes_per_sample"], \
            (file_path, os.path.getsize(file_path), width, height, component_count, row["bytes_per_sample"],
             width * height * component_count * row["bytes_per_sample"])
        assert row["samples"] == width * height * component_count
    else:
        enb.logger.debug("Cannot determine image geometry "
                         f"from file name {os.path.basename(file_path)}")
        return dict()
    return row


def _file_path_to_datatype_dict(file_path, existing_dict=None):
    existing_dict = existing_dict if existing_dict is not None else dict()

    base_name = os.path.basename(file_path)
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

    assert os.path.getsize(file_path) % existing_dict["bytes_per_sample"] == 0
    existing_dict["samples"] = os.path.getsize(file_path) // existing_dict["bytes_per_sample"]

    return existing_dict


class ImageGeometryTable(sets.FilePropertiesTable):
    """Basic properties table for images, including geometry.
    Allows automatic handling of tags in filenames, e.g., ZxYxX_u16be.
    """
    dataset_files_extension = "raw"

    # Data type columns

    @atable.column_function("bytes_per_sample", label="Bytes per sample", plot_min=0)
    def set_bytes_per_sample(self, file_path, row):
        if any(s in file_path for s in ("u8be", "u8le", "s8be", "s8le")):
            row[_column_name] = 1
        elif any(s in file_path for s in ("u16be", "u16le", "s16be", "s16le", "f16")):
            row[_column_name] = 2
        elif any(s in file_path for s in ("u32be", "u32le", "s32be", "s32le", "f32")):
            row[_column_name] = 4
        elif any(s in file_path for s in ("f64")):
            row[_column_name] = 8
        else:
            raise sets.UnkownPropertiesException(f"{self.__class__.__name__}: unknown {_column_name} for {file_path}")

    @atable.column_function("float", label="Floating point data?")
    def set_float(self, file_path, row):
        if any(s in os.path.basename(file_path) for s in
               ("u8be", "u8le", "s8be", "s8le", "u16be", "u16le", "s16be", "s16le",
                "u32be", "u32le", "s32be", "s32le")):
            row[_column_name] = False
        elif any(s in os.path.basename(file_path) for s in ("f16", "f32", "f64")):
            row[_column_name] = True
        else:
            enb.logger.debug(f"Unknown {_column_name} from {file_path}. Setting to False.")
            row[_column_name] = False

    @atable.column_function("signed", label="Signed samples")
    def set_signed(self, file_path, row):
        if any(s in file_path for s in ("u8be", "u16be", "u16le", "u32be", "u32le")):
            row[_column_name] = False
        elif any(s in file_path for s in ("s8be", "s16be", "s16le", "s32be", "s32le", "f16", "f32", "f64")):
            row[_column_name] = True
        else:
            enb.logger.debug(f"Unknown {_column_name} for {file_path}. Setting to False.")
            row[_column_name] = False

    @atable.column_function("big_endian", label="Big endian?")
    def set_big_endian(self, file_path, row):
        if any(s in file_path for s in ("u8be", "u16be", "u32be", "s8be", "s16be", "s32be")):
            row[_column_name] = True
        elif any(s in file_path for s in ("u8le", "u16le", "u32le", "s8le", "s16le", "s32le")):
            row[_column_name] = False
        elif any(s in file_path for s in ("f16", "f32", "f64")):
            row[_column_name] = True
        else:
            enb.logger.debug(f"Unknown {_column_name} for {file_path}. Setting to False.")
            row[_column_name] = False

    @atable.column_function("dtype", label="Numpy dtype")
    def set_column_dtype(self, file_path, row):
        """Set numpy's dtype string
        """
        if row["float"]:
            row[_column_name] = f"f{8 * row['bytes_per_sample']}"
        else:
            row[
                _column_name] = f"{'>' if row['big_endian'] else '<'}{'i' if row['signed'] else 'u'}{row['bytes_per_sample']}"

    @atable.column_function("type_name", label="Type name usable in file names")
    def set_type_name(self, file_path, row):
        """Set the type name usable in file names
        """
        if row["float"]:
            row[_column_name] = f"f{8 * row['bytes_per_sample']}"
        else:
            row[
                _column_name] = f"{'s' if row['signed'] else 'u'}{8 * row['bytes_per_sample']}{'be' if row['big_endian'] else 'le'}"

    # Image dimension columns

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

    dataset_files_extension = "raw"

    @atable.column_function([
        atable.ColumnProperties(name="sample_min", label="Min sample value"),
        atable.ColumnProperties(name="sample_max", label="Max sample value")])
    def set_sample_extrema(self, file_path, row):
        array = load_array_bsq(file_or_path=file_path, image_properties_row=row).flatten()
        row["sample_min"], row["sample_max"] = array.min(), array.max()
        if row["float"] == False:
            assert row["sample_min"] == int(row["sample_min"])
            assert row["sample_max"] == int(row["sample_max"])
            row["sample_min"] = int(row["sample_min"])
            row["sample_max"] = int(row["sample_max"])

    @atable.column_function("dynamic_range_bits", label="Dynamic range (bits)")
    def set_dynamic_range_bits(self, file_path, row):
        if row["float"] is True:
            range_len = 8 * row["bytes_per_sample"]
        else:
            range_len = int(row["sample_max"]) - int(row["sample_min"])
        assert range_len >= 0, (file_path, row["sample_max"], row["sample_min"], range_len)
        row[_column_name] = max(1, math.ceil(math.log2(range_len + 1)))

    @atable.column_function(
        "entropy_1B_bps", label="Entropy (bps, 1-byte samples)", plot_min=0, plot_max=8)
    def set_file_1B_entropy(self, file_path, row):
        """Return the zero-order entropy of the data in file_path (1-byte samples are assumed)
        """
        row[_column_name] = entropy(np.fromfile(file_path, dtype="uint8").flatten())

    @atable.column_function(
        "entropy_2B_bps", label="Entropy (bps, 2-byte samples)", plot_min=0, plot_max=16)
    def set_file_2B_entropy(self, file_path, row):
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


class SampleDistributionTable(ImageGeometryTable):
    @enb.atable.column_function(
        [enb.atable.ColumnProperties("sample_distribution",
                                     label="Sample probability distribution",
                                     plot_min=0, plot_max=1, has_dict_values=True)])
    def set_sample_distribution(self, file_path, row):
        image = enb.isets.load_array_bsq(file_or_path=file_path, image_properties_row=row)
        unique, counts = np.unique(image, return_counts=True)
        row[_column_name] = dict(zip(unique, counts / image.size))


class HistogramFullnessTable1Byte(atable.ATable):
    dataset_files_extension = "raw"

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
    dataset_files_extension = "raw"

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
    dataset_files_extension = "raw"

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


class ImageVersionTable(sets.FileVersionTable, ImageGeometryTable):
    dataset_files_extension = "raw"

    def __init__(self, version_base_dir, version_name,
                 original_base_dir=None, csv_support_path=None, check_generated_files=True,
                 original_properties_table=None):
        original_properties_table = ImageGeometryTable(
            base_dir=original_base_dir) if original_properties_table is None else original_properties_table

        super().__init__(version_base_dir=version_base_dir,
                         version_name=version_name,
                         original_properties_table=original_properties_table,
                         original_base_dir=original_base_dir,
                         csv_support_path=csv_support_path,
                         check_generated_files=check_generated_files)


class QuantizedImageVersion(ImageVersionTable):
    dataset_files_extension = "raw"

    def __init__(self, version_base_dir, qstep,
                 original_base_dir=None, csv_support_path=None, check_generated_files=True,
                 original_properties_table=None):
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
        img = load_array_bsq(file_or_path=input_path, image_properties_row=row)
        if math.log2(self.qstep) == int(math.log2(self.qstep)):
            img >>= int(math.log2(self.qstep))
        else:
            img //= self.qstep
        dump_array_bsq(array=img, file_or_path=output_path)


class FitsVersionTable(enb.sets.FileVersionTable, enb.sets.FilePropertiesTable):
    """Read FITS files and convert them to raw files,
    sorting them by type (integer or float)	and by bits per pixel.

    By Òscar Maireles.
    """
    fits_extension = "fit"
    allowed_extensions = ["fit", "fits"]
    version_name = "FitsToRaw"

    # No need to set  dataset_files_extension here, because get_default_target_indices is overwriten.
    def __init__(self, original_base_dir, version_base_dir):
        super().__init__(
            original_base_dir=original_base_dir,
            version_base_dir=version_base_dir,
            original_properties_table=sets.FilePropertiesTable(),
            version_name=self.version_name,
            check_generated_files=False)

    def get_default_target_indices(self):
        indices = []
        for ext in self.allowed_extensions:
            indices.extend(enb.atable.get_all_input_files(
                ext=ext, base_dataset_dir=self.original_base_dir))
        return indices

    def original_to_versioned_path(self, original_path):
        if original_path.lower().endswith(".fit"):
            input_ext = "fit"
        elif original_path.lower().endswith(".fits"):
            input_ext = "fits"
        else:
            raise ValueError(f"Invalid input extension {original_path}")

        return os.path.join(
            os.path.dirname(
                os.path.abspath(original_path)).replace(
                os.path.abspath(self.original_base_dir),
                os.path.abspath(self.version_base_dir)),
            os.path.basename(original_path).replace(
                f".{input_ext}", f".raw"))

    @enb.atable.redefines_column
    def set_version_time(self, file_path, row):
        row[_column_name] = 0

    @enb.atable.redefines_column
    def set_version_repetitions(self, file_path, row):
        row[_column_name] = 1

    def version(self, input_path, output_path, row):
        if input_path.lower().endswith(".fit"):
            input_ext = ".fit"
        elif input_path.lower().endswith(".fits"):
            input_ext = ".fits"
        else:
            raise ValueError(f"Invalid extension found in {input_path}")

        hdul = fits.open(input_path)
        saved_images = 0
        for hdu_index, hdu in enumerate(hdul):
            if hdu.header["NAXIS"] == 0:
                continue
            data = hdu.data.transpose()
            header = hdu.header

            if header['BITPIX'] == 8:
                pass
            else:

                if header['NAXIS'] == 1:
                    if header['BITPIX'] < 0:
                        name_label = f'-f{-header["BITPIX"]}-1x1x{header["NAXIS1"]}'
                        dtype_name = f'float{-header["BITPIX"]}'
                        enb_type_name = f"f{-header['BITPIX']}"
                    elif header['BITPIX'] > 0:
                        name_label = f'-u{header["BITPIX"]}be-1x1x{header["NAXIS1"]}'
                        dtype_name = f'>u{header["BITPIX"] // 8}'
                        enb_type_name = f"u{header['BITPIX']}be"
                    else:
                        raise ValueError(f"Invalid bitpix {header['BITPIX']}")
                    data = np.expand_dims(data, axis=1)
                    data = np.expand_dims(data, axis=2)

                elif header['NAXIS'] == 2:
                    if header['BITPIX'] < 0:
                        name_label = f'-f{-header["BITPIX"]}-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        dtype_name = f'float{-header["BITPIX"]}'
                        enb_type_name = f"f{-header['BITPIX']}"
                    elif header['BITPIX'] > 0:
                        name_label = f'-u{header["BITPIX"]}be-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        dtype_name = f'>u{header["BITPIX"] // 8}'
                        enb_type_name = f"u{header['BITPIX']}be"
                    else:
                        raise ValueError(f"Invalid bitpix {header['BITPIX']}")

                    data = np.expand_dims(data, axis=2)
                elif header['NAXIS'] == 3:
                    if header['BITPIX'] < 0:
                        name_label = f'-f{-header["BITPIX"]}-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        dtype_name = f'float{-header["BITPIX"]}'
                        enb_type_name = f"f{-header['BITPIX']}"
                    elif header['BITPIX'] > 0:
                        name_label = f'-u{header["BITPIX"]}be-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        dtype_name = f'>u{header["BITPIX"] // 8}'
                        enb_type_name = f"u{header['BITPIX']}be"
                    else:
                        raise ValueError(f"Invalid bitpix {header['BITPIX']}")
                elif header['NAXIS'] == 4:
                    if header['BITPIX'] < 0:
                        name_label = f'-f{-header["BITPIX"]}-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        dtype_name = f'float{-header["BITPIX"]}'
                        enb_type_name = f"f{-header['BITPIX']}"
                    elif header['BITPIX'] > 0:
                        name_label = f'-u{header["BITPIX"]}be-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        dtype_name = f'>u{header["BITPIX"] // 8}'
                        enb_type_name = f"u{header['BITPIX']}be"
                    else:
                        raise ValueError(f"Invalid bitpix {header['BITPIX']}")
                    data = np.squeeze(data, axis=3)
                else:
                    raise Exception(f"Invalid header['NAXIS'] = {header['NAXIS']}")

                output_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), enb_type_name)
                effective_output_path = os.path.join(
                    output_dir,
                    f"{os.path.basename(output_path).replace('.raw', '')}_img{saved_images}{name_label}.raw")
                os.makedirs(os.path.dirname(effective_output_path), exist_ok=True)
                if os.path.isfile(effective_output_path) == True:
                    pass
                else:
                    if options.verbose > 2:
                        print(f"Dumping FITS->raw ({repr(effective_output_path)}) from hdu_index={hdu_index}")
                    enb.isets.dump_array_bsq(array=data, file_or_path=effective_output_path, dtype=dtype_name)
                    fits_header_path = os.path.join(os.path.dirname(os.path.abspath(effective_output_path)).replace(
                        os.path.abspath(self.version_base_dir),
                        f"{os.path.abspath(self.version_base_dir)}_headers"),
                        os.path.basename(effective_output_path).replace('.raw', '') + "-fits_header.txt")
                    os.makedirs(os.path.dirname(fits_header_path), exist_ok=True)
                    if options.verbose > 2:
                        print(f"Writing to fits_header_path={repr(fits_header_path)}")
                    if os.path.exists(fits_header_path):
                        os.remove(fits_header_path)
                    header.totextfile(fits_header_path)

            saved_images += 1


class PNGCurationTable(enb.sets.FileVersionTable):
    """Given a directory tree containing PNG images, copy those images into
    a new directory tree in raw BSQ format adding geometry information tags to
    the output names recognized by enb.isets.
    """
    dataset_files_extension = "png"

    def __init__(self, original_base_dir, version_base_dir, csv_support_path=None):
        super().__init__(version_base_dir=version_base_dir,
                         version_name=self.__class__.__name__,
                         original_base_dir=original_base_dir,
                         check_generated_files=False,
                         csv_support_path=csv_support_path)

    def version(self, input_path, output_path, row):
        with enb.logger.info_context(f"Versioning {input_path}"):
            im = imageio.imread(input_path)
            if len(im.shape) == 2:
                im = im[:, :, np.newaxis]
            assert len(im.shape) == 3, f"Invalid shape in read image {input_path}: {im.shape}"
            im = im.swapaxes(0, 1)
            if im.dtype == np.uint8:
                type_str = "u8be"
            elif im.dtype == np.uint16:
                type_str = "u16be"
            else:
                raise f"Invalid data type found in read image {input_path}: {im.dtype}"
            output_path = f"{output_path[:-4]}-{type_str}-{im.shape[2]}x{im.shape[1]}x{im.shape[0]}.raw"
            dump_array_bsq(array=im, file_or_path=output_path)


def load_array_bsq(file_or_path, image_properties_row=None,
                   width=None, height=None, component_count=None, dtype=None):
    """Load a numpy array indexed by [x,y,z] from file_or_path using
    the geometry information in image_properties_row.

    :param file_or_path: either a string with the path to the input file,
      or a file open for reading (typically with "b" mode).
    :param image_properties_row: if not None, it shall be a dict-like object. The
      width, height, component_count, bytes_per_sample, signed, big_endian and float
      keys should be present to determine the read parameters. The remaining arguments overwrite
      those defined in image_properties_row (if image_properties_row is not None and if present).
      If None, image geometry is attempted to be obtained from the image path. If this fails,
      none of the remaining parameters can be None.
    :param width: if not None, force the read to assume this image width
    :param height: if not None, force the read to assume this image height
    :param component_count: if not None, force the read to assume this number of components (bands)
    :param dtype: if not None, it must by a valid argument for dtype in numpy, and will be used for reading. In
      this case, the bytes_per_sample, signed, big_endian and float keys are not accessed in image_properties_row.
    :return: a 3-D numpy array with the image data, which can be indexed as [x,y,z].
    """
    if image_properties_row is None:
        try:
            image_properties_row = file_path_to_geometry_dict(file_or_path)
        except ValueError:
            assert not any(v is None for v in (width, height, component_count, dtype)), \
                f"image_properties_row={image_properties_row} but some None in " \
                f"(width, height, component_count, dtype): {(width, height, component_count, dtype)}."
    width = width if width is not None else image_properties_row["width"]
    height = height if height is not None else image_properties_row["height"]
    component_count = component_count if component_count is not None else image_properties_row["component_count"]
    dtype = dtype if dtype is not None else iproperties_row_to_numpy_dtype(image_properties_row)

    return np.fromfile(file_or_path, dtype=dtype).reshape(component_count, height, width).swapaxes(0, 2)


def dump_array_bsq(array, file_or_path, mode="wb", dtype=None):
    """Dump a raw array array indexed in [x,y,z] order into a band sequential (BSQ) ordering,
    i.e., the concatenation of each component (z axis), each component in raster
    order. Parent folders are created if not already existing.

    :param file_or_path: It can be either a file-like object, or a string-like
      object. If it is a file, contents are writen without altering the file
      pointer beforehand. In this case, the file is not closed afterwards.
      If it is a string-like object, it will be interpreted
      as a file path, open as determined by the mode parameter.
    :param mode: if file_or_path is a path, the output file is opened in this mode
    :param dtype: if not None, the array is casted to this type before dumping
    :param force_big_endian: if True, a copy of the array is made and its bytes are swapped before outputting
      data to file. This parameter is ignored if dtype is provided.
    """
    if isinstance(file_or_path, str):
        os.makedirs(os.path.dirname(file_or_path), exist_ok=True)
    try:
        assert not file_or_path.closed, f"Cannot dump to a closed file"
        was_open_here = False
    except AttributeError:
        file_or_path = open(file_or_path, mode)
        was_open_here = True

    if dtype is not None and array.dtype != dtype:
        array = array.astype(dtype)

    # Expand 2D arrays to 3D trivially
    if len(array.shape) == 2:
        array = np.expand_dims(array, 2)

    array = array.swapaxes(0, 2)
    array.tofile(file_or_path)

    if was_open_here:
        file_or_path.close()


def iproperties_row_to_numpy_dtype(image_properties_row):
    """Return a string that identifies the most simple numpy dtype needed
    to represent an image with properties as defined in
    image_properties_row
    """
    if "float" in image_properties_row and image_properties_row["float"] is True:
        return "f" + str(image_properties_row["bytes_per_sample"])
    else:
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


def iproperties_to_name_tag(width, height, component_count, big_endian, bytes_per_sample, signed):
    """Return a full name tag (including sample type and dimension information),
    recognized by isets.
    """
    row = dict(width=width, height=height, component_count=component_count,
               big_endian=big_endian, bytes_per_sample=bytes_per_sample,
               signed=signed)
    return f"{iproperties_row_to_sample_type_tag(row)}" \
           f"-{iproperties_row_to_geometry_tag(row)}"


def raw_path_to_png(raw_path, png_path, image_properties_row=None):
    """Render an uint8 or uint16 raw image with 1, 3 or 4 components.
    
    :param raw_path: path to the image in raw format to render in png.
    :param png_path: path where the png file is to be stored.
    :param image_properties_row: if row_path does not contain geometry information,
      this parameter should be a dict-like object that indicates width, height, number of components,
      bytes per sample, signedness and endianness if applicable.
    """
    img = load_array_bsq(file_or_path=raw_path, image_properties_row=image_properties_row)
    render_array_png(img=img, png_path=png_path)


def render_array_png(img, png_path):
    """Render an uint8 or uint16 image with 1, 3 or 4 components.
    :param img: image array indexed by [x,y,z].
    :param png_path: path where the png file is to be stored.
    """
    max_value = np.max(img)
    if img.dtype == np.uint8:
        pass
    elif any(img.dtype == t for t in (np.uint16, np.uint32, np.uint64)):
        if max_value <= 255:
            img = img.astype(np.uint8)
        elif max_value <= 65535:
            img = img.astype(np.uint16)
        else:
            raise ValueError(f"Invalid maximum value {max_value} for type {img.dtype}. Not valid for PNG")
    else:
        raise ValueError(f"Image type {img.dtype} not supported for rendering into PNG. "
                         f"Try np.uint8 or np.uint16.")

    if img.shape[2] not in {1, 3, 4}:
        raise ValueError(f"Number of components not valid. Image shape (x,y,z) = {img.shape}")
    if os.path.dirname(png_path):
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
    imageio.imwrite(png_path, img.swapaxes(0, 1), format="png")
