from enb import icompression
from enb.config import get_options

options = get_options()
class HuffmanWrapper(icompression.WrapperCodec, icompression.LosslessCodec):
	def __init__(self):
		icompression.WrapperCodec.__init__(self, compressor_path=f"./plugin_Huffman/Huff",
		decompressor_path=f"./plugin_Huffman/Huff", param_dict=None, output_invocation_dir=None)

	def get_compression_params(self, original_path, compressed_path, original_file_info):
		return f" -h -f {original_path} {compressed_path}"

	def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
		return f" -h -d -f {compressed_path} {reconstructed_path}"
