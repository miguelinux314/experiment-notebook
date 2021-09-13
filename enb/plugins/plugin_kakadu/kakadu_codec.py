#!/usr/bin/env python3
"""
Wrappers for the Kakadu codec.
For instructions on downloading and installing visit:
https://github.com/miguelinux314/experiment-notebook/blob/master/enb/pluginsplugin_kakadu/README.md
"""
__author__ = "Natalia Blasco, Ester Jara, Artur Llabrés and Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import math
import numpy as np
import os
import tempfile
from enb import icompression
from enb import isets


class Kakadu2D(icompression.WrapperCodec, icompression.LosslessCodec, icompression.LossyCodec):
    # When searching for exact PSNR values, this error is tolerated
    psnr_tolerance = 1e-3
    max_search_iterations = 32

    def __init__(self, ht=False, spatial_dwt_levels=5,
                 lossless=None, bit_rate=None, quality_factor=None, psnr=None):
        """Kakadu wrapper that does not apply decorrelation across bands, even if more than one is present.

            :param ht: if True, the high-throughput version of the Kakadu codec is used
            :param spatial_dwt_levels: number of spatial discrete wavelet transform levels.
              Must be between 0 and 33.
            :param lossless: if True, the compression will be lossless, and bit_rate, quality_factor or
              psnr can not be
              used. If None, a lossless compression will be performed, unless
              bit_rate/quality_factor/psnr are set,
              in which case lossless will be set to False and the compression will be lossy.
            :param bit_rate: target bits per sample for each component of the image. If bit_rate is set,
              then lossless must be None or False.
            :param quality_factor: target quality factor for a lossy compression.
              If quality_factor is set then lossless
              must be None or False. Must be between 0 and 100.
            :param psnr: target peak signal-to-noise ratio for a lossy compression.
              A binary search is performed to find which quality factor will result in the
              indicated PSNR with the tolerance given by self.psnr_tolerance.
              If psnr is set then lossless must be None or False.
        """
        assert isinstance(ht, bool), "HT must be a boolean (True/False)"
        assert spatial_dwt_levels in range(0, 34), \
            f"Invalud number of spatial DWT levels {spatial_dwt_levels}"

        lossless = lossless if lossless is not None else (bit_rate is None and quality_factor is None and psnr is None)
        if lossless:
            assert all(v is None for v in [bit_rate, quality_factor, psnr]), \
                f"Cannot set bitrate, quality factor or PSNR when lossless is requested."
        else:
            assert sum(1 for v in (bit_rate, quality_factor, psnr) if v is not None) <= 1, \
                f"Only one of bitrate, quality factor and PSNR can be set at a time."
            if bit_rate is not None:
                assert bit_rate > 0, f"Invalid bit rate {bit_rate}"
            if quality_factor is not None:
                assert 0 < quality_factor <= 100, f"Invalid quality factor {quality_factor}"
            if psnr is not None:
                assert psnr > 0, f"Invalid psnr {psnr}"
            lossless = False

        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "kdu_compress"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "kdu_expand"),
            param_dict=dict(
                ht=ht,
                spatial_dwt_levels=spatial_dwt_levels,
                lossless=lossless,
                bit_rate=bit_rate,
                quality_factor=quality_factor,
                psnr=psnr))

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"-i {original_path}*{original_file_info['component_count']}" \
               f"@{original_file_info['width'] * original_file_info['height'] * original_file_info['bytes_per_sample']} " \
               f"-o {compressed_path} -no_info -full -no_weights " \
               f"Corder=LRCP " \
               f"Clevels={self.param_dict['spatial_dwt_levels']} " \
               f"Clayers={original_file_info['component_count']} " \
               f"Creversible={'yes' if self.param_dict['lossless'] else 'no'} " \
               f"Cycc=no " \
               f"Sdims=\\{{{original_file_info['width']},{original_file_info['height']}\\}} " \
               f"Nprecision={original_file_info['bytes_per_sample'] * 8} " \
               f"Sprecision={original_file_info['bytes_per_sample'] * 8} " \
               f"Nsigned={'yes' if original_file_info['signed'] else 'no'} " \
               f"Ssigned={'yes' if original_file_info['signed'] else 'no'} " \
               + (f"Qstep=0.000000001 " if self.param_dict['bit_rate'] is not None else "") \
               + f"{'Cmodes=HT' if self.param_dict['ht'] else ''} " \
                 f"{'-rate ' + str(self.param_dict['bit_rate'] * original_file_info['component_count']) if self.param_dict['bit_rate'] else ''}" \
                 f"{'Qfactor=' + str(self.param_dict['quality_factor']) if self.param_dict['quality_factor'] else ''}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-i {compressed_path} -o {reconstructed_path} -raw_components"

    def compress(self, original_path, compressed_path, original_file_info=None):
        if self.param_dict['psnr'] is not None:
            with tempfile.NamedTemporaryFile() as tmp_file:
                br_a = 0
                br_b = 32
                iteration = 0

                psnr_error = float("inf")
                while psnr_error > self.psnr_tolerance and iteration <= self.max_search_iterations:
                    iteration += 1
                    self.param_dict['bit_rate'] = (br_b + br_a) / 2
                    compression_results = icompression.WrapperCodec.compress(
                        self, original_path, compressed_path, original_file_info=original_file_info)
                    self.decompress(
                        compressed_path,
                        reconstructed_path=tmp_file.name,
                        original_file_info=original_file_info)

                    max_error = (2 ** (8 * original_file_info["bytes_per_sample"])) - 1
                    dtype = isets.iproperties_row_to_numpy_dtype(original_file_info)
                    original_array = np.fromfile(original_path, dtype=dtype).astype(np.int64)
                    reconstructed_array = np.fromfile(tmp_file.name, dtype=dtype).astype(np.int64)
                    actual_bps = 8 * os.path.getsize(compressed_path) / original_file_info["samples"]

                    mse = np.average(((original_array - reconstructed_array) ** 2))
                    psnr = 10 * math.log10((max_error ** 2) / mse) if mse > 0 else float("inf")
                    if self.param_dict['psnr'] > psnr:
                        br_a = min(self.param_dict['bit_rate'], actual_bps)
                    else:
                        br_b = max(self.param_dict['bit_rate'], actual_bps)

                    psnr_error = abs(self.param_dict['psnr'] - psnr)

                    # print(f"[watch] iteration={iteration}")
                    # print(f"[watch] mse={mse}")
                    # print(f"[watch] psnr={psnr}")
                    #
                    # print(f"[watch] br_a={br_a}")
                    # print(f"[watch] br_b={br_b}")
                    # print(f"[watch] actual_bps={actual_bps}")
                    # print(f"[watch] self.param_dict['bit_rate'] - actual_bps={self.param_dict['bit_rate'] - actual_bps}")
                    # print()
                print(f"[watch] psnr_error={psnr_error}")




        else:
            compression_results = icompression.WrapperCodec.compress(
                self, original_path, compressed_path, original_file_info=original_file_info)

        return compression_results

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        temp_list = []
        temp_path = f""
        for i in range(0, original_file_info['component_count']):
            temp_list.append(tempfile.NamedTemporaryFile(suffix=".raw").name)
            if i < (original_file_info['component_count'] - 1):
                temp_path += f"{temp_list[i]},"
            else:
                temp_path += f"{temp_list[i]}"

        decompression_results = icompression.WrapperCodec.decompress(
            self, compressed_path, reconstructed_path=temp_path, original_file_info=original_file_info)

        with open(reconstructed_path, "wb") as output_file:
            for p in temp_path.split(","):
                with open(p, "rb") as component_file:
                    output_file.write(component_file.read())
        decompression_results.reconstructed_path = reconstructed_path
        return decompression_results

    @property
    def label(self):
        return f"Kakadu {'HT' if self.param_dict['ht'] else ''}" \
               f"{'lossless' if self.param_dict['lossless'] else 'lossy'}"


class KakaduMCT(Kakadu2D):
    def __init__(self, ht=False, spatial_dwt_levels=5, spectral_dwt_levels=5, lossless=None,
                 bit_rate=None, quality_factor=None, psnr=None):
        """
        :param spectral_dwt_levels: number of spectral discrete wavelet transform levels. Must be between 0 and 32.
        """
        assert 0 <= spectral_dwt_levels <= 32, f"Invalid number of spectral levels"
        Kakadu2D.__init__(self, ht=ht, spatial_dwt_levels=spatial_dwt_levels, lossless=lossless,
                          bit_rate=bit_rate, quality_factor=quality_factor, psnr=psnr)
        self.param_dict["spectral_dwt_levels"] = spectral_dwt_levels

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return Kakadu2D.get_compression_params(
            self,
            original_path=original_path,
            compressed_path=compressed_path,
            original_file_info=original_file_info) + \
               f" Mcomponents={original_file_info['component_count']} " \
               f"Mstage_inputs:I1=\\{{0,{original_file_info['component_count'] - 1}\\}} " \
               f"Mstage_outputs:I1=\\{{0,{original_file_info['component_count'] - 1}\\}} " \
               f"Mstage_collections:I1=\\{{{original_file_info['component_count']},{original_file_info['component_count']}\\}} " \
               f"Mstage_xforms:I1=\\{{DWT," \
               + ('1' if self.param_dict['lossless'] else '0') + \
               f",4,0,{self.param_dict['spectral_dwt_levels']}\\}} " \
               f"Mvector_size:I4={original_file_info['component_count']} " \
               f"Mvector_coeffs:I4=0 Mnum_stages=1 Mstages=1"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-i {compressed_path} -o {reconstructed_path} -raw_components "

    @property
    def label(self):
        return super().label.replace("Kakadu", "Kakadu MCT")
