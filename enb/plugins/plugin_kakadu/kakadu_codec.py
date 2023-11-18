#!/usr/bin/env python3
"""
Wrappers for the Kakadu codec.
For instructions on downloading and installing visit:
https://github.com/miguelinux314/experiment-notebook/blob/master/enb/plugins/plugin_kakadu/README.md
"""
__author__ = "Natalia Blasco, Ester Jara, Artemis Llabrés and Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import math
import numpy as np
import os
import tempfile
import enb
from enb import icompression
from enb import isets


class Kakadu2D(icompression.WrapperCodec, icompression.LosslessCodec, icompression.LossyCodec):
    """Kakadu JPEG 2000 wrapper that applies the 5/3 IWT or the 9/7 DWT (spatially) when lossless is True or False,
    respectively. No spectral decorrelation is applied, unless the apply_ycc flag is selected.

    Note that subclasses may overwrite the get_atk_params method to configure specific spatial transforms.
    """
    # When searching for exact PSNR values, this error is tolerated
    psnr_tolerance = 1e-3
    max_search_iterations = 32

    def __init__(self, ht=False, spatial_dwt_levels=5,
                 lossless=None, bit_rate=None, quality_factor=None, psnr=None,
                 apply_ycc=False, num_threads=0):
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
            :param num_threads: number of threads with which kakadu is to be run. 0 means single thread.
        """
        assert isinstance(ht, bool), "HT must be a boolean (True/False)"
        assert spatial_dwt_levels in range(0, 34), \
            f"Invalud number of spatial DWT levels {spatial_dwt_levels}"

        lossless = lossless if lossless is not None else (
                bit_rate is None and quality_factor is None and psnr is None)
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

        assert num_threads == int(num_threads), f"Invalid number of threads {num_threads}"
        assert num_threads >= 0, f"Invalid number of threads {num_threads}"

        param_dict = dict(
            ht=ht,
            spatial_dwt_levels=spatial_dwt_levels,
            lossless=lossless,
            bit_rate=bit_rate,
            quality_factor=quality_factor,
            psnr=psnr,
            num_threads=num_threads)
        if apply_ycc:
            param_dict["apply_ycc"] = True
        icompression.WrapperCodec.__init__(
            self,
            compressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "kdu_compress"),
            decompressor_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "kdu_expand"),
            param_dict=param_dict)

    def get_atk_params(self, original_file_info):
        """Get the ATK parameters that allow customization of the spatial 2D DWT applied to the data.
        If this method returns an empty string, then the default type of DWT is applied
        (e.g., the reversible 5/3 IWT for lossless compression, or the irreversible 9/7 CDF for lossy compression.
        Note that the Creversible=yes or Creversible=no is already provided by self.get_compression_params()
        """
        return ""

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        if self.param_dict["num_threads"] > 1 and not enb.config.options.report_wall_time:
            enb.logger.warn("Careful! Measuring kakadu's process CPU time with multiple threads. "
                            "Add `options.report_wall_time = True` to your script or "
                            "invoke it with --report_wall_time to enable wall clock time measurements.")
        if original_file_info["float"]:
            raise ValueError("This enb codec does not support floating point data. "
                             "Please refer to the kakadu documentation "
                             "and perform manual compression")

        precision_bits = original_file_info['bytes_per_sample'] * 8

        return f"-i {original_path}*{original_file_info['component_count']}" \
               f"@{original_file_info['width'] * original_file_info['height'] * original_file_info['bytes_per_sample']} " \
               f"-o {compressed_path} -no_info -full -no_weights " \
               f"-num_threads {self.param_dict['num_threads']} " \
               f"Corder=LRCP " \
               f"Clevels={self.param_dict['spatial_dwt_levels']} " \
               f"Clayers={original_file_info['component_count']} " \
               f"Creversible={'yes' if self.param_dict['lossless'] else 'no'} " \
               f"{self.get_atk_params(original_file_info=original_file_info)} " \
               f"Cycc={'yes' if 'apply_ycc' in self.param_dict and self.param_dict['apply_ycc'] else 'no'} " \
               f"Sdims=\\{{{original_file_info['height']},{original_file_info['width']}\\}} " \
               f"Nprecision={precision_bits} " \
               f"Sprecision={precision_bits} " \
               f"Nsigned={'yes' if original_file_info['signed'] else 'no'} " \
               f"Ssigned={'yes' if original_file_info['signed'] else 'no'} " \
            + (f"Qstep=0.000000001 " if self.param_dict['bit_rate'] is not None else "") \
            + f"{'Cmodes=HT' if self.param_dict['ht'] else ''} " \
              f"{'-rate ' + str(self.param_dict['bit_rate'] * original_file_info['component_count']) if self.param_dict['bit_rate'] else ''}" \
              f"{'Qfactor=' + str(self.param_dict['quality_factor']) if self.param_dict['quality_factor'] else ''}"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-i {compressed_path} -o {reconstructed_path} -raw_components " \
               f"-num_threads {self.param_dict['num_threads']}"

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
                    actual_bps = 8 * os.path.getsize(compressed_path) / original_file_info[
                        "samples"]

                    mse = np.average(((original_array - reconstructed_array) ** 2))
                    psnr = 10 * math.log10((max_error ** 2) / mse) if mse > 0 else float("inf")
                    if self.param_dict['psnr'] > psnr:
                        br_a = min(self.param_dict['bit_rate'], actual_bps)
                    else:
                        br_b = max(self.param_dict['bit_rate'], actual_bps)

                    psnr_error = abs(self.param_dict['psnr'] - psnr)

        else:
            compression_results = icompression.WrapperCodec.compress(
                self, original_path, compressed_path, original_file_info=original_file_info)

        return compression_results

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        tmp_file_list = []
        for i in range(0, original_file_info['component_count']):
            tmp_file_list.append(tempfile.NamedTemporaryFile(
                dir=enb.config.options.base_tmp_dir, suffix=".raw", delete=True))
        output_path_str = ",".join(tmp_file.name for tmp_file in tmp_file_list)

        decompression_results = icompression.WrapperCodec.decompress(
            self, compressed_path, reconstructed_path=output_path_str,
            original_file_info=original_file_info)

        with open(reconstructed_path, "wb") as output_file:
            for tmp_file in tmp_file_list:
                with open(tmp_file.name, "rb") as component_file:
                    output_file.write(component_file.read())
        decompression_results.reconstructed_path = reconstructed_path

        for tmp_file in tmp_file_list:
            tmp_file.close()

        return decompression_results

    @property
    def label(self):
        rate_str = "" if not self.param_dict["bit_rate"] else f" R = {self.param_dict['bit_rate']}"
        psnr_str = "" if not self.param_dict["psnr"] else f" PSNR {self.param_dict['psnr']}"
        ycc_str = "" if "apply_ycc" not in self.param_dict or not self.param_dict[
            "apply_ycc"] else " YCC"
        return f"Kakadu {'HT' if self.param_dict['ht'] else ''}" \
               f"{'lossless' if self.param_dict['lossless'] else 'lossy'}{rate_str}{psnr_str}{ycc_str}"


class Kakadu2DHaar(Kakadu2D, icompression.LosslessCodec):
    """Kakadu JPEG 2000 wrapper that applies the spatial reversible or irreversible
    Haar transform when lossless is True or False,
    respectively. No spectral decorrelation is applied, unless the apply_ycc flag is selected.
    """

    def get_atk_params(self, original_file_info):
        return f"Catk=3 Kkernels:I3={'R' if self.param_dict['lossless'] else 'I'}2X2"

    @property
    def label(self):
        return f"{super().label} Haar"


class Kakadu2D97M(Kakadu2D, icompression.LosslessCodec):
    """Kakadu JPEG 2000 wrapper that applies the reversible 9/7-M DWT in the spatial 2D transform.
    """

    def get_atk_params(self, original_file_info):
        """Get the ATK filter for the reversible 9/7-M.
        """
        if not self.param_dict["lossless"]:
            enb.logger.warn(f"Warning: using {self.__class__.__name__} with lossy mode")
        return " Catk=7 " \
               " Ksteps:I7=\\{4,-1,4,7\\},\\{2,-1,1,1\\} " \
               " Kcoeffs:I7=0.0625,-0.5625,-0.5625,0.0625,0.25,0.25 " \
               " Kreversible:I7=yes " \
               " Ksymmetric:I7=yes "

    @property
    def label(self):
        return f"{super().label} 9/7-M"


class KakaduMCT(Kakadu2D):
    """Kakadu JPEG 2000 wrapper that applies the reversible 5/3 IWT or the irreversible 9/7 DWT
    (both spatially and spectrally) when lossless is True or False, respectively.
    """

    def __init__(self, ht=False, spatial_dwt_levels=5, spectral_dwt_levels=5, lossless=None,
                 bit_rate=None, quality_factor=None, psnr=None, mct_offset=0,
                 num_threads=0):
        """
        :param spectral_dwt_levels: number of spectral discrete wavelet transform levels. Must be between 0 and 32.
        :param mct_offset: integer offset subtracted from the input samples before compression.
          For unsigned data, the average pixel value or half the maximum pixel value are often good choices.
          For signed data, 0 or the average pixel value are often good choices.
        """
        assert 0 <= spectral_dwt_levels <= 32, f"Invalid number of spectral levels"
        assert mct_offset == int(mct_offset)
        Kakadu2D.__init__(self, ht=ht, spatial_dwt_levels=spatial_dwt_levels, lossless=lossless,
                          bit_rate=bit_rate, quality_factor=quality_factor, psnr=psnr,
                          num_threads=num_threads)
        self.param_dict["spectral_dwt_levels"] = spectral_dwt_levels
        self.param_dict["mct_offset"] = mct_offset

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
            f"Mvector_coeffs:I4={self.param_dict['mct_offset']} Mnum_stages=1 Mstages=1"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"-i {compressed_path} -o {reconstructed_path} -raw_components "

    @property
    def label(self):
        return super().label.replace("Kakadu", "Kakadu MCT")
