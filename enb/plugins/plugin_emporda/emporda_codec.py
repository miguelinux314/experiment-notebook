#!/usr/bin/env python3
"""Codec wrapper for the emporda software (https://gici.uab.cat/GiciWebPage/downloads.php#emporda)
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2022/04/08"

import os
import enb.icompression
import shutil


class Emporda(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec,
              enb.icompression.JavaWrapperCodec, enb.icompression.GiciLibHelper):
    """Wrapper for the emporda codec (https://gici.uab.cat/GiciWebPage/downloads.php#emporda)
    """

    def __init__(self,
                 compressor_jar=os.path.join(os.path.dirname(__file__), "emporda.jar"),
                 decompressor_jar=os.path.join(os.path.dirname(__file__), "emporda.jar"),
                 qs=0, ec=1, cm=1, pm=0, wp=2048, up=2):
        """
        :param qs: sets the quantization step.
        :param ec: The encoder type that will encode the image.
            0.- Lossless without predictor + entropy encoder.
            1.- Lossless with predictor + entropy encoder.
            2.- Lossless and near-lossless with predictor predictor + entropy encoder.
            3.- Lossless and near-lossless with state-of-the-art predictor + entropy encoder.
        :param cm: context model
            0.- No context model is used.
            1.- Context modelling is used during the encoding process.
        :param pm: Probability model employed for the entropy coder.
            0.- The probability is estimated using a full division operation.
            1.- The probability is estimated using a division implemented through a quantized Look Up Table.
                This option must be used with -qlut option.
            2.- The probability is estimated using only bitwise operators and witout division.
                When this option is used -wp and -up parameters must be the same value of form 2^X.
        :param wp: Indicates the maximum number of symbols within the variable-size sliding windows
          that are employed for the Entropy Coder to compute the probability of the context.
          Must be of the form 2^X.
        :param up: Indicates the number of symbols coded before updating the context probability in the Entropy Coder.
            Must be of the form 2^X.
        """
        assert shutil.which("java") is not None, \
            f"The 'java' program was not found in the path, but is required by {self.__class__.__name__}. " \
            f"Please (re)install a JRE in the path and try again."
        super().__init__(compressor_jar=compressor_jar,
                         decompressor_jar=decompressor_jar,
                         param_dict=dict(qs=qs, ec=ec, cm=cm, pm=pm, wp=wp, up=up))

    @property
    def label(self):
        return "Emporda"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 2, \
            f"Only 16-bit samples are currently supported by {self.__class__.__name__}"
        assert not original_file_info["float"], \
            f"Only integer samples are currently supported by {self.__class__.__name__}"
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are currently supported by {self.__class__.__name__}"

        return f"-Xmx256g -jar {self.compressor_jar} -c -i {original_path} -o {compressed_path} " \
               f"-ig {self.get_gici_geometry_str(original_file_info=original_file_info)} " \
               f"-qs {self.param_dict['qs']} " \
               f"-ec {self.param_dict['ec']} " \
               f"-cm {self.param_dict['cm']} " \
               f"-pm {self.param_dict['pm']} " \
               f"-wp {self.param_dict['wp']} " \
               f"-up {self.param_dict['up']}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 2, \
            f"Only 16-bit samples are currently supported by {self.__class__.__name__}"
        assert not original_file_info["float"], \
            f"Only integer samples are currently supported by {self.__class__.__name__}"
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are currently supported by {self.__class__.__name__}"
        
        return f"-Xmx256g -jar {self.decompressor_jar} -d -i {compressed_path} -o {reconstructed_path} " \
               f"-ig {self.get_gici_geometry_str(original_file_info=original_file_info)} " \
               f"-qs {self.param_dict['qs']} " \
               f"-ec {self.param_dict['ec']} " \
               f"-cm {self.param_dict['cm']} " \
               f"-pm {self.param_dict['pm']} " \
               f"-wp {self.param_dict['wp']} " \
               f"-up {self.param_dict['up']}"
