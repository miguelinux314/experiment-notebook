#!/usr/bin/env python
"""
Wrapper for the VVC codec, using the reference implementation from

https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM/-/tree/master
"""
__author__ = "Natalia Blasco, Ester Jara, Artemis Llabrés and Miguel Hernández-Cabronero"
__since__ = "2021/06/01"

import os
import math
import tempfile

import enb.isets
import numpy as np
from enb import icompression
from enb.config import options


class VVC(icompression.LittleEndianWrapper):
    """
    Base class for VVC coder.
    """

    def __init__(self, config_path, chroma_format="400", qp=0):
        """
        :param config_path: path to the .cfg configuration file for VVC.
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        :param qp: Specifies the base value of the quantization parameter (0-63, extended from HEVC's 0-51).
        """
        chroma_format = str(chroma_format)
        assert chroma_format in ["400"], f"Chroma format {chroma_format} not supported."
        assert qp == int(qp), f"Invalid non-integer QP={qp}"
        assert 0 <= qp <= 63, f"Invalid QP value {qp} out of range [0, 63]"
        self.config_path = os.path.relpath(config_path, options.project_root)
        assert os.path.isfile(config_path), f"VVC configuration file path {repr(config_path)} not found."

        param_dict = dict(chroma_format=chroma_format, QP=qp, config_path=config_path)
        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "EncoderAppStatic"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "DecoderAppStatic"),
            param_dict=param_dict)

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        if original_file_info['bytes_per_sample'] > 1:
            raise Exception(f"Bytes per sample = {original_file_info['bytes_per_sample']} "
                            f"not supported yet.")

        return f"-i {original_path} " \
               f"-c {os.path.join(options.project_root, self.param_dict['config_path'])} " \
               f"-b {compressed_path} " \
               f"-wdt {original_file_info['width']} " \
               f"-hgt {original_file_info['height']} " \
               f"-f {original_file_info['component_count']} " \
               f"-cf {self.param_dict['chroma_format']} " \
               f"--InputChromaFormat={self.param_dict['chroma_format']} " \
               f"--InputBitDepth={8 * original_file_info['bytes_per_sample']} " \
               f"-fr 1 "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-b {compressed_path} " \
               f"-o {reconstructed_path} " \
               f"-d {8 * original_file_info['bytes_per_sample']}"

    @property
    def label(self):
        raise NotImplementedError("Subclasses must implement their own label.")


class VVCLosslessIntra(VVC, icompression.LosslessCodec):
    """
    VVC subclass for lossless compression
    """

    def __init__(self, config_path=None, chroma_format="400"):
        """
        :param config_path: if not None, it must be a path to the .cfg configuration file for VVC.
          If None, the default configuration file for this class is selected.
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        """
        assert chroma_format == "400", f"Only '400' chroma format is supported by this plugin."
        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.relpath(__file__, options.project_root)),
                              f"vvc_lossless_{chroma_format}_intra.cfg")
        VVC.__init__(self, config_path, chroma_format, qp=0)

    @property
    def label(self):
        return "VVC lossless intra"


class VVCLosslessInter(VVC, icompression.LosslessCodec):
    """Inter, lossless compression with GOP size 8, based on the encoder_lowdelay_vtm_perf.cfg distributed
    with VVC.
    """

    def __init__(self, config_path=None, chroma_format="400"):
        """
        :param config_path: if not None, it must be a path to the .cfg configuration file for VVC.
          If None, the default configuration file for this class is selected.
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        :param gop_size: size of the group of pictures used for coding.
        :param intra_period: an intra slice is used every these many frames. It must be a multiple of
          gop_size (they can be identical).
        """
        assert chroma_format == "400", f"Only '400' chroma format is supported by this plugin."
        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.relpath(__file__, options.project_root)),
                              f"vvc_lossless_{chroma_format}_inter.cfg")
        VVC.__init__(self, config_path, chroma_format, qp=0)

    @property
    def label(self):
        return "VVC lossless inter"


class VVC_lossy(VVC, icompression.LossyCodec):
    """
    VVC subclass for lossy compression.
    This class admits only 1 band (1 frame at a time)
    """
    rate_decimals = 3

    def __init__(self, config_path=None, chroma_format="400", qp=25, bit_rate=None):
        """
        :param chroma_format: Specifies the chroma format used in the input file (only 400 supported).
        :param qp: Specifies the base value of the quantization parameter (0-51).
        :param bit_rate: target bitrate in bps.
        """

        bit_rate = round(float(bit_rate), self.rate_decimals) if bit_rate is not None else bit_rate

        config_path = config_path if config_path is not None \
            else os.path.join(os.path.dirname(os.path.relpath(__file__, options.project_root)),
                              f"vvc_lossy_{chroma_format}_onecomponent.cfg")
        VVC.__init__(
            self, config_path=config_path, chroma_format=chroma_format, qp=qp)

        self.param_dict['bit_rate'] = bit_rate

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["component_count"] == 1, f"Only one component (frame) is supported " \
                                                           f"in this VVC lossy wrapper."

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
