
import os
from enb import icompression
from enb.config import get_options

options = get_options()

class HEVC_H265(icompression.WrapperCodec, icompression.LossyCodec):
    def __init__(self, config_path):
        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "TAppEncoderStatic"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "TAppDecoderStatic"),
            param_dict=None, output_invocation_dir=None)
        self.config_path = config_path

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-i {original_path} -c {self.config_path} -b {compressed_path} -wdt {original_file_info['width']} -hgt " \
               f"{original_file_info['height']} -f {original_file_info['component_count']} -cf 400 " \
               f"--InputChromaFormat=400 --MSBExtendedBitDepth={8*original_file_info['bytes_per_sample']} " \
               f"--InputBitDepth={8*original_file_info['bytes_per_sample']}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-b {compressed_path} -o {reconstructed_path}"

    @property
    def label(self):
        return "HEVC H265"
