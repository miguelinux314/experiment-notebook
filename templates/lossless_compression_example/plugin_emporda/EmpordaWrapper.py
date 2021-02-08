import os
import math
from enb import icompression, tcall
from enb.config import get_options

options = get_options()


class EmpordaWrapper(icompression.WrapperCodec, icompression.LosslessCodec):
	def __init__(self, transformer_path="./plugin_emporda/ffc.jar", quantizer_step=1, emporda_option=3):
		#super().__init__(compressor_path="./plugin_emporda/emporda.jar", decompressor_path="./plugin_emporda/emporda.jar")
		icompression.WrapperCodec.__init__(
            self, compressor_path="./plugin_emporda/emporda.jar", decompressor_path="./plugin_emporda/emporda.jar",
            param_dict=None, output_invocation_dir=None)

		self.transformer_path = transformer_path
		self.quantizer_step = quantizer_step
		self.emporda_option = emporda_option

	def get_transform_params(self, original_path, transform_path, original_file_info):
		return f"java -jar -Xmx4096m {self.transformer_path} -i {original_path} -ig {original_file_info['component_count']} " \
		f"{original_file_info['height']} {original_file_info['width']} {original_file_info['bytes_per_sample']}" \
		f" {0 if original_file_info['big_endian'] else 1 } 0 -o {transform_path} -og {original_file_info['component_count']} " \
		f"{original_file_info['height']} {original_file_info['width']} 2 0 0"
	'''
	def get_detransform_params(self, reconstructed_path, original_file_info):
		return f"java -jar -Xmx4096m {self.transformer_path} -i {reconstructed_path}.raw -ig {original_file_info['component_count']} " \
		f"{original_file_info['height']} {original_file_info['width']} 2 0 0 -o {reconstructed_path} " \
		f"-og {original_file_info['component_count']} {original_file_info['height']} " \
		f"{original_file_info['width']} {original_file_info['bytes_per_sample']} {0 if original_file_info['big_endian'] else 1 } 0"
	'''
	def get_detransform_params(self, reconstructed_path, original_file_info):
		return f"java -jar -Xmx4096m {self.transformer_path} -i {reconstructed_path}.raw -ig {original_file_info['component_count']} "\
		f"{original_file_info['height']} {original_file_info['width']} 2 0 0 -o {reconstructed_path} -og {original_file_info['component_count']} "\
		f"{original_file_info['height']} {original_file_info['width']} {original_file_info['bytes_per_sample']} {0 if original_file_info['big_endian'] else 1} 0"

	def get_compression_params(self, original_path, compressed_path, original_file_info):
		return f"{self.get_transform_params(original_path, compressed_path, original_file_info)}; java -Xmx24g -jar {self.compressor_path} -c -i" \
		f" {compressed_path} -o {compressed_path} -ig {original_file_info['component_count']} " \
		f"{original_file_info['height']} {original_file_info['width']} 2 0 0 -qs {self.quantizer_step} -ec " \
		f"{self.emporda_option} -cm 1 -pm 0 -wp 1024 -up 32 -f /home/ester/Documentos/GICI/experiment-notebook-master/templates/lossless_compression_example/plugin_emporda/options.txt"
		#TODO: options.txt (Modificat path)
	'''
	def get_decompression_params(self, compressed_path, recontructed_path, original_file_info):
		return f"java -Xmx24g -jar {self.decompressor_path} -d -i" \
		f" {compressed_path} -o {recontructed_path}.raw -ig {original_file_info['component_count']} " \
		f"{original_file_info['height']} {original_file_info['width']} 2 0 0 -qs {self.quantizer_step} -ec " \
		f"{self.emporda_option} -cm 1 -pm 0 -wp 1024 -up 32 -f /home/ester/Documentos/GICI/experiment-notebook-master/templates/lossless_compression_example/plugin_emporda/options.txt; "
		f"{self.get_detransform_params(recontructed_path, original_file_info)}"
	'''
	def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
		return f"java -Xmx24g -jar {self.decompressor_path} -d -i {compressed_path} -o {reconstructed_path}.raw -ig "\
		f"{original_file_info['component_count']} {original_file_info['height']} {original_file_info['width']} 2 0 0 -qs {self.quantizer_step} "\
		f"-ec {self.emporda_option} -cm 1 -pm 0 -wp 1024 -up 32 -f options.txt; {self.get_detransform_params(reconstructed_path, original_file_info)}"

	def compress(self, original_path: str, compressed_path: str, original_file_info=None):
		print("COMPRESS\n")
		compression_params = self.get_compression_params(original_path=original_path, compressed_path=compressed_path, original_file_info=original_file_info)
		invocation = compression_params

		try:
			status, output, measured_time = tcall.get_status_output_time(invocation=invocation)
			print("STATUS 1", status)
			print("OUTPUT 1", output)
			print("MEASURED TIME 1", measured_time)
			if options.verbose > 3:
				print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
		except tcall.InvocationError as ex:
			print("EXCEPT 1")
			raise CompressionException(original_path=original_path, compressed_path=compressed_path, file_info=original_file_info, status=-1, output=None) from ex

		compression_results = self.compression_results_from_paths(original_path=original_path, compressed_path=compressed_path)
		compression_results.compression_time_seconds = measured_time
		compression_results.codec_param_dict["emporda_option"]=3
		print("COMPRESSION RESULTS 1 - ", compression_results)
		if self.output_invocation_dir is not None:
			print("If 1")
			invocation_name = "invocation_compression_" + self.name + os.path.abspath(os.path.realpath(original_file_info["file_path"])).replace(os.sep, "_")
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
		print("DECOMPRESS\n")
		decompression_params = self.get_decompression_params(compressed_path=compressed_path, reconstructed_path=reconstructed_path,original_file_info=original_file_info)
		invocation = decompression_params

		try:
			status, output, measured_time = tcall.get_status_output_time(invocation)
			print("STATUS 2", status)
			print("OUTPUT 2", output)
			print("MEASURED TIME 2", measured_time)
			if options.verbose > 3:
				print(f"[{self.name}] Compression OK; invocation={invocation} - status={status}; output={output}")
		except tcall.InvocationError as ex:
			print("EXCEPT 2")
			raise DecompressionException(compressed_path=compressed_path, reconstructed_path=reconstructed_path, file_info=original_file_info, status=-1, output=None) from ex

		decompression_results = self.decompression_results_from_paths(compressed_path=compressed_path, reconstructed_path=reconstructed_path)

		decompression_results.decompression_time_seconds = measured_time
		compression_results.codec_param_dict["emporda_option"]=3
		print(decompression_results)

		if self.output_invocation_dir is not None:
			print("If 2")
			invocation_name = "invocation_decompression_" + self.name + os.path.abspath(os.path.realpath(original_file_info["file_path"] if original_file_info is not None else compressed_path)).replace(os.sep,"_")
			with open(os.path.join(self.output_invocation_dir, invocation_name), "w") as invocation_file:
				invocation_file.write(f"Compressed path: {compressed_path}\n"
					f"Reconstructed path: {reconstructed_path}\n"
					f"Codec: {self.name}\n"
					f"Invocation: {invocation}\n"
					f"Status: {status}\n"
					f"Output: {output}\n"
					f"Measured time: {measured_time}")

		return decompression_results

