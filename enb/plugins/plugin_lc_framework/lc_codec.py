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


class LosslessLCFrameworkExperiment(enb.icompression.LosslessCompressionExperiment):
    """Lossless compression experiment with a `best_pipeline` column with the name
    of the best compressor for the current sample.
    """

    @enb.atable.column_function([
        enb.atable.ColumnProperties("best_pipeline", label="Best Compression Pipeline")
    ])
    def best_pipeline(self, index, row):
        """Name of the best pipeline for the current sample, e.g., 'BIT_2 RRE_1'
        """
        original_path, codec = self.index_to_path_task(index)
        if isinstance(codec, LCFramework) and original_path in codec.path_to_best_pipeline:
            row["best_pipeline"] = codec.path_to_best_pipeline[original_path]
        else:
            row["best_pipeline"] = "-"

    @enb.atable.column_function([
        enb.atable.ColumnProperties("generation_time_seconds", label="Generation time (s)"),
        enb.atable.ColumnProperties("compression_time_no_generation", label="Compression time (s)"),
    ])
    def set_time_measurements(self, index, row):
        """Columns related to the measurement of the LC search and generation times:

        - generation_time_seconds: time spend searching, generating and compiling the optimal codec.
        - compression_time_no_generation: compression time, not taking into account any time spent
          generating the optimal codec.
        """
        original_path, codec = self.index_to_path_task(index)
        if isinstance(codec, LCFramework) and original_path in codec.path_to_generation_time:
            row["generation_time_seconds"] = codec.path_to_generation_time[original_path]
        else:
            row["generation_time_seconds"] = 0

        row["compression_time_no_generation"] = (
                row["compression_time_seconds"] - row["generation_time_seconds"])



class LCFramework(icompression.WrapperCodec, icompression.LosslessCodec):
    """Codec based on the LC Framework. The `lc` binary is first used to search and generate
    the best compressor pipeline. This best compressor is compiled and executed on each
    call, and the time is included in the final result."""

    def __init__(self, compressor_path=__file__, decompressor_path=__file__,
                 combination=".+ .+"):
        """
        :param compressor_path: ignored and set automatically - kept for signature compatibility.
        :param decompressor_path: ignored and set automatically - kept for signature compatibility.
        :param combination: stage definition, e.g., ".+ .+" for the best combination of any two
          LC stage components.
        """
        super().__init__(compressor_path=compressor_path,
                         decompressor_path=decompressor_path,
                         param_dict=dict(combination=combination))

        self.tmp_dir = tempfile.mkdtemp(dir=enb.config.options.base_tmp_dir)
        self.combination_len = len(combination.split())
        # Name of the best pipeline for each sample indexed by the sample's path
        self.path_to_best_pipeline = {}
        # Generation time (including execution of lc and compilation of the codec), in seconds,
        # indexed by the sample's path
        self.path_to_generation_time = {}

    def compress(self, original_path, compressed_path, original_file_info=None):
        """Run lc to get the best stage combination, generate the code, compile, and compress
        with the compressor using that best combination.
        """
        execution_dir = os.path.join(self.tmp_dir, os.path.basename(compressed_path))
        self.path_to_generation_time[original_path] = 0

        # Run lc to find the best combination
        invocation = (f"{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lc')} "
                      f"{original_path} CR \"\" \"{self.param_dict['combination']}\"")
        enb.logger.debug(f"[{self.name}] Invocation: '{invocation}'")
        try:
            enb.logger.debug(f"[{self.name}] executing: {repr(invocation)}")
            status, output, measured_time, memory_kb = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            self.path_to_generation_time[original_path] += measured_time
            enb.logger.debug(
                f"[{self.name}] Compression OK; "
                f"invocation={invocation} - status={status}; "
                f"output={output}; memory={memory_kb} KB")
            os.remove(os.path.join(os.getcwd(), os.path.basename(
                original_path) + f".CR{self.combination_len}.csv"))
        except enb.tcall.InvocationError as ex:
            try:
                os.remove(os.path.join(os.getcwd(), os.path.basename(
                    original_path) + f".CR{self.combination_len}.csv"))
            except:
                pass

            raise enb.icompression.CompressionException(
                original_path=original_path,
                compressed_path=compressed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        # Compile compressor and decompressor with the best compression
        shutil.copytree(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "LC-framework-main"),
            os.path.join(execution_dir, "LC"))

        best_pipeline = self.output_to_best_pipeline(output)
        self.path_to_best_pipeline[original_path] = best_pipeline

        try:
            # Generate the compressor and decompressor source code
            invocation = (
                    os.path.join(execution_dir,
                                 'LC/generate_standalone_CPU_compressor_decompressor.py')
                    + f' "" "{best_pipeline}"'
            )
            _, _, measured_time, _ = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            self.path_to_generation_time[original_path] += measured_time

            # Compile the compressor
            invocation = (
                f"g++ -O3 -march=native -mno-fma -I. -std=c++17 "
                f"-o {os.path.join(execution_dir, 'compress')} "
                f"{os.path.join(execution_dir, 'LC/compressor-standalone.cpp')}"
            )
            _, _, measured_time, _ = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            self.path_to_generation_time[original_path] += measured_time

            # Compile the decompressor
            invocation = (
                f"g++ -O3 -march=native -mno-fma -I. -std=c++17 -o {os.path.join(execution_dir, 'decompress')} "
                f"{os.path.join(execution_dir, 'LC/decompressor-standalone.cpp')}"
            )
            _, _, measured_time, _ = \
                enb.tcall.get_status_output_time_memory(invocation=invocation)
            self.path_to_generation_time[original_path] += measured_time
        except enb.tcall.InvocationError as ex:
            raise enb.icompression.CompressionException(
                original_path=original_path,
                compressed_path=compressed_path,
                file_info=original_file_info,
                status=-1,
                output=None) from ex

        # Call to compressor using the best configuration
        self.compressor_path = os.path.join(execution_dir, "compress")
        self.decompressor_path = os.path.join(execution_dir, "decompress")
        result = super().compress(original_path, compressed_path, original_file_info)

        # The generation and compilation times are added to the total compression time
        result.compression_time_seconds += self.path_to_generation_time[original_path]

        return result

    def decompress(self, compressed_path, reconstructed_path, original_file_info):
        super().decompress(compressed_path=compressed_path,
                           reconstructed_path=reconstructed_path,
                           original_file_info=original_file_info)

        # Cleanup the temporary generation/compilation dir used for this compress/decompress
        if os.path.abspath(os.path.dirname(self.compressor_path)).startswith(
                os.path.abspath(self.tmp_dir)):
            shutil.rmtree(self.compressor_path, ignore_errors=True)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {reconstructed_path}"

    def output_to_best_pipeline(self, output: str) -> str:
        """Parse the output of an LC invocation and return the name of the best pipeline.
        """
        pattern = r'pipeline:\s*(.*?)\n'
        return re.findall(pattern, output)[-1]

    @property
    def label(self):
        return f"LC ({self.param_dict['combination']})"

    def __delete__(self, instance):
        """The codec is responsible for cleaning up its temporary directory.
        """
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
