import os
from enb import icompression, tcall
from enb.config import get_options
import tempfile


options = get_options()


class FSEWrapper(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self):
        icompression.WrapperCodec.__init__(self, compressor_path=f"./fse",
                                           decompressor_path=f"./fse", param_dict=None,
                                           output_invocation_dir=None)


    def get_compression_params(self, original_path, compressed_path, original_file_info):
        print("COMPRESSION")
        return f" -e {original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        print("DECOMPRESSION")
        return f" -e -d {compressed_path} {reconstructed_path}"

