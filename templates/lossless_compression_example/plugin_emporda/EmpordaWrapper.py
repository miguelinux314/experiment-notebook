import os
from enb import icompression, tcall
from enb.config import get_options
import tempfile

options = get_options()


class EmpordaWrapper(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self, transformer_path=f"/plugin_emporda/ffc.jar", quantizer_step=1, emporda_option=3):
        # super().__init__(compressor_path="./plugin_emporda/emporda.jar", decompressor_path="./plugin_emporda/emporda.jar")
        icompression.WrapperCodec.__init__(self, compressor_path=f"./plugin_emporda/emporda.jar",
                                           decompressor_path=f"./plugin_emporda/emporda.jar", param_dict=None,
                                           output_invocation_dir=None)

        self.transformer_path = transformer_path
        self.quantizer_step = quantizer_step
        self.emporda_option = emporda_option

    def get_transform_params(self, original_path, transform_path, original_file_info):
        return f" -i {original_path} -ig {original_file_info['component_count']} " \
               f"{original_file_info['height']} {original_file_info['width']} {original_file_info['bytes_per_sample']}" \
               f" {0 if original_file_info['big_endian'] else 1} 0 -o {transform_path} -og {original_file_info['component_count']} " \
               f"{original_file_info['height']} {original_file_info['width']} 2 0 0"
        """
		f"java -jar -Xmx4096m {self.transformer_path} -i {original_path} -ig {original_file_info['component_count']} " \
		f"{original_file_info['height']} {original_file_info['width']} {original_file_info['bytes_per_sample']}" \
		f" {0 if original_file_info['big_endian'] else 1 } 0 -o {transform_path} -og {original_file_info['component_count']} " \
		f"{original_file_info['height']} {original_file_info['width']} 2 0 0"
		"""

    def get_detransform_params(self, reconstructed_path, original_file_info):
        return f" -i {reconstructed_path}.raw -ig {original_file_info['component_count']} " \
               f"{original_file_info['height']} {original_file_info['width']} 2 0 0 -o {reconstructed_path} -og {original_file_info['component_count']} " \
               f"{original_file_info['height']} {original_file_info['width']} {original_file_info['bytes_per_sample']} {0 if original_file_info['big_endian'] else 1} 0"
        """
		f"java -jar -Xmx4096m {self.transformer_path} -i {reconstructed_path}.raw -ig {original_file_info['component_count']} "\
		f"{original_file_info['height']} {original_file_info['width']} 2 0 0 -o {reconstructed_path} -og {original_file_info['component_count']} "\
		f"{original_file_info['height']} {original_file_info['width']} {original_file_info['bytes_per_sample']} {0 if original_file_info['big_endian'] else 1} 0"
		"""

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f" -c -i {compressed_path} -o {compressed_path} -ig {original_file_info['component_count']} " \
               f"{original_file_info['height']} {original_file_info['width']} 2 0 0 -qs {self.quantizer_step} -ec " \
               f"{self.emporda_option} -cm 1 -pm 0 -wp 1024 -up 32 -f ./plugin_emporda/options.txt"
        """
		f"{self.get_transform_params(original_path, compressed_path, original_file_info)}; java -Xmx24g -jar {self.compressor_path} -c -i" \
		f" {compressed_path} -o {compressed_path} -ig {original_file_info['component_count']} " \
		f"{original_file_info['height']} {original_file_info['width']} 2 0 0 -qs {self.quantizer_step} -ec " \
		f"{self.emporda_option} -cm 1 -pm 0 -wp 1024 -up 32 -f ./plugin_emporda/options.txt"
		"""

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f" -d -i {compressed_path} -o {reconstructed_path}.raw -ig " \
               f"{original_file_info['component_count']} {original_file_info['height']} {original_file_info['width']} 2 0 0 -qs {self.quantizer_step} " \
               f"-ec {self.emporda_option} -cm 1 -pm 0 -wp 1024 -up 32 -f ./plugin_emporda/options.txt"

        """
		java -Xmx24g -jar {self.decompressor_path} -d -i {compressed_path} -o {reconstructed_path}.raw -ig "\
		f"{original_file_info['component_count']} {original_file_info['height']} {original_file_info['width']} 2 0 0 -qs {self.quantizer_step} "\
		f"-ec {self.emporda_option} -cm 1 -pm 0 -wp 1024 -up 32 -f ./plugin_emporda/options.txt; {self.get_detransform_params(reconstructed_path, original_file_info)}"
		"""

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        print("COMPRESS")
        transformed_file = tempfile.NamedTemporaryFile()
        transformed_path = transformed_file.name
        compression_params = self.get_compression_params(original_path=original_path, compressed_path=compressed_path,
                                                         original_file_info=original_file_info)
        transform_params = self.get_transform_params(original_path=original_path, transform_path=compressed_path,
                                                     original_file_info=original_file_info)

        invocation = f"java -jar -Xmx4096m {transformed_path} {transform_params}; java -jar -Xmx24g {self.compressor_path} {compression_params}"

        try:
            status, output, measured_time = tcall.get_status_output_time(invocation=invocation)
            if options.verbose > 3:
                print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
        except tcall.InvocationError as ex:
            raise CompressionException(original_path=original_path, compressed_path=compressed_path,
                                       file_info=original_file_info, status=-1, output=None) from ex

        compression_results = self.compression_results_from_paths(original_path=original_path,
                                                                  compressed_path=compressed_path)
        compression_results.compression_time_seconds = measured_time
        compression_results.codec_param_dict["emporda_option"] = 3
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
        detransform_params = self.get_detransform_params(reconstructed_path=reconstructed_path,
                                                         original_file_info=original_file_info)
        invocation = f"java -jar -Xmx4096m {self.decompressor_path} {decompression_params}; java -jar -Xmx24g {self.transformer_path} {detransform_params}"

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
