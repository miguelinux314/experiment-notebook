#!/usr/bin/env python3
"""Codec wrapper for the SPECK codec.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2022/04/08"

import os
import enb.icompression


class SPECK(enb.icompression.LosslessCodec,
            enb.icompression.LossyCodec,
            enb.icompression.JavaWrapperCodec,
            enb.icompression.GiciLibHelper):
    """Wrapper for the SPECK codec.
    """

    def __init__(self,
                 compressor_jar=os.path.join(os.path.dirname(__file__), "SpeckCode.jar"),
                 decompressor_jar=os.path.join(os.path.dirname(__file__), "SpeckDecode.jar"),
                 wavelet_type="1", wavelet_levels=5):
        """
        :param wavelet_type:     Discrete wavelet transform type for each image component.
            First value is for the first component, second value for the second component and so on.
            If only one value is specified, wavelet transform type will be the same for all components.
            Valid values are:
                 0 -  No wavelet transform
                 1 - Integer (Reversible) 5/3 DWT
                 2 - Real Isorange (irreversible) 9/7 DWT
                 3 - Real Isonorm (irreversible) 9/7 DWT
                 4 - Integer (Reversible) 9/7M DWT (CCSDS-Recommended)
                 5 - Integer 5/3 DWT (classic construction)
                 6 - Integer 9/7 DWT (classic construction)
                 7 - Haar Transform
                 8 - Reversible-Haar Transform
        :param wavelet_levels: number of wavelet levels to be applied.
        """
        super().__init__(compressor_jar=compressor_jar,
                         decompressor_jar=decompressor_jar,
                         param_dict=dict(wavelet_type=wavelet_type,
                                         wavelet_levels=wavelet_levels))

    @property
    def label(self):
        return "SPECK"

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        assert original_file_info["component_count"] == 1, \
            f"Only images with 1 component are currently supported by {self.__class__.__name__}"
        assert original_file_info["big_endian"], \
            f"Only big-endian samples are currently supported by {self.__class__.__name__}"
        assert original_file_info["bytes_per_sample"] in [1, 2], \
            f"Only 8-bit and 16-bit samples are currently supported by {self.__class__.__name__}"
        
        return f"-Xmx256g -jar {self.compressor_jar} -i {original_path} -f {compressed_path} " \
               f"-g {self.get_gici_geometry_str(original_file_info=original_file_info)} " \
               f"-w {self.param_dict['wavelet_type']} -wl {self.param_dict['wavelet_levels']}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        assert original_file_info["component_count"] == 1, f"Only images with 1 component are currently supported."
        
        return f"-Xmx256g -jar {self.decompressor_jar} " \
               f"-f {compressed_path} -o {reconstructed_path} " \
               f"-g {self.get_gici_geometry_str(original_file_info=original_file_info)} " \
               f"-w {self.param_dict['wavelet_type']} -wl {self.param_dict['wavelet_levels']}"
