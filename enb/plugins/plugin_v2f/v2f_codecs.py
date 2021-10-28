#!/usr/bin/env python3
"""Codecs wrapping V2F forests.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/09/01"

import os
import subprocess
import enb

# Constants taken from the C code for consistency and maintainability.
V2F_C_QUANTIZER_MODE_NONE = 0
V2F_C_QUANTIZER_MODE_UNIFORM = 1
V2F_C_QUANTIZER_MODE_COUNT = 2
V2F_C_DECORRELATOR_MODE_NONE = 0
V2F_C_DECORRELATOR_MODE_LEFT = 1
V2F_C_DECORRELATOR_MODE_2_LEFT = 2
V2F_C_DECORRELATOR_MODE_JPEGLS = 3
V2F_C_DECORRELATOR_MODE_COUNT = 4
V2F_C_QUANTIZER_MODE_MAX_STEP_SIZE = 255


class V2FCodec(enb.icompression.LosslessCodec,
               enb.icompression.NearLosslessCodec,
               enb.icompression.WrapperCodec):
    """Wrapper for the V2F compressor/decompressor tools in C,
    which must be present in the same path as this script.
    """

    def __init__(self, v2fc_header_path, qstep=None, quantizer_mode=None, decorrelator_mode=None,
                 verify_on_initialization=True, time_results_dir=None):
        """
        Initialize a V2F codec that employs the forest definition in `v2fc_header_path`, and optionally
        overwrite the quantization and decorrelation defined in them.

        :param v2fc_header_path: path to the V2F forest definition to be employed
        :param qstep: quantization step size. Only applied if quantizer_mode is not
          V2F_C_DECORRELATOR_MODE_NONE. Cannot exceed V2F_C_QUANTIZER_MODE_MAX_STEP_SIZE.
        :param quantizer_mode: quantization mode; see the V2F_C_QUANTIZER_MODE_* constants.
        :param decorrelator_mode: decorrelation (e.g., prediction) mode;
          see see the V2F_C_DECORRELATOR_MODE_* constants.
        :param verify_on_initialization: if True, the codec in v2fc_heder_path is verified upon initialization.
        :param time_results_dir: if not None, it must be the path of a directory that will be used to store time
          measurements reported by the V2F prototype.
        """
        self.codec_root_dir = os.path.abspath(os.path.dirname(__file__))
        super().__init__(compressor_path=os.path.join(self.codec_root_dir, "v2f_compress"),
                         decompressor_path=os.path.join(self.codec_root_dir, "v2f_decompress"),
                         param_dict=dict(
                             v2fc_header_path=v2fc_header_path,
                             qstep=qstep,
                             quantizer_mode=quantizer_mode,
                             decorrelator_mode=decorrelator_mode))

        # Header path with the V2F codec (including forest) definition
        self.v2fc_header_path = v2fc_header_path
        if not self.v2fc_header_path or not os.path.isfile(self.v2fc_header_path):
            raise ValueError(f"Cannot find a V2F codec definition at {repr(self.v2fc_header_path)}. "
                             f"Please make sure you are passing the right argument to "
                             f"{self.__class__}'s initialzier, and that the file is actually present.")

        # Verify the chosen codec if configured to do so.
        self.verifier_path = os.path.join(self.codec_root_dir, "v2f_verify_codec")
        if verify_on_initialization:
            self.verify_codec(v2fc_header_path=v2fc_header_path)

        # Prepare the folder where time measurements are to be stored
        self.time_results_dir = time_results_dir
        if self.time_results_dir:
            os.makedirs(self.time_results_dir, exist_ok=True)

    def verify_codec(self, v2fc_header_path):
        """Run the V2F codec verification tool for a given path.
        An exception is raised if this verification fails.
        """
        if not os.path.isfile(self.verifier_path):
            raise ValueError(f"Could not find the V2F codec verifier tool at {repr(self.verifier_path)}. "
                             f"Please make sure it is present at that path and try again.")

        with enb.logger.info_context(f"Verifying V2F codec {repr(v2fc_header_path)}"):
            invocation = f"{self.verifier_path} {os.path.abspath(v2fc_header_path)}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise ValueError(f"V2F codec verification failed for {repr(v2fc_header_path)}.\n"
                                 f"status: {status}\n"
                                 f"invocation: {repr(invocation)}\n"
                                 f"execution output: {output}.")
            else:
                enb.logger.info(f"Verification OK. Returned message:\n{output}")

    def get_time_path(self, original_path):
        assert self.time_results_dir, f"Trying to run get_time_path() without having set self.time_results_dir."
        return os.path.join(self.time_results_dir,
                            f"q{self.param_dict['quantizer_mode']}_"
                            f"s{self.param_dict['qstep']}_"
                            f"d{self.param_dict['decorrelator_mode']}_" + \
                            os.path.basename(self.v2fc_header_path).replace(os.sep, "__"),
                            os.path.abspath(original_path).replace(os.sep, "__")
                            + "_times.csv")

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_path} {self.get_optional_argument_string(original_path=original_path)} " \
               f"{self.v2fc_header_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {self.get_optional_argument_string(original_path=None)} " \
               f"{self.v2fc_header_path} {reconstructed_path}"

    def get_optional_argument_string(self, original_path):
        optional_str = ""
        if self.param_dict['quantizer_mode'] is not None:
            optional_str += f"-q {self.param_dict['quantizer_mode']} "
        if self.param_dict['qstep'] is not None:
            optional_str += f"-s {self.param_dict['qstep']} "
        if self.param_dict['decorrelator_mode'] is not None:
            optional_str += f"-d {self.param_dict['decorrelator_mode']} "
        if self.time_results_dir is not None and original_path is not None:
            time_path = self.get_time_path(original_path)
            os.makedirs(os.path.dirname(time_path), exist_ok=True)
            optional_str += f"-t {time_path} "
        return optional_str

    @property
    def label(self):
        return "V2F"
