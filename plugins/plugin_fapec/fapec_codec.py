#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrappers for the FAPEC codec.

2020/09/07: added support for the CILLIC algorithm
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "25/05/2020"

import os

from enb import icompression
from enb.config import get_options

options = get_options()


class FAPEC_Abstract(icompression.LossyCodec, icompression.LosslessCodec, icompression.WrapperCodec):
    """Base class for FAPEC coders
    """
    BAND_FORMAT_BIP, BAND_FORMAT_BIL, BAND_FORMAT_BSQ, BAND_FORMAT_BAYER = range(4)
    default_band_format = BAND_FORMAT_BSQ

    def __init__(self, bin_dir=None, chunk_size_str="128M", threads=1,
                 lsb_discard_count=0,
                 adaptiveness_block_length=128,
                 output_invocation_dir=None):
        """
        :param bin_dir: path to the dir with the fapec and unfapec binaries
        :param chunk_size_str: string to be passed in the -chunk argument
        :param threads: number of threads to use for compression/decompression
        :param output_invocation_dir
        """
        param_dict = dict()
        param_dict["chunk"] = chunk_size_str
        assert lsb_discard_count >= 0
        if lsb_discard_count > 0:
            param_dict["lossy"] = lsb_discard_count
        assert threads >= 0
        param_dict["mt"] = threads
        assert 32 <= adaptiveness_block_length <= 1024
        param_dict["bl"] = adaptiveness_block_length

        bin_dir = bin_dir if bin_dir is not None else os.path.dirname(__file__)
        super().__init__(compressor_path=os.path.join(bin_dir, "fapec"),
                         decompressor_path=os.path.join(bin_dir, "unfapec"),
                         param_dict=param_dict, output_invocation_dir=output_invocation_dir)

    def get_transform_dict_params(self, original_file_info):
        raise NotImplementedError("Please select one of the subclasses")

    def get_dtype(self, original_file_info):
        return 8 * original_file_info["bytes_per_sample"]

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        invocation_params = dict(self.param_dict)
        invocation_params.update(
            hd=0, chd=0,
            dtype=self.get_dtype(original_file_info=original_file_info))
        invocation_params.update(self.get_transform_dict_params(original_file_info=original_file_info))
        invocation = " ".join(f"-{k} {v}" for k, v in invocation_params.items())
        if original_file_info["signed"]:
            invocation += " -signed"
        if original_file_info["big_endian"]:
            invocation += " -be"
        invocation += " -ow -noattr "
        invocation += f"-o {compressed_path} {original_path}"
        return invocation

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        invocation = f"-o {reconstructed_path} -ow {compressed_path}"
        return invocation


class FAPEC_NP(FAPEC_Abstract):
    """Wrapper for FAPEC with no preprocessing (-np option).
    """

    def get_transform_dict_params(self, original_file_info):
        return dict(np=("tc" if original_file_info["signed"] else "us"))

    @property
    def label(self):
        return "FAPEC-NP"

class FAPEC_SPA(FAPEC_Abstract):
    """Wrapper for FAPEC with only spatial decorrelation (Delta)
    """

    def get_transform_dict_params(self, original_file_info):
        return dict()

    @property
    def label(self):
        return "FAPEC-SPA"

class FAPEC_MB(FAPEC_Abstract):
    """Wrapper for FAPEC with no preprocessing (-np option).
    """

    def get_transform_dict_params(self, original_file_info):
        return dict(bands=original_file_info["component_count"])

    @property
    def label(self):
        return "FAPEC-MB"


class FAPEC_LP(FAPEC_Abstract):
    """Wrapper for FAPEC with "spatial" lineal prediction (-lp flag)
    """

    def __init__(self, linear_prediction_order=1,
                 bin_dir=None, chunk_size_str="128M", threads=1,
                 lsb_discard_count=0,
                 adaptiveness_block_length=128,
                 output_invocation_dir=None):
        super().__init__(bin_dir=bin_dir, chunk_size_str=chunk_size_str,
                         threads=threads, lsb_discard_count=lsb_discard_count,
                         adaptiveness_block_length=adaptiveness_block_length,
                         output_invocation_dir=output_invocation_dir)
        assert linear_prediction_order >= 0
        assert linear_prediction_order == int(linear_prediction_order)
        self.linear_prediction_order = linear_prediction_order

    linear_prediction_oder = 1

    def get_transform_dict_params(self, original_file_info):
        assert self.linear_prediction_oder >= 1
        if self.linear_prediction_order == 1:
            return dict()
        else:
            return dict(od=self.linear_prediction_oder)

    @property
    def name(self):
        return super().name + (f"_od={self.linear_prediction_order}" if self.linear_prediction_order > 1 else "")

    @property
    def label(self):
        return "FAPEC-LP"


class FAPEC_DWT(FAPEC_Abstract):
    """Run FAPEC with the spectral+spatial IWT (-dwt flag).
    """
    def __init__(self, dwt_losses=0,
                 bin_dir=None, chunk_size_str="128M", threads=1,
                 lsb_discard_count=0,
                 adaptiveness_block_length=128,
                 output_invocation_dir=None):
        super().__init__(bin_dir=bin_dir, chunk_size_str=chunk_size_str,
                         threads=threads, lsb_discard_count=lsb_discard_count,
                         adaptiveness_block_length=adaptiveness_block_length,
                         output_invocation_dir=output_invocation_dir)
        self.dwt_losses = dwt_losses
        assert self.dwt_losses >= 0

    @property
    def name(self):
        return super().name + f"_dwt_losses={self.dwt_losses}"

    @property
    def label(self):
        return f"FAPEC-IWT"

    def get_transform_dict_params(self, original_file_info):
        return dict(dwt=f"{original_file_info['width']} "
                        f"{original_file_info['height']} "
                        f"{original_file_info['component_count']} "
                        f"{self.dwt_losses} "
                        f"{original_file_info['dynamic_range_bits']} "
                        f"{2}") # <bfmt>    Bands format: 0=BIP, 1=BIL, 2=BSQ, 3=Bayer

class FAPEC_CILLIC(FAPEC_Abstract):
    """Run fapec with the CILLIC option.
    """
    def __init__(self, losses=0, multiband_levels=6,
                 bin_dir=None, chunk_size_str="128M", threads=1,
                 lsb_discard_count=0,
                 adaptiveness_block_length=128,
                 output_invocation_dir=None):
        super().__init__(bin_dir=bin_dir, chunk_size_str=chunk_size_str,
                         threads=threads, lsb_discard_count=lsb_discard_count,
                         adaptiveness_block_length=adaptiveness_block_length,
                         output_invocation_dir=output_invocation_dir)
        self.losses = losses
        self.multiband_levels = multiband_levels
        assert self.losses >= 0

    @property
    def name(self):
        return super().name + f"_losses={self.losses}_lev={self.multiband_levels}"

    @property
    def label(self):
        return f"FAPEC-CILLIC"

    def get_transform_dict_params(self, original_file_info):
        return dict(cillic=f"{original_file_info['width']} "
                        f"{original_file_info['height']} "
                        f"{original_file_info['component_count']} "
                        f"{self.losses} "
                        f"{original_file_info['dynamic_range_bits']} "
                        f"{2}", # <bfmt>    Bands format: 0=BIP, 1=BIL, 2=BSQ, 3=Bayer
                    lev=self.multiband_levels)


class FAPEC_2DDWT(FAPEC_DWT):
    """Run FAPEC with a single spatial DWT transform, by forcing dymensions
    to be z'=1, x'=x, y'=y*z.
    """

    @property
    def name(self):
        return super().name + f"_dwt_losses={self.dwt_losses}"

    @property
    def label(self):
        return f"FAPEC-2DIWT"

    def get_transform_dict_params(self, original_file_info):

        dimension_str = f"{original_file_info['width']} " \
                        f"{original_file_info['height'] * original_file_info['component_count']} " \
                        f"1 "

        if original_file_info["component_count"] < 8461:
            return dict(dwt=f"{dimension_str} "
                            f"{self.dwt_losses} "
                            f"{original_file_info['dynamic_range_bits']} "
                            f"{2}")  # <bfmt>    Bands format: 0=BIP, 1=BIL, 2=BSQ, 3=Bayer
        else:
            # IASI crashes otherwise
            return dict()



class FAPEC_HPA(FAPEC_Abstract):
    def __init__(self, hpa_losses=0,
                 bin_dir=None, chunk_size_str="128M", threads=1,
                 lsb_discard_count=0,
                 adaptiveness_block_length=128,
                 output_invocation_dir=None):
        super().__init__(bin_dir=bin_dir, chunk_size_str=chunk_size_str,
                         threads=threads, lsb_discard_count=lsb_discard_count,
                         adaptiveness_block_length=adaptiveness_block_length,
                         output_invocation_dir=output_invocation_dir)
        self.hpa_losses = hpa_losses
        assert 0 <= self.hpa_losses <= 16

    @property
    def name(self):
        return super().name + f"_hpa_losses={self.hpa_losses}"

    @property
    def label(self):
        return f"FAPEC-HPA"

    def get_transform_dict_params(self, original_file_info):
        return dict(hpa=f"{original_file_info['width']} "
                        f"{original_file_info['height']} "
                        f"{original_file_info['component_count']} "
                        f"{self.hpa_losses} "
                        f"{original_file_info['dynamic_range_bits']} "
                        f"{2}") # <bfmt>    Bands format: 0=BIP, 1=BIL, 2=BSQ, 3=Bayer