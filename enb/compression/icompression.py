#!/usr/bin/env python3
"""Image compression experiment module.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/04/01"

import os
import re
import filecmp
import hashlib
import tempfile
import time
import collections
import functools
import shutil
import math
import numpy as np
from scipy import signal
from scipy.ndimage.filters import convolve

from enb.atable import ColumnProperties, column_function, indices_to_internal_loc
from enb.isets import load_array_bsq, dump_array_bsq

# These * imports provide backwards import compatibility for versions < v1.1.0,
# but enb.compression.* is preferred since v1.1.0.
from enb.compression import * 
from enb.compression.codec import *
from enb.compression.wrapper import *


class LossyCompressionExperiment(CompressionExperiment):
    """Lossy compression of raw image files.
    """

    @column_function("mse", label="MSE", plot_min=0)
    def set_MSE(self, index, row):
        """Set the mean squared error of the reconstructed image.
        """
        original_array = np.fromfile(
            self.codec_results.compression_results.original_path,
            dtype=self.codec_results.numpy_dtype).astype(np.int64)

        reconstructed_array = np.fromfile(
            self.codec_results.decompression_results.reconstructed_path,
            dtype=self.codec_results.numpy_dtype).astype(np.int64)
        row[_column_name] = np.average(
            ((original_array - reconstructed_array) ** 2))

    @column_function("pae", label="PAE", plot_min=0)
    def set_PAE(self, index, row):
        """Set the peak absolute error (maximum absolute pixelwise
        difference) of the reconstructed image.
        """
        original_array = np.fromfile(
            self.codec_results.compression_results.original_path,
            dtype=self.codec_results.numpy_dtype).astype(np.int64)

        reconstructed_array = np.fromfile(
            self.codec_results.decompression_results.reconstructed_path,
            dtype=self.codec_results.numpy_dtype).astype(np.int64)
        row[_column_name] = np.max(np.abs(original_array - reconstructed_array))

    @column_function("psnr_bps", label="PSNR (dB)", plot_min=0)
    def set_PSNR_nominal(self, index, row):
        """Set the PSNR assuming nominal dynamic range given by
        bytes_per_sample.
        """
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[indices_to_internal_loc(file_path)]
        if row.image_info_row["float"]:
            row[_column_name] = float("inf")
        else:
            max_error = (2 ** (8 * row.image_info_row["bytes_per_sample"])) - 1
            row[_column_name] = (
                    20 * math.log10((max_error) / math.sqrt(row["mse"]))) \
                if row["mse"] > 0 else float("inf")

    @column_function("psnr_dr", label="PSNR (dB)", plot_min=0)
    def set_PSNR_dynamic_range(self, index, row):
        """Set the PSNR assuming dynamic range given by dynamic_range_bits.
        """
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            indices_to_internal_loc(file_path)]
        max_error = (2 ** row.image_info_row["dynamic_range_bits"]) - 1
        row[_column_name] = 20 * math.log10(max_error / math.sqrt(row["mse"])) \
            if row["mse"] > 0 else float("inf")


class StructuralSimilarity(CompressionExperiment):
    """Set the Structural Similarity (SSIM) and Multi-Scale Structural
    Similarity metrics (MS-SSIM) to measure the similarity between two images.

    Authors:
        - http://www.cns.nyu.edu/~lcv/ssim/msssim.zip
        - https://github.com/dashayushman/TAC-GAN/blob/master/msssim.py
    """

    @column_function([
        ColumnProperties(name="ssim", label="SSIM", plot_max=1),
        ColumnProperties(name="ms_ssim", label="MS-SSIM",
                         plot_max=1)])
    def set_StructuralSimilarity(self, index, row):
        file_path, codec_name = self.index_to_path_task(index)
        row.image_info_row = self.dataset_table_df.loc[
            indices_to_internal_loc(file_path)]
        original_array = np.fromfile(
            self.codec_results.compression_results.original_path,
            dtype=self.codec_results.numpy_dtype)
        original_array = np.reshape(original_array,
                                    (row.image_info_row["width"],
                                     row.image_info_row["height"],
                                     row.image_info_row["component_count"]))

        reconstructed_array = np.fromfile(
            self.codec_results.decompression_results.reconstructed_path,
            dtype=self.codec_results.numpy_dtype)
        reconstructed_array = np.reshape(reconstructed_array,
                                         (row.image_info_row["width"],
                                          row.image_info_row["height"],
                                          row.image_info_row[
                                              "component_count"]))

        row["ssim"] = self.compute_SSIM(original_array, reconstructed_array)
        row["ms_ssim"] = self.cumpute_MSSIM(original_array, reconstructed_array)

    def cumpute_MSSIM(self, img1, img2, max_val=255, filter_size=11,
                      filter_sigma=1.5, k1=0.01, k2=0.03, weights=None):
        """Return the MS-SSIM score between `img1` and `img2`.

        This function implements Multi-Scale Structural Similarity (MS-SSIM) Image
        Quality Assessment according to Zhou Wang's paper, "Multi-scale structural
        similarity for image quality assessment" (2003).
        Link: https://ece.uwaterloo.ca/~z70wang/publications/msssim.pdf

        Author's MATLAB implementation:
        http://www.cns.nyu.edu/~lcv/ssim/msssim.zip

        Author's Python implementation:
        https://github.com/dashayushman/TAC-GAN/blob/master/msssim.py

        Authors documentation:

        :param img1: Numpy array holding the first RGB image batch.
        :param img2: Numpy array holding the second RGB image batch.
        :param max_val: the dynamic range of the images (i.e., the difference
          between the maximum the and minimum allowed values).
        :param filter_size: Size of blur kernel to use (will be reduced for
          small images).
        :param filter_sigma: Standard deviation for Gaussian blur kernel (
          will be reduced for small images).
        :param k1: Constant used to maintain stability in the SSIM
          calculation (0.01 in the original paper).
        :param k2: Constant used to maintain stability in the SSIM
          calculation (0.03 in the original paper).
        """
        # pylint: disable=too-many-arguments
        if img1.shape != img2.shape:
            raise RuntimeError(
                'Input images must have the same shape (%s vs. %s).',
                img1.shape, img2.shape)
        if img1.ndim != 3:
            raise RuntimeError("Input images must have four dimensions, "
                               f"not {img1.ndim}")

        weights = np.array(weights if weights else
                           [0.0448, 0.2856, 0.3001, 0.2363, 0.1333])
        levels = weights.size
        downsample_filter = np.ones((2, 2, 1)) / 4.0
        im1, im2 = [x.astype(np.float64) for x in [img1, img2]]
        mssim = np.array([])
        mcs = np.array([])
        for _ in range(levels):
            ssim, cs = self.compute_SSIM(
                im1, im2, max_val=max_val, filter_size=filter_size,
                filter_sigma=filter_sigma, k1=k1, k2=k2, full=True)
            mssim = np.append(mssim, ssim)
            mcs = np.append(mcs, cs)
            filtered = [convolve(im, downsample_filter, mode='reflect')
                        for im in [im1, im2]]
            im1, im2 = [x[::2, ::2, :] for x in filtered]

        return np.prod(mcs[0:levels - 1] ** weights[0:levels - 1]) * (
                mssim[levels - 1] ** weights[levels - 1])

    def compute_SSIM(self, img1, img2, max_val=255, filter_size=11,
                     filter_sigma=1.5, k1=0.01, k2=0.03, full=False):
        """Return the Structural Similarity Map between `img1` and `img2`.

        This function attempts to match the functionality of ssim_index_new.m
        by Zhou Wang: http://www.cns.nyu.edu/~lcv/ssim/msssim.zip

        Author's Python implementation:
        https://github.com/dashayushman/TAC-GAN/blob/master/msssim.py

        :param img1: Numpy array holding the first RGB image batch.
        :param img2: Numpy array holding the second RGB image batch.

        :param max_val: the dynamic range of the images (i.e., the difference
          between the maximum the and minimum allowed values).

        :param filter_size: Size of blur kernel to use (will be reduced for
          small images). :param filter_sigma: Standard deviation for Gaussian
          blur kernel (will be reduced for small images). :param k1: Constant
          used to maintain stability in the SSIM calculation (0.01 in the
          original paper). :param k2: Constant used to maintain stability in
          the SSIM calculation (0.03 in the original paper).
        """
        # pylint: disable=too-many-arguments
        if img1.shape != img2.shape:
            raise RuntimeError(
                'Input images must have the same shape (%s vs. %s).',
                img1.shape, img2.shape)
        if img1.ndim != 3:
            raise RuntimeError(
                f"Input images must have four dimensions, not {img1.ndim}")
        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)
        height, width, bytes = img1.shape

        # Filter size can't be larger than height or width of images.
        size = min(filter_size, height, width)

        # Scale down sigma if a smaller filter size is used.
        sigma = size * filter_sigma / filter_size if filter_size else 0

        if filter_size:
            window = np.reshape(self._FSpecialGauss(size, sigma),
                                (size, size, 1))
            mu1 = signal.fftconvolve(img1, window, mode='valid')
            mu2 = signal.fftconvolve(img2, window, mode='valid')
            sigma11 = signal.fftconvolve(img1 * img1, window, mode='valid')
            sigma22 = signal.fftconvolve(img2 * img2, window, mode='valid')
            sigma12 = signal.fftconvolve(img1 * img2, window, mode='valid')
        else:
            # Empty blur kernel so no need to convolve.
            mu1, mu2 = img1, img2
            sigma11 = img1 * img1
            sigma22 = img2 * img2
            sigma12 = img1 * img2

        mu11 = mu1 * mu1
        mu22 = mu2 * mu2
        mu12 = mu1 * mu2
        sigma11 -= mu11
        sigma22 -= mu22
        sigma12 -= mu12

        # Calculate intermediate values used by both ssim and cs_map.
        c1 = (k1 * max_val) ** 2
        c2 = (k2 * max_val) ** 2
        v1 = 2.0 * sigma12 + c2
        v2 = sigma11 + sigma22 + c2
        ssim = np.mean((((2.0 * mu12 + c1) * v1) / ((mu11 + mu22 + c1) * v2)))
        cs = np.mean(v1 / v2)
        if full:
            return ssim, cs
        return ssim

    def _FSpecialGauss(self, size, sigma):

        radius = size // 2
        offset = 0.0
        start, stop = -radius, radius + 1
        if size % 2 == 0:
            offset = 0.5
            stop -= 1
        x, y = np.mgrid[offset + start:stop, offset + start:stop]
        assert len(x) == size
        g = np.exp(-((x ** 2 + y ** 2) / (2.0 * sigma ** 2)))
        return g / g.sum()


class SpectralAngleTable(LossyCompressionExperiment):
    """Lossy compression experiment that computes spectral angle "distance"
    measures between the compressed and the reconstructed images.

    Subclasses of LossyCompressionExperiment may inherit from this one to
    automatically add the data columns defined here
    """

    def get_spectral_angles_deg(self, index, row):
        """Return a sequence of spectral angles (in degrees),
        one per (x,y) position in the image, flattened in raster order.
        """
        # Read original and reconstructed images
        original_file_path, task_name = index
        image_properties_row = self.get_dataset_info_row(original_file_path)
        decompression_results = self.codec_results.decompression_results
        original_array = load_array_bsq(
            file_or_path=original_file_path,
            image_properties_row=image_properties_row)
        reconstructed_array = load_array_bsq(
            file_or_path=decompression_results.reconstructed_path,
            image_properties_row=image_properties_row)

        # Reshape flattening the x,y axes, and maintaining the z axis for
        # each (x,y) position
        original_array = np.reshape(
            original_array.swapaxes(0, 1),
            (image_properties_row["width"] * image_properties_row["height"],
             image_properties_row["component_count"]),
            "F").astype("i8")
        reconstructed_array = np.reshape(
            reconstructed_array.swapaxes(0, 1),
            (image_properties_row["width"] * image_properties_row["height"],
             image_properties_row["component_count"]),
            "F").astype("i8")

        dots = np.einsum("ij,ij->i", original_array, reconstructed_array)
        magnitude_a = np.linalg.norm(original_array, axis=1)
        magnitude_b = np.linalg.norm(reconstructed_array, axis=1)

        for i in range(magnitude_a.shape[0]):
            # Avoid division by zero
            magnitude_a[i] = max(1e-4, magnitude_a[i])
            magnitude_b[i] = max(1e-4, magnitude_b[i])

        # Clip, because the dot product can slip past 1 or -1 due to rounding
        cosines = np.clip(dots / (magnitude_a * magnitude_b), -1, 1)
        angles = np.degrees(np.arccos(cosines))
        # Round because two identical images should return an angle of exactly 0
        angles = np.round(angles, 5)

        return angles.tolist()

    @column_function([
        ColumnProperties("mean_spectral_angle_deg",
                         label="Mean spectral angle (deg)",
                         plot_min=0, plot_max=None),
        ColumnProperties("max_spectral_angle_deg",
                         label="Max spectral angle (deg)",
                         plot_min=0, plot_max=None)])
    def set_spectral_distances(self, index, row):
        spectral_angles = self.get_spectral_angles_deg(index=index, row=row)

        for angle in spectral_angles:
            assert not np.isnan(
                angle), f"Error calculating an angle for {index}: {angle}"

        row["mean_spectral_angle_deg"] = sum(spectral_angles) / len(
            spectral_angles)
        row["max_spectral_angle_deg"] = max(spectral_angles)


class GiciLibHelper:
    """Definition of helper methods that can be used with software based on
    the GiciLibs (see gici.uab.cat/GiciWebPage/downloads.php).
    """

    def file_info_to_data_str(self, original_file_info):
        if original_file_info["bytes_per_sample"] == 1:
            data_type_str = "1"
        elif original_file_info["bytes_per_sample"] == 2:
            if original_file_info["signed"]:
                data_type_str = "3"
            else:
                data_type_str = "2"
        elif original_file_info["bytes_per_sample"] == 4:
            if original_file_info["signed"]:
                return "4"
            else:
                raise ValueError(
                    "32-bit samples are supported, but they must be signed.")
        else:
            raise ValueError(
                f"Invalid data type, not supported by "
                f"{self.__class__.__name__}: {original_file_info}")
        return data_type_str

    def file_info_to_endianness_str(self, original_file_info):
        return "0" if original_file_info["big_endian"] else "1"

    def get_gici_geometry_str(self, original_file_info):
        """Get a string to be passed to the -ig or -og parameters. The '-ig'
        or '-og' part is not included in the returned string.
        """
        return f"{original_file_info['component_count']} " \
               f"{original_file_info['height']} " \
               f"{original_file_info['width']} " \
               f"{self.file_info_to_data_str(original_file_info=original_file_info)} " \
               f"{self.file_info_to_endianness_str(original_file_info=original_file_info)} " \
               f"0 "
