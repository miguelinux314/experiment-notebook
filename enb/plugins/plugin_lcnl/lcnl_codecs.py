#!/usr/bin/env python3
"""Wrappers for the CCSDS 123.0-B-2 codecs.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/01"

import os
import subprocess
import tempfile
import shutil
import sortedcontainers
import math

from enb.atable import get_canonical_path
from enb import icompression
from enb.config import options


class CCSDS_LDC(icompression.LosslessCodec, icompression.WrapperCodec):
    default_large_J = 64

    def __init__(self, bin_dir=None, large_J=None, r=None, restricted_code_options_flag=None,
                 output_header_dir=None):
        """
        :param bin_dir: path to the directory that contains the
          ldc_encoder, ldc_decoder and ldc_header_tool binaries. If it is None,
          options.external_bin_base_dir is None. If this is None as well, the
          same directory of this script is used by default.
        :param large_J: block size (8, 16, 32, or 64), or None for codec's default
        :param r: reference sample period (from 1 to 4096), or None for codec's default
        :param restricted_code_options_flag: use restricted set of code options.
          Must be 0 when n >= 5.
        :param output_header_dir: if not None, LDC headers produced for each
          image are stored in this folder, with a name based on this codec's name
          and the image's full path. Headers stored this way are not reused by the codec
        """
        bin_dir = bin_dir if bin_dir is not None else options.external_bin_base_dir
        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        bin_dir = get_canonical_path(bin_dir)
        assert os.path.isdir(bin_dir), f"Invalid binary dir {bin_dir}."
        ldc_encoder_path = os.path.join(bin_dir, "ldc_encoder")
        ldc_decoder_path = os.path.join(bin_dir, "ldc_decoder")
        ldc_header_tool_path = os.path.join(bin_dir, "ldc_header_tool")

        param_dict = sortedcontainers.SortedDict()
        large_J = large_J if large_J is not None else self.default_large_J
        assert large_J in (8, 16, 32, 64), f"Invalid large_J value {large_J}"
        param_dict["large_j"] = large_J
        if r is not None:
            assert 1 <= r <= 4096, f"Invalid r value {r}"
            param_dict["r"] = r
        if restricted_code_options_flag is not None:
            param_dict["restricted_code_options_flag"] = restricted_code_options_flag
        for p in (ldc_encoder_path, ldc_decoder_path, ldc_header_tool_path):
            assert os.path.isfile(p), f"Binary {p} does not exist"
            assert os.access(p, os.EX_OK), f"Binary {p} is not executable"
        icompression.WrapperCodec.__init__(
            self, compressor_path=ldc_encoder_path,
            decompressor_path=ldc_decoder_path, param_dict=param_dict)
        self.ldc_header_tool_path = ldc_header_tool_path
        self.output_header_dir = output_header_dir

    @property
    def label(self):
        return f"CCSDS 121.0-B-3 J{self.param_dict['large_j']}"

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        with tempfile.NamedTemporaryFile(
                prefix=f"corrected_length_{os.path.basename(original_path)}",
                dir=options.base_tmp_dir) as corrected_length_file, \
                tempfile.NamedTemporaryFile(
                    prefix=f"header_{os.path.basename(original_path)}_") as image_dependent_header_file:
            # Complete full large_j blocks so that LDC does not fail
            shutil.copyfile(original_path, corrected_length_file.name)
            if original_file_info["samples"] % self.param_dict["large_j"] != 0:
                with open(corrected_length_file.name, "ab") as flf:
                    missing_samples = (self.param_dict["large_j"]
                                       - (original_file_info["samples"] % self.param_dict["large_j"]))
                    flf.write(bytes(0 for _ in range(
                        missing_samples * original_file_info["bytes_per_sample"])))
                    flf.flush()

            # Create an image-specific compression header
            header_invocation = \
                f"{self.ldc_header_tool_path} " \
                f"-x n={8 * original_file_info['bytes_per_sample']} " \
                f"-x large_n={os.path.getsize(corrected_length_file.name) // original_file_info['bytes_per_sample']} " \
                f"-x data_sense={0 if original_file_info['signed'] else 1} "
            header_invocation += " ".join(f"-x {k}={v}" for k, v in self.param_dict.items())
            header_invocation += f" {image_dependent_header_file.name}"
            status, output = subprocess.getstatusoutput(header_invocation)
            if status != 0:
                raise Exception(f"Status = {status} != 0.\n"
                                f"Input=[{header_invocation}].\n"
                                f"Output=[{output}]")
            original_file_info = original_file_info.copy()
            original_file_info["_header_path"] = image_dependent_header_file.name

            # Perform actual compression
            cr = super().compress(original_path=corrected_length_file.name,
                             compressed_path=compressed_path,
                             original_file_info=original_file_info)
            cr.original_path = original_path

            if self.output_header_dir is not None:
                header_output_name = "header_" + self.name + os.path.abspath(os.path.realpath(original_path)).replace(
                    os.sep, "_")
                os.makedirs(self.output_header_dir, exist_ok=True)
                shutil.copyfile(image_dependent_header_file.name,
                                os.path.join(self.output_header_dir, header_output_name))

            return cr

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_file_info['_header_path']} " \
               f"{file_info_to_format_string(original_file_info)} " \
               f"{original_path} {compressed_path}"

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        super().decompress(compressed_path=compressed_path,
                           reconstructed_path=reconstructed_path,
                           original_file_info=original_file_info)
        with open(reconstructed_path, "r+") as rf:
            rf.truncate(original_file_info["samples"]
                        * original_file_info["bytes_per_sample"])

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} " \
               f"{file_info_to_format_string(original_file_info)} " \
               f"{reconstructed_path}"


class CCSDS_LCNL(icompression.NearLosslessCodec, icompression.WrapperCodec):
    ENTROPY_SAMPLE_ADAPTIVE, ENTROPY_HYBRID, ENTROPY_BLOCK_ADAPTIVE = range(3)
    default_entropy_codec_type = ENTROPY_HYBRID

    SAMPLE_ORDER_BIQ, SAMPLE_ORDER_BSQ = range(2)
    default_sample_encoding_order = SAMPLE_ORDER_BSQ  # BSQ

    default_large_P = 3
    LOCAL_SUM_WIDE_NEI, LOCAL_SUM_NARROW_NEI, LOCAL_SUM_WIDE_COL, LOCAL_SUM_NARROW_COL = \
        range(4)
    default_local_sum_type = LOCAL_SUM_WIDE_NEI
    PREDICTION_FULL, PREDICTION_REDUCED = range(2)
    default_prediction_mode = PREDICTION_FULL
    FIDELITY_LOSSLESS, FIDELITY_ABSOLUTE, FIDELITY_RELATIVE, FIDELITY_BOTH = range(4)

    default_large_j = 64
    default_r = 4096
    default_large_r = 64

    def __init__(self, bin_dir=None, absolute_error_limit=None, relative_error_limit=None,
                 entropy_coder_type=None, sample_encoding_order=None, large_p=None,
                 local_sum_type=None, prediction_mode=None, large_j=None, r=None,
                 output_header_dir=None):
        # Process params
        param_dict = sortedcontainers.SortedDict()
        param_dict["a_vector"] = absolute_error_limit
        param_dict["r_vector"] = relative_error_limit
        # entropy coder type always present
        entropy_coder_type = entropy_coder_type if entropy_coder_type is not None \
            else self.default_entropy_codec_type
        assert entropy_coder_type in (self.ENTROPY_SAMPLE_ADAPTIVE, self.ENTROPY_HYBRID, self.ENTROPY_BLOCK_ADAPTIVE)
        if entropy_coder_type == self.ENTROPY_BLOCK_ADAPTIVE:
            large_j = large_j if large_j is not None else self.default_large_j
            r = r if r is not None else self.default_r
            param_dict["large_j"] = large_j
            param_dict["r"] = r
        param_dict["entropy_coder_type"] = entropy_coder_type
        # Sample encoding order default is BIQ, which is not how images are stored.
        # Therefore, it should always be store in param_dict
        sample_encoding_order = sample_encoding_order if sample_encoding_order is not None \
            else self.default_sample_encoding_order
        assert sample_encoding_order in (self.SAMPLE_ORDER_BIQ, self.SAMPLE_ORDER_BSQ)
        param_dict["sample_encoding_order"] = sample_encoding_order
        #
        large_p = large_p if large_p is not None else self.default_large_P
        assert 0 <= large_p <= 15
        param_dict["large_p"] = large_p
        #
        local_sum_type = local_sum_type if local_sum_type is not None \
            else self.default_local_sum_type
        assert local_sum_type in (self.LOCAL_SUM_WIDE_NEI, self.LOCAL_SUM_NARROW_NEI,
                                  self.LOCAL_SUM_WIDE_COL, self.LOCAL_SUM_NARROW_COL), local_sum_type
        if local_sum_type != self.default_local_sum_type:
            param_dict["local_sum_type"] = local_sum_type
        #
        prediction_mode = prediction_mode if prediction_mode is not None else self.default_prediction_mode
        if prediction_mode is not None and prediction_mode != self.default_prediction_mode:
            assert prediction_mode in (self.PREDICTION_FULL, self.PREDICTION_REDUCED)
            param_dict["prediction_mode"] = prediction_mode

        # Set binary paths
        bin_dir = bin_dir if bin_dir is not None else options.external_bin_base_dir
        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        assert os.path.isdir(bin_dir), f"Invalid binary dir {bin_dir}."
        lcnl_encoder_path = os.path.join(bin_dir, "lcnl_encoder")
        lcnl_decoder_path = os.path.join(bin_dir, "lcnl_decoder")
        self.lcnl_header_tool_path = os.path.join(bin_dir, "lcnl_header_tool")
        for p in lcnl_encoder_path, lcnl_decoder_path, self.lcnl_header_tool_path:
            assert os.path.isfile(p), f"Binary file {p} does not exist"
            assert os.access(p, os.EX_OK), f"Binary file {p} is not executable"

        # Complete initialization
        icompression.WrapperCodec.__init__(
            self, compressor_path=lcnl_encoder_path, decompressor_path=lcnl_decoder_path,
            param_dict=param_dict)
        self.output_header_dir = output_header_dir

    def get_image_params(self, original_path, original_file_info):
        """Get the dictionary of parameters to use in the -x k=v options of lcnl_header_tool.
        """
        if self.param_dict['a_vector'] is None and self.param_dict['r_vector'] is None:
            quantizer_fidelity_control_method = self.FIDELITY_LOSSLESS
        elif self.param_dict['a_vector'] is not None and self.param_dict['r_vector'] is None:
            quantizer_fidelity_control_method = self.FIDELITY_ABSOLUTE
        elif self.param_dict['a_vector'] is None and self.param_dict['r_vector'] is not None:
            quantizer_fidelity_control_method = self.FIDELITY_RELATIVE
        else:
            quantizer_fidelity_control_method = self.FIDELITY_BOTH

        image_params = dict(self.param_dict)
        if image_params["a_vector"] is None:
            del image_params["a_vector"]
        else:
            image_params["large_d_large_a"] = math.floor(math.log2(int(image_params["a_vector"]))) + 1 \
                if image_params["a_vector"] > 0 else 1
        if image_params["r_vector"] is None:
            del image_params["r_vector"]
        else:
            image_params["large_d_large_r"] = math.floor(math.log2(int(image_params["r_vector"]))) + 1 \
                if image_params["r_vector"] > 0 else 1

        if original_file_info["bytes_per_sample"] == 1:
            large_d = min(8, max(2, original_file_info["dynamic_range_bits"]))
        elif original_file_info["bytes_per_sample"] == 2:
            large_d = max(9, min(16, original_file_info["dynamic_range_bits"]))
        elif original_file_info["bytes_per_sample"] == 4:
            large_d = max(24, min(32, original_file_info["dynamic_range_bits"]))
        else:
            raise ValueError(f"Bytes per sample = {original_file_info['bytes_per_sample']} not supported")

        image_params.update(
            large_n_x=original_file_info["width"],
            large_n_y=original_file_info["height"],
            large_n_z=original_file_info["component_count"],
            sample_type=1 if original_file_info["signed"] else 0,
            large_d=large_d,
            quantizer_fidelity_control_method=quantizer_fidelity_control_method,
            absolute_error_limit_assignment_method=0,  # band independent
            relative_error_limit_assignment_method=0,  # band independent
        )

        return image_params

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        with tempfile.NamedTemporaryFile(
                prefix=f"header_{os.path.basename(original_path)}_") as image_dependent_header_file:
            image_params = self.get_image_params(original_path=original_path, original_file_info=original_file_info)
            header_invocation = f"{self.lcnl_header_tool_path} " + \
                                " ".join(f"-x {k}={v}" for k, v in image_params.items()) + \
                                f" {image_dependent_header_file.name}"
            status, output = subprocess.getstatusoutput(header_invocation)

            if status != 0:
                raise Exception(f"Status = {status} != 0.\n"
                                f"Input=[{header_invocation}].\n"
                                f"Output=[{output}]")
            original_file_info = original_file_info.copy()
            original_file_info["_header_path"] = image_dependent_header_file.name

            cr = super().compress(original_path=original_path,
                             compressed_path=compressed_path,
                             original_file_info=original_file_info)


            if self.output_header_dir is not None:
                header_output_name = "header_" + self.name + os.path.abspath(os.path.realpath(original_path)).replace(
                    os.sep, "_")
                os.makedirs(self.output_header_dir, exist_ok=True)
                shutil.copyfile(image_dependent_header_file.name,
                                os.path.join(self.output_header_dir, header_output_name))

            return cr

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"{original_file_info['_header_path']} " \
               + f"{file_info_to_format_string(original_file_info)} " \
               + f"{original_path} {compressed_path}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"{compressed_path} {file_info_to_format_string(original_file_info)} {reconstructed_path}"

    @property
    def label(self):
        try:
            entropy_coder_type = self.param_dict["entropy_coder_type"]
        except KeyError:
            entropy_coder_type = self.default_entropy_codec_type
        if entropy_coder_type == self.ENTROPY_SAMPLE_ADAPTIVE:
            s = "CCSDS 123.0-B-2 Sample Adaptative"
        elif entropy_coder_type == self.ENTROPY_BLOCK_ADAPTIVE:
            s = "CCSDS 123.0-B-2 Block Adaptative"
        elif entropy_coder_type == self.ENTROPY_HYBRID:
            s = "CCSDS 123.0-B-2 Hybrid"
        else:
            raise ValueError(f"Unexpected entropy coding type {entropy_coder_type}")

        s += f" $a_z={self.param_dict['a_vector']}$" \
            if self.param_dict['a_vector'] is not None else ''
        s += f" $r_z={self.param_dict['r_vector']}$" \
            if self.param_dict['r_vector'] is not None else ''

        return s


class CCSDS_LCNL_GreenBook(CCSDS_LCNL):
    """Wrapper for CCSDS_LCNL that uses the default params specified in
    the Green Book.
    """
    # Green book default constants
    default_large_omega = 19
    default_v_min = -1
    default_log_two_t_inc = 6
    default_sample_representative_flag = 1
    default_large_theta = 3
    default_phi_vector = "7"
    default_large_u_max = 18
    default_gamma_star = 6
    default_gamma_0 = 1

    def __init__(self,
                 bin_dir=None,
                 absolute_error_limit=None,
                 relative_error_limit=None,
                 entropy_coder_type=None,
                 output_header_dir=None):
        super().__init__(bin_dir=bin_dir,
                         absolute_error_limit=absolute_error_limit,
                         relative_error_limit=relative_error_limit,
                         entropy_coder_type=entropy_coder_type,
                         output_header_dir=output_header_dir)

    def get_image_params(self, original_path, original_file_info):
        image_params = super().get_image_params(
            original_path=original_path, original_file_info=original_file_info)
        # Add default params if not already present
        for var_name, default_value in [("large_r", self.default_large_r),
                                        ("large_omega", self.default_large_omega),
                                        ("v_min", self.default_v_min),
                                        ("log_two_t_inc", self.default_log_two_t_inc),
                                        ("large_theta", self.default_large_theta),
                                        ("sample_representative_flag", self.default_sample_representative_flag),
                                        ("phi_vector", self.default_phi_vector),
                                        ("large_u_max", self.default_large_u_max),
                                        ("gamma_star", self.default_gamma_star),
                                        ("gamma_0", self.default_gamma_0)]:
            if var_name not in image_params or image_params[var_name] is None:
                image_params[var_name] = default_value

        if any(n in os.path.abspath(os.path.realpath(original_path)).replace(os.sep, "/").lower()
               for n in ("/crism/", "/hyperion/", "/m3/", "/modis/",
                         "SFSI_mantar_Rad_rmnoise-s16be-240x140x452.raw".lower())):
            image_params["local_sum_type"] = self.LOCAL_SUM_WIDE_COL
        else:
            image_params["local_sum_type"] = self.LOCAL_SUM_WIDE_NEI

        if any(n in os.path.abspath(os.path.realpath(original_path)).replace(os.sep, "/").lower()
               for n in ("/airs/",
                         "f011020t01p03r05_sc01.uncal-u16be-224x512x614",
                         "t0477f06-raw-u16be-72x1225x406",
                         "/crism/", "/hyperion/", "/iasi/", "/m3/",
                         "MOD01.A2001222.1200day-nuc-u16be-14x2030x1354.raw".lower(),
                         "MOD01.A2001222.1200day-u16be-14x2030x1354.raw".lower(),
                         "MOD01.A2001222.1200night-u16be-17x2030x1354.raw".lower())):
            image_params["prediction_mode"] = self.PREDICTION_REDUCED
        else:
            image_params["prediction_mode"] = self.PREDICTION_FULL

        if any(n in os.path.abspath(os.path.realpath(original_path)).replace(os.sep, "/").lower()
               for n in ("f060925t01p00r12_sc00.c.img-s16be-224x512x677.raw".lower(),
                         "/sfsi/")):
            image_params["phi_vector"] = 5
        elif any(n in os.path.abspath(os.path.realpath(original_path)).replace(os.sep, "/").lower()
                 for n in ("/airs/", "/aviris/", "/casi/", "/crism/", "/hyperion/",
                           "M3targetB-nuc-u16be-260x512x640.raw".lower(),
                           "M3targetB-u16be-260x512x640.raw".lower())):
            image_params["phi_vector"] = 3
        else:
            image_params["phi_vector"] = 0
        image_params["v_max"] = 7 - image_params["phi_vector"]

        # Use user-defined parameters if present
        for param in ("phi_vector", "psi_vector", "large_theta", "v_max"):
            try:
                image_params[param] = self.param_dict[param]
            except KeyError:
                pass

        return image_params


class CCSDS_LCNL_AdjustedGreenBook(CCSDS_LCNL_GreenBook):
    def get_image_params(self, original_path, original_file_info):
        if any(name in original_path.lower() for name in ("/modis/", "/spot5/", "/hyperion/", "/iasi/")):
            return CCSDS_LCNL.get_image_params(self, original_path=original_path, original_file_info=original_file_info)
        else:
            return super().get_image_params(original_path=original_path, original_file_info=original_file_info)


def file_info_to_format_string(file_info):
    format_string = "s" if file_info["signed"] else "u"
    format_string += str(8 * file_info["bytes_per_sample"])
    format_string += "be" if file_info["big_endian"] else "le"
    return format_string
