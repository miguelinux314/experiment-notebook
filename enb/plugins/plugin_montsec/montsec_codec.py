#!/usr/bin/env python3
"""Codec wrapper for the montsec software
"""
__author__ = "Xavier Fernandez Mellado and Pau Quintas Torra"
__since__ = "2023/12/14"

import os
import enb.icompression
import shutil


class Montsec(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec,
              enb.icompression.JavaWrapperCodec, enb.icompression.GiciLibHelper):
    """Wrapper for the montsec codec
    """

    def __init__(self,
                 compressor_jar=os.path.join(os.path.dirname(__file__), "montsec.jar"),
                 decompressor_jar=os.path.join(os.path.dirname(__file__), "montsec.jar"),
                 qs: int = 1, cm: int = 0, bypass: int = 0):
        """
        :param qs: sets the quantization step.
        :param cm: context model
            0.- No context model is used.
            1.- Context modelling type 1 is used during the encoding process (self context).
            2.- Context modelling type 2 is used during the encoding process (HV).
            3.- Context modelling type 3 is used during the encoding process (HVDS).
        :param bypass: Number of the bitplane in which stop compressing and send the raw bit
        """
        assert (cm >= 0) and (cm <= 3), \
            f"The context modeling must be a integer value between [0 and 3]"
        assert (bypass >= 0) and (bypass <= 8), \
            f"Bypass must be into [0 and 8]"
        super().__init__(compressor_jar=compressor_jar,
                         decompressor_jar=decompressor_jar,
                         param_dict=dict(qs=qs, cm=cm, bypass=bypass))

    @property
    def label(self):
        return ("Montsec"
                + (" self context" if self.param_dict['cm'] == 1 else "")
                + (" HV context" if self.param_dict['cm'] == 2 else "")
                + (" HVDS context" if self.param_dict['cm'] == 3 else ""))

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert not original_file_info["float"], \
            f"Only integer samples are currently supported by {self.__class__.__name__}"
        assert original_file_info["bytes_per_sample"] in [1, 2], \
            f"Bytes per sample must be 1 or 2 in class {self.__class__.__name__}"
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are currently supported by {self.__class__.__name__}"

        return f"-Xmx24g -jar {self.compressor_jar} -c -i {original_path} -o {compressed_path} " \
               f"-ig {self.get_gici_geometry_str(original_file_info=original_file_info)} " \
               f"-qs {self.param_dict['qs']} " \
               f"-cm {self.param_dict['cm']} " \
               f"-bypass {self.param_dict['bypass']} "

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        assert not original_file_info["float"], \
            f"Only integer samples are currently supported by {self.__class__.__name__}"
        assert original_file_info["bytes_per_sample"] in [1, 2], \
            f"Bytes per sample must be 1 or 2 in class {self.__class__.__name__}"
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are currently supported by {self.__class__.__name__}"

        return f"-Xmx24g -jar {self.decompressor_jar} -d -i {compressed_path} -o {reconstructed_path} "
