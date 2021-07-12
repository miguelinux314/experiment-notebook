#!/usr/bin/env python
"""
Wrapper for the VVC codec, using the reference implementation from

https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM/-/tree/master
"""

import os

import enb.icompression
from enb import icompression
from enb.config import options
import math


class VVC(icompression.WrapperCodec):
    """
    Base class for VVC coder
    """
    default_qp = 0

    def __init__(self, config_path, chroma_format="400", qp=None):
        """
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        :param qp: Specifies the base value of the quantization parameter (0-51).
        """
        chroma_format = str(chroma_format)
        assert chroma_format in ["400"], f"Chroma format {chroma_format} not supported."
        qp = int(qp) if qp is not None else self.default_qp
        assert 0 <= qp <= 63

        param_dict = dict(chroma_format=chroma_format, QP=qp)
        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "EncoderAppStatic"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "DecoderAppStatic"),
            param_dict=param_dict)

        self.config_path = config_path

        @staticmethod
        def get_binary_signature(binary_path):
            return "debug"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info['component_count'] == 1, f"Only 1 frame supported"
        return f"-i {original_path} " \
               f"-c {self.config_path} " \
               f"-b {compressed_path} " \
               f"-wdt {original_file_info['width']} " \
               f"-hgt {original_file_info['height']} " \
               f"-f {original_file_info['component_count']} " \
               f"-cf {self.param_dict['chroma_format']} " \
               f"--InputChromaFormat={self.param_dict['chroma_format']} " \
               f"--InputBitDepth={8 * original_file_info['bytes_per_sample']} " \
               f"--InternalBitDepth={8 * original_file_info['bytes_per_sample']} " \
               f"-fr 1 "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        assert original_file_info['component_count'] == 1, f"Only 1 frame supported"
        return f"-b {compressed_path} " \
               f"-o {reconstructed_path} " \
               f"-d {8 * original_file_info['bytes_per_sample']}"

    @property
    def label(self):
        raise NotImplementedError("Subclasses must implement their own label.")


class VVC_lossless(VVC, icompression.LosslessCodec):
    """
    VVC subclass for lossless compression
    """

    def __init__(self, config_path=None, chroma_format="400"):
        """
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        """
        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f"vvc_lossless_{chroma_format}.cfg")
        VVC.__init__(self, config_path, chroma_format, qp=0)

    @property
    def label(self):
        return "VVC lossless"


class VVC_lossy(VVC, icompression.LossyCodec):
    """
    VVC subclass for lossy compression
    """

    rate_decimals = 3

    def __init__(self, config_path=None, chroma_format="400", qp=None, bit_rate=None):
        """
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        :param qp: Specifies the base value of the quantization parameter (0-51).
        :param bit_rate: target bitrate in bps.
        """

        bit_rate = round(float(bit_rate), self.rate_decimals) if bit_rate is not None else bit_rate

        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f"vvc_lossy_{chroma_format}.cfg")
        VVC.__init__(
            self, config_path=config_path, chroma_format=chroma_format, qp=qp)

        self.param_dict['bit_rate'] = bit_rate

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert self.param_dict['bit_rate'] is None, f"Bit rate not implemented"

        if original_file_info['bytes_per_sample'] > 1:
            raise Exception(f"Bytes per sample = {original_file_info['bytes_per_sample']} "
                            f"not supported yet.")

        params = super().get_compression_params(
            original_path=original_path,
            compressed_path=compressed_path,
            original_file_info=original_file_info)

        if self.param_dict['bit_rate'] is not None:
            target_rate = math.ceil(self.param_dict['bit_rate']
                                    * original_file_info['width'] * original_file_info['height'])
            params += " --RateControl"
            params += f" --TargetBitrate={target_rate} "
            # params += "--MaxSubLayers=16"
        else:
            params += f" --QP={self.param_dict['QP']} --InitialQP={self.param_dict['QP']}"
        return params

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        assert self.param_dict['bit_rate'] is None, f"Bit rate not implemented"

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
        if self.param_dict["bit_rate"] is not None:
            rate_format = "{0:." + str(self.rate_decimals) + "f}"
            s = f"VVC {rate_format.format(self.param_dict['bit_rate'])}bps"
        else:
            s = f"VVC QP{self.param_dict['QP']}"
        return s

if __name__ == '__main__':
    print("This example compresses all .raw images in ./test_data/")
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")
    exp = enb.icompression.LosslessCompressionExperiment(codecs=[VVC_lossless()])
    enb.aanalysis.ScalarDistributionAnalyzer().analyze_df(
        full_df=exp.get_df(),
        column_to_properties=exp.column_to_properties)
    print("Done!")
    