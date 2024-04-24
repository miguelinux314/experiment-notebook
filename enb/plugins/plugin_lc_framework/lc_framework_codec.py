#!/usr/bin/env python3
"""Wrappers for the LC framework implementation
"""
__author__ = "Pau Quintas Torra, Xavier Fernandez Mellado"
__since__ = "2024/04/03"

import os
import re
import tempfile
import shutil
from enb import icompression
import enb


def get_best_pipeline(output: str) -> str:
    pattern = r'pipeline:\s*(.*?)\n'
    return re.findall(pattern, output)[-1]


class LosslessLCFrameworkExperiment(enb.icompression.LosslessCompressionExperiment):
    def __init__(self, codecs,
                 dataset_paths):

        super().__init__(codecs=codecs, dataset_paths=dataset_paths)

    @enb.atable.column_function([
        enb.atable.ColumnProperties("best_pipeline", label="Best Compression Pipeline")
    ])
    def best_pipeline(self, index, row):
        original_path, codec = self.index_to_path_task(index)
        if isinstance(codec, LCFramework) and original_path in codec.best_pipeline_dict:
            row["best_pipeline"] = codec.best_pipeline_dict[original_path]
        else:
            row["best_pipeline"] = "-"

class LCFramework(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self,
                 compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "lc"),
                 decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "lc"),
                 combination=".+ .+"):

        super().__init__(compressor_path=compressor_path,
                         decompressor_path=decompressor_path,
                         param_dict=dict(combination=combination))

        self.tmp_dir = tempfile.mkdtemp(dir=enb.config.options.base_tmp_dir)
        self.combination_len = len(combination.split())
        self.best_pipeline_dict = {}

    def compress(self, original_path, compressed_path, original_file_info=None):
        execution_dir = os.path.join(self.tmp_dir, os.path.basename(compressed_path))
        compression_time = 0

        # Run lc to find the best combination
        invocation = (f"{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lc')} "
                      f"{original_path} CR \"\" \"{self.param_dict['combination']}\"")
        enb.logger.debug(f"[{self.name}] Invocation: '{invocation}'")
        try:
            enb.logger.debug(f"[{self.name}] executing: {repr(invocation)}")
            status, output, measured_time, memory_kb = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            compression_time += measured_time
            enb.logger.debug(
                f"[{self.name}] Compression OK; "
                f"invocation={invocation} - status={status}; "
                f"output={output}; memory={memory_kb} KB")

            os.remove(os.path.join(os.getcwd(), os.path.basename(original_path) + f".CR{self.combination_len}.csv"))
        except enb.tcall.InvocationError as ex:
            try:
                os.remove(os.path.join(os.getcwd(), os.path.basename(original_path) + f".CR{self.combination_len}.csv"))
            except:
                pass

            raise CompressionException(
                original_path=original_path,
                compressed_path=compressed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        # Compile compressor and decompressor with the best compression
        shutil.copytree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "LC-framework-main"),
                        os.path.join(execution_dir, "LC"))

        best_pipeline = get_best_pipeline(output)
        self.best_pipeline_dict[original_path] = best_pipeline

        try:
            invocation = (
                f"{os.path.join(execution_dir, 'LC/generate_standalone_CPU_compressor_decompressor.py')} "
                f"\"\" \"{best_pipeline}\""
            )
            _, _, measured_time, _ = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            compression_time += measured_time

            invocation = (
                f"g++ -O3 -march=native -mno-fma -I. -std=c++17 -o {os.path.join(execution_dir, 'compress')} "
                f"{os.path.join(execution_dir, 'LC/compressor-standalone.cpp')}"
            )

            _, _, measured_time, _ = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            compression_time += measured_time

            invocation = (
                f"g++ -O3 -march=native -mno-fma -I. -std=c++17 -o {os.path.join(execution_dir, 'decompress')} "
                f"{os.path.join(execution_dir, 'LC/decompressor-standalone.cpp')}"
            )

            _, _, measured_time, _ = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            compression_time += measured_time

        except enb.tcall.InvocationError as ex:
            raise "Compilation Error" from ex

        # Call to compressor using the best configuration
        self.compressor_path = os.path.join(execution_dir, "compress")
        self.decompressor_path = os.path.join(execution_dir, "decompress")

        result = super().compress(original_path, compressed_path, original_file_info)
        result.compression_time_seconds += compression_time
        return result

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {reconstructed_path}"

    @property
    def label(self):
        return f"LC_Framework {self.param_dict['combination']}"
