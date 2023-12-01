#!/usr/bin/env python3
"""Wrapper for the HEVC codec, using the reference implementation from

https://vcgit.hhi.fraunhofer.de/jvet/HM
"""
__author__ = "Natalia Blasco, Ester Jara, Artemis Llabrés and Miguel Hernández-Cabronero"
__since__ = "2021/09/01"

import os
import math
from enb import icompression


class HEVC(icompression.LittleEndianWrapper):
    default_qp = 0

    """
    Base class for HEVC coder
    """

    def __init__(self, config_path, chroma_format="400", qp=None):
        """
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        :param qp: Specifies the base value of the quantization parameter (0-51).
        """
        chroma_format = str(chroma_format)
        assert chroma_format in ["400"], f"Chroma format {chroma_format} not supported."
        qp = int(qp) if qp is not None else self.default_qp
        assert 0 <= qp <= 51

        param_dict = dict(chroma_format=chroma_format, QP=qp)

        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(
                os.path.abspath(__file__)), "TAppEncoderStatic"),
            decompressor_path=os.path.join(os.path.dirname(
                os.path.abspath(__file__)), "TAppDecoderStatic"),
            param_dict=param_dict)

        self.config_path = config_path

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        if original_file_info["float"]:
            raise ValueError("This codec does not support floating point data")

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

    @property
    def label(self):
        raise NotImplementedError("Subclasses must implement their own label.")


class HEVC_lossless(icompression.LosslessCodec, HEVC):
    """
    HEVC subclass for lossless compression
    """

    def __init__(self, config_path=None, chroma_format="400"):
        """
        :param chroma_format: Specifies the chroma format used in the input file
        (only 400 supported).
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

    rate_decimals = 3

    def __init__(self, config_path=None, chroma_format="400", qp=25, bit_rate=None):
        """
        :param chroma_format: Specifies the chroma format used in the input file
          (only 400 supported).
        :param qp: Specifies the base value of the quantization parameter (0-51).
        :param bit_rate: target bitrate in bps.
        """
        bit_rate = round(float(bit_rate), self.rate_decimals) if bit_rate is not None else bit_rate

        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f"hevc_lossy_{chroma_format}.cfg")
        HEVC.__init__(
            self, config_path=config_path, chroma_format=chroma_format, qp=qp)

        self.param_dict['bit_rate'] = bit_rate

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        params = super().get_compression_params(
            original_path=original_path,
            compressed_path=compressed_path,
            original_file_info=original_file_info)

        if self.param_dict['bit_rate'] is not None:
            target_rate = math.ceil(self.param_dict['bit_rate']
                                    * original_file_info['width'] * original_file_info['height'])
            params += " --RateControl "
            params += f" --TargetBitrate={target_rate} "
        else:
            params += f" --QP={self.param_dict['QP']} --InitialQP={self.param_dict['QP']}"

        return params

    @property
    def label(self):
        if self.param_dict["bit_rate"] is not None:
            rate_format = "{0:." + str(self.rate_decimals) + "f}"
            s = f"HEVC {rate_format.format(self.param_dict['bit_rate'])}bps"
        else:
            s = f"HEVC QP{self.param_dict['QP']}"

        return s
