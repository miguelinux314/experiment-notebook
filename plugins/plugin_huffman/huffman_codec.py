import os
from enb import icompression
from enb.config import get_options

options = get_options()

class HuffmanWrapper(icompression.WrapperCodec, icompression.LosslessCodec):
	def __init__(self):
		icompression.WrapperCodec.__init__(self,
			compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "Huff"),
			decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "Huff"),
			param_dict=None, output_invocation_dir=None)

	def get_compression_params(self, original_path, compressed_path, original_file_info):
		return f"-h -f {original_path} {compressed_path}"

	def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
		return f"-h -d -f {compressed_path} {reconstructed_path}"

	@property
	def label(self):
        	return "Huffman"
