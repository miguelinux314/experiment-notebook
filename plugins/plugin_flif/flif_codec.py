#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codec wrapper for the FLIF lossless image coder (precursor of JPEG-LS
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "09/02/2021"

import os
import time
import tempfile
import subprocess
import imageio
import numpy as np
import enb

class FLIF(enb.icompression.LosslessCodec, enb.icompression.PNGWrapperCodec):
    def __init__(self, flif_binary=os.path.join(os.path.dirname(__file__), "flif")):
        super().__init__(compressor_path=flif_binary, decompressor_path=flif_binary)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-e --overwrite {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-d --overwrite {compressed_path} {reconstructed_path}"

    # def compress(self, original_path: str, compressed_path: str, original_file_info=None):
    #     img = enb.isets.load_array_bsq(
    #         file_or_path=original_path, image_properties_row=original_file_info)
    #     with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
    #         imageio.imwrite(tmp_file.name, img)
    #         invocation = f"{self.flif_binary} -e --overwrite {tmp_file.name} {compressed_path}"
    #         time_before = time.process_time()
    #         status, output = subprocess.getstatusoutput(invocation)
    #         time_after = time.process_time()
    #         if status != 0:
    #             raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
    #                 status, invocation, output))
    #         compression_results = self.compression_results_from_paths(
    #             original_path=original_path, compressed_path=compressed_path)
    #         compression_results.compression_time_seconds = max(0, time_after - time_before)
    #         return compression_results
    #
    # def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
    #     with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
    #         invocation = f"{self.flif_binary} -d --overwrite {compressed_path} {tmp_file.name}"
    #         status, output = subprocess.getstatusoutput(invocation)
    #         if status != 0:
    #             raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
    #                 status, invocation, output))
    #         img = imageio.imread(tmp_file.name, "png")
    #         img.swapaxes(0, 1)
    #         img = np.expand_dims(img, axis=2)
    #         enb.isets.dump_array_bsq(img, file_or_path=reconstructed_path)


