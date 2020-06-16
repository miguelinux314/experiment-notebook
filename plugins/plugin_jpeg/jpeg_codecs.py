#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrappers for the reference JPEG implementation
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "08/04/2020"

import os
import sortedcontainers
import shutil
import tempfile
import numpy as np

from enb import icompression
from enb import isets
from enb import sets
from enb import pgm
from enb import tarlite
from enb.config import get_options

options = get_options()


class JPEG_LS(icompression.NearLosslessCodec, icompression.WrapperCodec):
    max_dimension_size = 65535

    def __init__(self, max_error=0, bin_dir=None, output_invocation_dir=None):
        """
        :param max_error: maximum pixelwise error allowed. Use 0 for lossless
          compression
        :param bin_dir: path to the directory that contains the
          ldc_encoder, ldc_decoder and ldc_header_tool binaries. If it is None,
          options.external_bin_base_dir is None. If this is None as well, the
          same directory of this script is used by default.
        """
        bin_dir = bin_dir if bin_dir is not None else options.external_bin_base_dir
        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        assert os.path.isdir(bin_dir), f"Invalid binary dir {bin_dir}."
        jpeg_bin_path = os.path.join(bin_dir, "jpeg")

        param_dict = sortedcontainers.SortedDict()
        param_dict["ls"] = 0
        max_error = int(max_error)
        assert max_error >= 0
        param_dict["m"] = int(max_error)
        icompression.WrapperCodec.__init__(
            self, compressor_path=jpeg_bin_path, decompressor_path=jpeg_bin_path,
            param_dict=param_dict, output_invocation_dir=output_invocation_dir)

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        assert original_file_info["bytes_per_sample"] in [1, 2], \
            f"Only 1 or 2 bytes per sample, unsigned values {original_file_info['bytes_per_sample']}"
        assert original_file_info["width"] <= self.max_dimension_size
        assert original_file_info["height"] <= self.max_dimension_size
        complete_array = isets.load_array_bsq(file_or_path=original_path, image_properties_row=original_file_info)
        if original_file_info["signed"]:
            complete_array = complete_array.astype(np.int64)
            complete_array += 2 ** ((8 * original_file_info['bytes_per_sample']) - 1)
            assert (complete_array >= 0).all(), f"Error converting signed into unsigned"

        bands_per_image = min(original_file_info["component_count"],
                              self.max_dimension_size // original_file_info["height"])

        tw = tarlite.TarliteWriter()

        total_compression_time = 0

        with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
            stacked_size = 0
            for stack_index, start_band_index in enumerate(
                    range(0, original_file_info["component_count"], bands_per_image)):
                end_band_index_not_included = min(original_file_info["component_count"],
                                                  start_band_index + bands_per_image)
                stacked_array = np.hstack(tuple(complete_array[:, :, z].squeeze()
                                                for z in range(start_band_index, end_band_index_not_included)))
                stacked_size += stacked_array.shape[0] * stacked_array.shape[1]

                with tempfile.NamedTemporaryFile(dir=options.base_tmp_dir,
                                                 suffix=".pgm") as tmp_stack_file:
                    pgm.write_pgm(array=stacked_array,
                                  bytes_per_sample=original_file_info["bytes_per_sample"],
                                  output_path=tmp_stack_file.name)
                    stack_compressed_path = os.path.join(tmp_dir, str(stack_index))
                    compression_results = super().compress(
                        original_path=tmp_stack_file.name,
                        compressed_path=stack_compressed_path,
                        original_file_info=original_file_info)
                    total_compression_time += compression_results.compression_time_seconds

                    tw.add_file(input_path=stack_compressed_path)
            assert stacked_size == complete_array.shape[0] * complete_array.shape[1] * complete_array.shape[2], \
                f"Total stacked size {stacked_size} does not match the expectations. " \
                f"({stacked_size} vs {complete_array.shape[0] * complete_array.shape[1] * complete_array.shape[2]}"

            tw.write(output_path=compressed_path)

            compression_results = self.compression_results_from_paths(
                original_path=original_path, compressed_path=compressed_path)
            compression_results.compression_time_seconds = total_compression_time

            return compression_results

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        tr = tarlite.TarliteReader(tarlite_path=compressed_path)

        bands_per_image = min(original_file_info["component_count"],
                              self.max_dimension_size // original_file_info["height"])

        total_decompression_time = 0
        recovered_components = []
        with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
            tr.extract_all(output_dir_path=tmp_dir)

            for stack_index, start_band_index in enumerate(
                    range(0, original_file_info["component_count"], bands_per_image)):
                compressed_stack_path = os.path.join(tmp_dir, str(stack_index))

                with tempfile.NamedTemporaryFile(dir=options.base_tmp_dir, suffix=".pgm") as stack_path:
                    decompression_results = super().decompress(
                        compressed_path=compressed_stack_path, reconstructed_path=stack_path.name)
                    total_decompression_time += decompression_results.decompression_time_seconds

                    assert os.path.isfile(stack_path.name)
                    stack_array = pgm.read_pgm(input_path=stack_path.name)

                    limits = tuple(range(original_file_info["height"],
                                         stack_array.shape[1],
                                         original_file_info["height"]))

                    recovered_components.extend(np.hsplit(stack_array, limits))

        e_sum = 0
        for c in recovered_components:
            assert len(c.shape) == 2
            e_sum += c.shape[0] * c.shape[1]
        assert e_sum == original_file_info['width'] * original_file_info['height'] * original_file_info[
            'component_count'], \
            f"Wrong number of recovered pixels {e_sum}, " \
            f"expected {original_file_info['width'] * original_file_info['height'] * original_file_info['component_count']}."
        assert len(recovered_components) == original_file_info["component_count"]
        assert recovered_components[0].shape == (original_file_info["width"], original_file_info["height"])

        recovered_array = np.dstack(recovered_components)
        assert recovered_array.shape == (
            original_file_info['width'], original_file_info['height'], original_file_info['component_count'])

        if original_file_info["signed"]:
            recovered_array = recovered_array.astype(np.int64)
            recovered_array -= 2 ** ((8 * original_file_info["bytes_per_sample"]) - 1)

        isets.dump_array_bsq(array=recovered_array, file_or_path=reconstructed_path,
                             dtype=isets.iproperties_row_to_numpy_dtype(image_properties_row=original_file_info))

        decompression_results = self.decompression_results_from_paths(
            compressed_path=compressed_path, reconstructed_path=reconstructed_path)
        decompression_results.decompression_time_seconds = total_decompression_time
        return decompression_results

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        s = " ".join(f"-{k} {v}" for k, v in self.param_dict.items())
        s += f" {original_path} {compressed_path}"
        return s

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return "JPEG-LS"
