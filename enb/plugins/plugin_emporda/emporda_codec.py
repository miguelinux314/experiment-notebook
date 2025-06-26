#!/usr/bin/env python3
"""Codec wrapper for the emporda software (https://gici.uab.cat/GiciWebPage/downloads.php#emporda)
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2022/04/08"

import os
import shutil

import enb


class EmpordaAC(enb.icompression.LosslessCodec, enb.icompression.NearLosslessCodec,
                enb.icompression.JavaWrapperCodec, enb.icompression.GiciLibHelper):
    """Wrapper for the Empordà codec using a custom Arithmetic Coder

    (https://gici.uab.cat/GiciWebPage/downloads.php#emporda)
    """

    def __init__(self,
                 compressor_jar=os.path.join(os.path.dirname(__file__), "emporda_ac.jar"),
                 decompressor_jar=os.path.join(os.path.dirname(__file__), "emporda_ac.jar"),
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

    @property
    def label(self):
        return "Emporda AC"


class EmpordaCCSDS(enb.icompression.LosslessCodec,
                   enb.icompression.JavaWrapperCodec,
                   enb.icompression.GiciLibHelper):
    """Wrapper for the Empordà codec using the CCSDS 123.0-B-1 entropy coders
    (block adaptive or sample adaptive), with the possibility of enabling and disabling
    the prediction stage.
    (https://gici.uab.cat/GiciWebPage/downloads.php#emporda)
    """
    SAMPLE_ADAPTIVE_ENCODER = 0
    BLOCK_ENCODER = 1
    OPTIONS_SAMPLE_ADAPTIVE_PATH = os.path.join(
        os.path.dirname(__file__), "options_sample_adaptive.txt")
    OPTIONS_BLOCK_ADAPTIVE_PATH = os.path.join(
        os.path.dirname(__file__), "options_block_adaptive.txt")

    def __init__(
            self,
            entropy_coder: int,
            skip_prediction: bool,
            compressor_jar: str = os.path.join(os.path.dirname(__file__), "emporda_ccsds.jar"),
            decompressor_jar: str = os.path.join(os.path.dirname(__file__), "emporda_ccsds.jar")):
        """
        :param entropy_coder: one of EmpordaNoPrediction.SAMPLE_ADAPTIVE_ENCODER or
          EmpordaNoPrediction.BLOCK_ENCODER, for the sample adaptive or the block adaptive
          entropy coder, respectively.
        :param skip_prediction: if True, the prediction stage is skipped
        :param compressor_jar, decompressor_jar: custom jar files implementing the emporda codec.
        """
        enb.icompression.JavaWrapperCodec.__init__(
            self,
            compressor_jar=compressor_jar,
            decompressor_jar=decompressor_jar,
            param_dict={"entropy_coder": entropy_coder,
                        "skip_prediction": 0 if not skip_prediction else 1})

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 1, \
            f"Only 8-bit samples are currently supported by {self.__class__.__name__}"
        assert not original_file_info["float"], \
            f"Only integer samples are currently supported by {self.__class__.__name__}"
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are currently supported by {self.__class__.__name__}"

        if self.param_dict["entropy_coder"] == self.SAMPLE_ADAPTIVE_ENCODER:
            options_file_path = self.OPTIONS_SAMPLE_ADAPTIVE_PATH
        elif self.param_dict["entropy_coder"] == self.BLOCK_ENCODER:
            options_file_path = self.OPTIONS_BLOCK_ADAPTIVE_PATH
        else:
            raise ValueError(f"Invalid entropy coder type {self.param_dict['entropy_coder']!r}")

        return (f"-Xmx256g -jar {self.decompressor_jar} "
                f"-c "
                f"-i {os.path.abspath(original_path)} "
                f"-ig {self.get_gici_geometry_str(original_file_info=original_file_info)} "
                f"-qm 0 "
                f"-o {os.path.abspath(compressed_path)} "
                f"-f {options_file_path} "
                f"-p {'0' if self.param_dict['skip_prediction'] else '1'}")

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        assert original_file_info["bytes_per_sample"] == 1, \
            f"Only 8-bit samples are currently supported by {self.__class__.__name__}"
        assert not original_file_info["float"], \
            f"Only integer samples are currently supported by {self.__class__.__name__}"
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are currently supported by {self.__class__.__name__}"

        if self.param_dict["entropy_coder"] == self.SAMPLE_ADAPTIVE_ENCODER:
            options_file_path = self.OPTIONS_SAMPLE_ADAPTIVE_PATH
        elif self.param_dict["entropy_coder"] == self.BLOCK_ENCODER:
            options_file_path = self.OPTIONS_BLOCK_ADAPTIVE_PATH
        else:
            raise ValueError(f"Invalid entropy coder type {self.param_dict['entropy_coder']!r}")

        return (f"-Xmx256g -jar {self.decompressor_jar} "
                f"-d "
                f"-i {os.path.abspath(compressed_path)} "
                f"-ig {self.get_gici_geometry_str(original_file_info=original_file_info)} "
                f"-qm 0 "
                f"-o {os.path.abspath(reconstructed_path)} "
                f"-f {options_file_path} "
                f"-p {'0' if self.param_dict['skip_prediction'] else '1'}")

    @property
    def label(self):
        prediction_str = " NP" if self.param_dict["skip_prediction"] == 1 else ""
        ec_str = f"Sample adaptive" \
            if self.param_dict["entropy_coder"] == self.SAMPLE_ADAPTIVE_ENCODER \
            else "Block adaptive"
        return f"Emporda CCSDS {prediction_str} ({ec_str})"
