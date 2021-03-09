import os
from enb import icompression
from enb.config import get_options

options = get_options()


class HEVC(icompression.WrapperCodec, icompression.LosslessCodec):
    def __init__(self, config_path=None, chroma_format="400"):
        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f"hevc_lossless_{chroma_format}.cfg")

        chroma_format = str(chroma_format)
        assert chroma_format in ["400"], f"Chroma format {chroma_format} not supported."

        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "TAppEncoderStatic"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "TAppDecoderStatic"),
            param_dict=dict(chroma_format=chroma_format))

        self.config_path = config_path

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-i {original_path} -c {self.config_path} -b {compressed_path} -wdt {original_file_info['width']} " \
               f"-hgt {original_file_info['height']} -f {original_file_info['component_count']} " \
               f"-cf {self.param_dict['chroma_format']} --InputChromaFormat={self.param_dict['chroma_format']} " \
               f"--InputBitDepth={8 * original_file_info['bytes_per_sample']}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-b {compressed_path} -o {reconstructed_path} -d {8 * original_file_info['bytes_per_sample']}"

    @property
    def label(self):
        return "HEVC"
