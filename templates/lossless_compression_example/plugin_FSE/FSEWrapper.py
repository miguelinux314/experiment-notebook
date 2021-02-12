import os
from enb import icompression, tcall
from enb.config import get_options
import tempfile


options = get_options()

import os
import subprocess
import re
import time


class FSEWrapper(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self):
        icompression.WrapperCodec.__init__(self, compressor_path=f"./plugin_FSE/fse",
                                           decompressor_path=f"./plugin_FSE/fse", param_dict=None,
                                           output_invocation_dir=None)


    def get_compression_params(self, original_path, compressed_path, original_file_info):
        print("COMPRESSION")
        return f" -e -f {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        print("DECOMPRESSION")
        return f" -e -d -f {compressed_path} {reconstructed_path}"

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        print("COMPRESS")
        compression_params = self.get_compression_params(original_path=original_path, compressed_path=compressed_path,
                                                         original_file_info=original_file_info)

        invocation = f"{self.compressor_path} {compression_params}"
        print(invocation)
        try:
            print("111111111111111111111111111111111111111111111111111")
            if os.path.isfile("/usr/bin/time"):
                invocation = f"/usr/bin/time -f 'u%U@s%S' {invocation}"
            else:
                invocation = f"{invocation}"
                wall = True
            print("......................................................")
            wall_time_before = time.time()
            print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            status, output = subprocess.getstatusoutput(invocation)
            print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
            wall_time_after = time.time()
            expected_status_value = 0
            output_lines = output.splitlines()
            output = "\n".join(output_lines[:-1] if not wall else output_lines)
            print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
            if expected_status_value is not None and status != expected_status_value:
                raise InvocationError(
                    f"status={status} != {expected_status_value}.\nInput=[{invocation}].\nOutput=[{output}]".format(
                        status, invocation, output))
            print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
            if wall:
                print("///////////////////////////////////////////////////////////////////")
                measured_time = wall_time_after - wall_time_before
            else:
                print("======================================================00000000")
                m = re.fullmatch(r"u(\d+\.\d+)@s(\d+\.\d+)", output_lines[-1])
                if m is not None:
                    measured_time = float(m.group(1)) + float(m.group(2))
                else:
                    raise InvocationError(f"Output {output_lines} did not contain a valid time signature")

            print("2222222222222222222222222222222222222222222222222222222222222222222")
            if options.verbose > 3:
                print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
        except tcall.InvocationError as ex:
            print("3333333333333333333333333333333333333333333333333333333333333333333333")
            raise CompressionException(original_path=original_path, compressed_path=compressed_path,
                                       file_info=original_file_info, status=-1, output=None) from ex
        print("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        compression_results = self.compression_results_from_paths(original_path=original_path,
                                                                  compressed_path=compressed_path)
        compression_results.compression_time_seconds = measured_time
        print("BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")
        if self.output_invocation_dir is not None:
            invocation_name = "invocation_compression_" + self.name + os.path.abspath(
                os.path.realpath(original_file_info["file_path"])).replace(os.sep, "_")
            with open(os.path.join(self.output_invocation_dir, invocation_name), "w") as invocation_file:
                invocation_file.write(f"Original path: {original_path}\n"
                                      f"Compressed path: {compressed_path}\n"
                                      f"Codec: {self.name}\n"
                                      f"Invocation: {invocation}\n"
                                      f"Status: {status}\n"
                                      f"Output: {output}\n"
                                      f"Measured time: {measured_time}")

        return compression_results

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        print("DECOMPRESS")
        decompression_params = self.get_decompression_params(compressed_path=compressed_path,
                                                             reconstructed_path=tempfile.NamedTemporaryFile().name,
                                                             original_file_info=original_file_info)
        invocation = f"{self.decompressor_path} {decompression_params}"
        print(invocation)

        try:
            status, output, measured_time = tcall.get_status_output_time(invocation)
            if options.verbose > 3:
                print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
        except tcall.InvocationError as ex:
            raise DecompressionException(compressed_path=compressed_path, reconstructed_path=reconstructed_path,
                                         file_info=original_file_info, status=-1, output=None) from ex

        decompression_results = self.decompression_results_from_paths(compressed_path=compressed_path,
                                                                      reconstructed_path=reconstructed_path)

        decompression_results.decompression_time_seconds = measured_time
        decompression_results.codec_param_dict["emporda_option"] = 3

        if self.output_invocation_dir is not None:
            invocation_name = "invocation_decompression_" + self.name + os.path.abspath(os.path.realpath(
                original_file_info["file_path"] if original_file_info is not None else compressed_path)).replace(os.sep,
                                                                                                                 "_")
            with open(os.path.join(self.output_invocation_dir, invocation_name), "w") as invocation_file:
                invocation_file.write(f"Compressed path: {compressed_path}\n"
                                      f"Reconstructed path: {reconstructed_path}\n"
                                      f"Codec: {self.name}\n"
                                      f"Invocation: {invocation}\n"
                                      f"Status: {status}\n"
                                      f"Output: {output}\n"
                                      f"Measured time: {measured_time}")

        return decompression_results

