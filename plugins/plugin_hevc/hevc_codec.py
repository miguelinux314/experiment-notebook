import os
from enb import icompression
from enb.config import get_options

options = get_options()

# TODO: document module
# TODO: document classes and initializer parameters
# TODO: add parameter to control target bitrate (in lossy)
# Don't include it if the user does not choose anything
#       --RateControl            Rate control: enable rate control
#       --TargetBitrate          Rate control: target bit-rate

class HEVC(icompression.WrapperCodec):
    """
    Base class for HEVC coder
    """
    def __init__(self, config_path, chroma_format="400", qp=0):
        """
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        :param qp: Specifies the base value of the quantization parameter (0-51).
        """
        chroma_format = str(chroma_format)
        assert chroma_format in ["400"], f"Chroma format {chroma_format} not supported."

        param_dict = dict(chroma_format=chroma_format)

        assert 0 <= qp <= 51
        param_dict['QP'] = qp

        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "TAppEncoderStatic"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "TAppDecoderStatic"),
            param_dict=param_dict)

        self.config_path = config_path

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-i {original_path} " \
               f"-c {self.config_path} " \
               f"-b {compressed_path} " \
               f"-wdt {original_file_info['width']} " \
               f"-hgt {original_file_info['height']} " \
               f"-f {original_file_info['component_count']} " \
               f"-cf {self.param_dict['chroma_format']} " \
               f"--InputChromaFormat={self.param_dict['chroma_format']} " \
               f"--InputBitDepth={8 * original_file_info['bytes_per_sample']} "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-b {compressed_path} " \
               f"-o {reconstructed_path} " \
               f"-d {8 * original_file_info['bytes_per_sample']}"


class HEVC_lossless(icompression.LosslessCodec, HEVC):
    """
    HEVC subclass for lossless compression
    """
    def __init__(self, config_path=None, chroma_format="400"):
        """
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        """
        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f"hevc_lossless_{chroma_format}.cfg")
        HEVC.__init__(self, config_path, chroma_format, qp=0)

    @property
    def label(self):
        return "HEVC lossless"


class HEVC_lossy(icompression.LossyCodec, HEVC):
    """
    HEVC subclass for lossy compression
    """
    def __init__(self, config_path=None, chroma_format="400", qp=4, bit_rate=None):
        """
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        :param qp: Specifies the base value of the quantization parameter (0-51).
        :bit_rate: target bitrate in bps.
        """
        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f"hevc_lossy_{chroma_format}.cfg")
        HEVC.__init__(
            self, config_path=config_path, chroma_format=chroma_format, qp=qp)

        self.param_dict['bit_rate'] = bit_rate

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        if original_file_info['bytes_per_sample'] > 1:
            raise Exception(f"Bytes per sample = {original_file_info['bytes_per_sample']} "
                            f"not supported yet.")
        else:
            params = super().get_compression_params(
                original_path=original_path,
                compressed_path=compressed_path,
                original_file_info=original_file_info) + \
                   f" -q {self.param_dict['QP']}"

            if self.param_dict['bit_rate'] is not None:
                params += f" --RateControl" \
                          f" --TargetBitrate={self.param_dict['bit_rate']}"

            return params

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        if original_file_info['bytes_per_sample'] > 1:
            raise Exception(f"Bytes per sample = "
                            f"{original_file_info['bytes_per_sample']} "
                            f"not supported")
        else:
            return super().get_decompression_params(compressed_path=compressed_path,
                                                    reconstructed_path=reconstructed_path,
                                                    original_file_info=original_file_info)

    @property
    def label(self):
        return "HEVC lossy"
