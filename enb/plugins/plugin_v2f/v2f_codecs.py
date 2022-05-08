#!/usr/bin/env python3
"""Codecs wrapping V2F forests.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/09/01"

import os
import shutil
import subprocess
import itertools
import re
import pandas as pd
import numpy as np
import enb
import time

# Constants taken from the C code for consistency and maintainability.
V2F_C_QUANTIZER_MODE_NONE = 0
V2F_C_QUANTIZER_MODE_UNIFORM = 1
V2F_C_QUANTIZER_MODE_COUNT = 2
V2F_C_DECORRELATOR_MODE_NONE = 0
V2F_C_DECORRELATOR_MODE_LEFT = 1
V2F_C_DECORRELATOR_MODE_2_LEFT = 2
V2F_C_DECORRELATOR_MODE_JPEGLS = 3
V2F_C_DECORRELATOR_MODE_FGIJ = 4
V2F_C_DECORRELATOR_MODE_COUNT = 5
V2F_C_QUANTIZER_MODE_MAX_STEP_SIZE = 255


class V2FCodec(enb.icompression.LosslessCodec,
               enb.icompression.NearLosslessCodec,
               enb.icompression.WrapperCodec):
    """Wrapper for the V2F compressor/decompressor tools in C,
    which must be present in the same path as this script.
    """

    def __init__(self, v2fc_header_path, qstep=None, quantizer_mode=None, decorrelator_mode=None,
                 verify_on_initialization=True, time_results_dir=None,
                 shadow_position_pairs=[]):
        """
        Initialize a V2F codec that employs the forest definition in `v2fc_header_path`, and optionally
        overwrite the quantization and decorrelation defined in them.

        :param v2fc_header_path: path to the V2F forest definition to be employed
        :param qstep: quantization step size. Only applied if quantizer_mode is not
          V2F_C_DECORRELATOR_MODE_NONE. Cannot exceed V2F_C_QUANTIZER_MODE_MAX_STEP_SIZE.
        :param quantizer_mode: quantization mode; see the V2F_C_QUANTIZER_MODE_* constants.
        :param decorrelator_mode: decorrelation (e.g., prediction) mode;
          see see the V2F_C_DECORRELATOR_MODE_* constants.
        :param verify_on_initialization: if True, the codec in v2fc_heder_path is verified upon initialization.
        :param time_results_dir: if not None, it must be the path of a directory that will be used to store time
          measurements reported by the V2F prototype.
        :param shadow_position_pairs: a list of zero or more tuples describing the y-positions of the 
          horizontal shadow regions. Shadow regions are not compressed and are reconstructed as constant zero.
          Each tuple must be of the form (start, end), where start and end are the first and last row index 
          (starting with zero) of the shadow. If the list is empty, no shadow regions are specified.
          Shadow regions cannot overlap. 
        """
        self.codec_root_dir = os.path.abspath(os.path.dirname(__file__))

        shadow_position_pairs = sorted(shadow_position_pairs)
        verify_shadow_position_pairs(shadow_position_pairs)

        super().__init__(compressor_path=os.path.join(self.codec_root_dir, "v2f_compress"),
                         decompressor_path=os.path.join(self.codec_root_dir, "v2f_decompress"),
                         param_dict=dict(
                             v2fc_header_path=v2fc_header_path,
                             qstep=qstep,
                             quantizer_mode=quantizer_mode,
                             decorrelator_mode=decorrelator_mode,
                             shadow_position_pairs=shadow_position_pairs))

        # Header path with the V2F codec (including forest) definition
        self.v2fc_header_path = v2fc_header_path
        if not self.v2fc_header_path or not os.path.isfile(self.v2fc_header_path):
            raise ValueError(f"Cannot find a V2F codec definition at {repr(self.v2fc_header_path)}. "
                             f"Please make sure you are passing the right argument to "
                             f"{self.__class__}'s initializier, and that the file is actually present.")

        # Verify the chosen codec if configured to do so.
        self.verifier_path = os.path.join(self.codec_root_dir, "v2f_verify_codec")
        if verify_on_initialization:
            self.verify_codec(v2fc_header_path=v2fc_header_path)

        # Prepare the folder where time measurements are to be stored
        self.time_results_dir = time_results_dir
        if self.time_results_dir:
            os.makedirs(self.time_results_dir, exist_ok=True)

    def verify_codec(self, v2fc_header_path):
        """Run the V2F codec verification tool for a given path.
        An exception is raised if this verification fails.
        """
        if not os.path.isfile(self.verifier_path):
            raise ValueError(f"Could not find the V2F codec verifier tool at {repr(self.verifier_path)}. "
                             f"Please make sure it is present at that path and try again.")

        with enb.logger.info_context(f"Verifying V2F codec {repr(v2fc_header_path)}"):
            invocation = f"{self.verifier_path} {os.path.abspath(v2fc_header_path)}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise ValueError(f"V2F codec verification failed for {repr(v2fc_header_path)}.\n"
                                 f"status: {status}\n"
                                 f"invocation: {repr(invocation)}\n"
                                 f"execution output: {output}.")
            else:
                enb.logger.info(f"Verification OK. Returned message:\n{output}")

    def get_time_path(self, original_path):
        assert self.time_results_dir, f"Trying to run get_time_path() without having set self.time_results_dir."
        return os.path.join(self.time_results_dir,
                            f"q{self.param_dict['quantizer_mode']}_"
                            f"s{self.param_dict['qstep']}_"
                            f"d{self.param_dict['decorrelator_mode']}_" + \
                            ("noshadow_" if self.param_dict["shadow_position_pairs"] else "") + \
                            os.path.basename(self.v2fc_header_path).replace(os.sep, "__"),
                            os.path.relpath(os.path.abspath(original_path), 
                                            enb.config.options.project_root).replace(os.sep, "__")
                            + "_times.csv")

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_path} {self.get_optional_argument_string(original_path=original_path)} " \
               f"-w {original_file_info['width']} " \
               + (f"-y {','.join(str(y) for y in itertools.chain(*self.param_dict['shadow_position_pairs']))} "
                  if self.param_dict['shadow_position_pairs'] else '') + \
               f"{self.v2fc_header_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} " \
               f"{self.get_optional_argument_string(original_path=None)} " \
               f"-w {original_file_info['width']} " \
               f"{self.v2fc_header_path} {reconstructed_path}"

    def get_optional_argument_string(self, original_path):
        optional_str = ""
        if self.param_dict['quantizer_mode'] is not None:
            optional_str += f"-q {self.param_dict['quantizer_mode']} "
        if self.param_dict['qstep'] is not None:
            optional_str += f"-s {self.param_dict['qstep']} "
        if self.param_dict['decorrelator_mode'] is not None:
            optional_str += f"-d {self.param_dict['decorrelator_mode']} "
        if self.time_results_dir is not None and original_path is not None:
            time_path = self.get_time_path(original_path)
            os.makedirs(os.path.dirname(time_path), exist_ok=True)
            optional_str += f"-t {time_path} "
        return optional_str

    @property
    def label(self):
        if self.param_dict["decorrelator_mode"] == V2F_C_DECORRELATOR_MODE_NONE:
            dec_str = "none"
        elif self.param_dict["decorrelator_mode"] == V2F_C_DECORRELATOR_MODE_LEFT:
            dec_str = "left"
        elif self.param_dict["decorrelator_mode"] == V2F_C_DECORRELATOR_MODE_2_LEFT:
            dec_str = "two left"
        elif self.param_dict["decorrelator_mode"] == V2F_C_DECORRELATOR_MODE_JPEGLS:
            dec_str = "JPEG-LS"
        elif self.param_dict["decorrelator_mode"] == V2F_C_DECORRELATOR_MODE_FGIJ:
            dec_str = "FGIJ"
        else:
            raise ValueError(self.param_dict["decorrelator_mode"])

        return f"V2F Qstep={self.param_dict['qstep']} pred={dec_str}"


class ShadowLossyExperiment(enb.icompression.LossyCompressionExperiment):
    """This compression experiment verifies that loss is restricted to 
    the defined y shadow regions, while the remainder of the image is
    reconstructed without loss. An exception is raised if this verification fails.
    
    Some additional columns are generated to track tree size, decorrelation mode, and
    other parameters specific to V2F codecs.
    """

    def __init__(self, codecs, shadow_position_pairs=[],
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table=None,
                 overwrite_file_properties=False,
                 reconstructed_dir_path=None,
                 compressed_copy_dir_path=None,
                 task_families=None):
        super().__init__(codecs=codecs,
                         dataset_paths=dataset_paths,
                         csv_experiment_path=csv_experiment_path,
                         csv_dataset_path=csv_dataset_path,
                         dataset_info_table=dataset_info_table,
                         overwrite_file_properties=overwrite_file_properties,
                         reconstructed_dir_path=reconstructed_dir_path,
                         compressed_copy_dir_path=compressed_copy_dir_path,
                         task_families=task_families)
        verify_shadow_position_pairs(shadow_position_pairs)
        self.shadow_position_pairs = sorted(shadow_position_pairs)

    def column_lossless_except_shadows(self, index, row):
        """Verify that lossless results are obtained in every part of the image except for
        the shadows, which must contain all zero values if the shadow_position_pairs entry
        is present in the codec's param_dict.
        """
        original_path, codec = self.index_to_path_task(index)
        reconstructed_path = self.codec_results.decompression_results.reconstructed_path

        original_img = enb.isets.load_array_bsq(original_path)
        reconstructed_img = enb.isets.load_array_bsq(
            file_or_path=reconstructed_path,
            image_properties_row=self.get_dataset_info_row(file_path=original_path))

        for shadow_start, shadow_end in self.shadow_position_pairs:
            try:
                if codec.param_dict["shadow_position_pairs"]:
                    if np.any(reconstructed_img[:, shadow_start:shadow_end + 1, :] != 0):
                        raise enb.icompression.CompressionException(
                            output=f"Non-zero values found at ({shadow_start}, {shadow_end}) of the reconstructed image")
            except KeyError:
                pass
            reconstructed_img[:, shadow_start:shadow_end + 1, :] = \
                original_img[:, shadow_start:shadow_end + 1, :]

        if np.any(original_img != reconstructed_img):
            raise enb.icompression.CompressionException(
                output=f"Not lossless reconstruction outside the shadow regions")

        return True

    def column_decorrelator_mode(self, index, row):
        """Name of the decorrelation method used by this current codec.
        """
        path, codec = self.index_to_path_task(index)

        try:
            decorrelator_mode = codec.param_dict["decorrelator_mode"]
            if decorrelator_mode == V2F_C_DECORRELATOR_MODE_NONE:
                return "No decorrelation"
            elif decorrelator_mode == V2F_C_DECORRELATOR_MODE_LEFT:
                return "Left neighbor prediction"
            elif decorrelator_mode == V2F_C_DECORRELATOR_MODE_2_LEFT:
                return "Two left neighbor prediction"
            elif decorrelator_mode == V2F_C_DECORRELATOR_MODE_JPEGLS:
                return "JPEG-LS prediction"
            elif decorrelator_mode == V2F_C_DECORRELATOR_MODE_FGIJ:
                return "Four neighbor prediction"
            else:
                raise KeyError(decorrelator_mode)
        except KeyError:
            assert not isinstance(codec, V2FCodec)
            return f"{codec.label}'s decorrelation"

    def column_tree_size(self, index, row):
        """Number of included nodes in the trees of the V2F forest.
        """
        path, codec = self.index_to_path_task(index)
        try:
            return int(re.search(r"_treesize-(\d+)_", os.path.basename(codec.v2fc_header_path)).group(1))
        except AttributeError:
            return -1

    def column_tree_count(self, index, row):
        """Number of trees in the V2F forest.
        """
        path, codec = self.index_to_path_task(index)
        try:
            return int(re.search(r"_treecount-(\d+)_", os.path.basename(codec.v2fc_header_path)).group(1))
        except AttributeError:
            return -1

    def column_symbol_count(self, index, row):
        """Number of symbols in the source.
        """
        path, codec = self.index_to_path_task(index)
        try:
            return int(re.search(r"_symbolcount-(\d+)_", os.path.basename(codec.v2fc_header_path)).group(1))
        except AttributeError:
            return -1

    def column_optimization_column(self, index, row):
        """Name of the analysis column used to obtain the ideal source's
        symbol distribution.
        """
        path, codec = self.index_to_path_task(index)
        try:
            return str(re.search(r"_optimizedfor-(.*)_withentropy-", os.path.basename(codec.v2fc_header_path)).group(1))
        except AttributeError:
            return f"{codec.label}: N/A"

    def column_ideal_source_entropy(self, index, row):
        """Entropy of the ideal source for which the forest is optimized.
        """
        path, codec = self.index_to_path_task(index)
        try:
            return float(
                re.search(r"_withentropy-(\d+\.\d+)_avg_all.v2fc", os.path.basename(codec.v2fc_header_path)).group(1))
        except AttributeError:
            return -1

    @enb.atable.column_function("block_coding_time_seconds", label="Block coding time (s)", plot_min=0)
    def set_block_coding_time_seconds(self, index, row):
        """Calculate the total coding time without considering initialization,
        """
        path, codec = self.index_to_path_task(index)
        if not isinstance(codec, V2FCodec):
            row[_column_name] = row["compression_time_seconds"]
        else:
            time_df = pd.read_csv(codec.get_time_path(path))
            row[_column_name] = float(time_df[time_df["name"] == "v2f_compressor_compress_block"]["total_cpu_seconds"])


def verify_shadow_position_pairs(shadow_position_pairs):
    """Check that the list of shadow positions is valid, and raise a ValueError otherwise.
    """
    if shadow_position_pairs:
        shadow_position_pairs = sorted(shadow_position_pairs)
        if any(len(pair) != 2 for pair in shadow_position_pairs):
            print(f"[watch] shadow_position_pairs={shadow_position_pairs}")

            raise ValueError("All shadow pairs must have length exactly 2")
        if any(pair[0] > pair[1] for pair in shadow_position_pairs):
            raise ValueError("Shadow pairs must have start <= end")
        for i in range(len(shadow_position_pairs) - 1):
            if shadow_position_pairs[i][1] >= shadow_position_pairs[i + 1][0]:
                raise ValueError(f"Shadow region {shadow_position_pairs[i]} and {shadow_position_pairs[i + 1]} "
                                 "overlap, which is not allowed.")
