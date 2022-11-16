#!/usr/bin/env python3
"""Plugin to extract photometry information from a file using IRAF.
"""
__author__ = "Òscar Maireles and Miguel Hernández-Cabronero"
__since__ = "2022/11/07"

import os
import enb
import tempfile
import subprocess
import pandas as pd
import sys
from astropy.io import fits


def raw_to_fits(raw_path, fits_path):
    # Load image indexed by [x,y,z]
    img = enb.isets.load_array_bsq(raw_path)
    # Reindex image to [z,y,x] and save 
    fits.PrimaryHDU(img.swapaxes(0, 2)).writeto(fits_path)


def raw_to_photometry_df(
        raw_path,
        extension=0, fwhm=3.5, sigma=6, threshold=8.0,
        min_value=3_000_000, max_value=50_000_000,
        annulus=10.0, dannulus=10.0, aperture=4.0,
        sigma_phot=0.0):
    with tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir, suffix=".csv") as csv_file, \
            tempfile.NamedTemporaryFile(dir=enb.config.options.base_tmp_dir, suffix=".fits") as fits_file:
        raw_to_fits(raw_path, fits_file.name)
        slave_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iraf_photometry_slave.py")
        invocation = f"{sys.executable} " \
                     f"{os.path.abspath(slave_path)} " \
                     f"{os.path.abspath(fits_file.name)} {os.path.abspath(csv_file.name)}"
        status, output = subprocess.getstatusoutput(invocation)
        if status != 0:
            raise Exception(f"Status = {status} != 0.\nInput=[{invocation}].\nOutput=[{output}]")
        return pd.read_csv(csv_file.name)


class LossyPhotometryExperiment(enb.icompression.LossyCompressionExperiment):
    """Lossy compression experiment that extracts photometry-based distortion metrics.
    """

    def __init__(self, codecs, threshold,
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table=None,
                 overwrite_file_properties=False,
                 task_families=None):

        super().__init__(codecs=codecs, dataset_paths=dataset_paths, csv_experiment_path=csv_experiment_path,
                         csv_dataset_path=csv_dataset_path,
                         dataset_info_table=dataset_info_table, overwrite_file_properties=overwrite_file_properties,
                         task_families=task_families)

        self.threshold = threshold

    @enb.atable.column_function([
        enb.atable.ColumnProperties("original_photometry_object_count", label="Original photometry object count",
                                    plot_min=0),
        enb.atable.ColumnProperties("reconstructed_photometry_object_count",
                                    label="Reconstructed photometry object count", plot_min=0),
        enb.atable.ColumnProperties("recovered_objects", label="Recovered objects", plot_min=0),
        enb.atable.ColumnProperties("mean_magnitude_difference", label="Mean magnitude difference", plot_min=0),
        enb.atable.ColumnProperties("maximum_magnitude_difference", label="Maximum magnitude difference", plot_min=0),
        enb.atable.ColumnProperties("F1_score", label="F1 score", plot_mitrue_positive=0),
    ])
    def set_photometry_columns(self, index, row):
        original_raw_path, codec = self.index_to_path_task(index)
        reconstructed_raw_path = self.codec_results.decompression_results.reconstructed_path

        original_photometry_df = raw_to_photometry_df(raw_path=original_raw_path)
        reconstructed_photometry_df = raw_to_photometry_df(raw_path=reconstructed_raw_path)

        x_position_original = original_photometry_df.loc[:, "x"]
        x_position_reconstructed = reconstructed_photometry_df.loc[:, "x"]
        y_position_original = original_photometry_df.loc[:, "y"]
        y_position_reconstructed = reconstructed_photometry_df.loc[:, "y"]
        magnitude_original = original_photometry_df.loc[:, "magnitude"]
        magnitude_reconstructed = reconstructed_photometry_df.loc[:, "magnitude"]

        true_positive = 0
        magnitude_difference = []

        for i in range(len(x_position_reconstructed)):
            for j in range(len(x_position_original)):
                if len(x_position_original) == 1:
                    pass
                elif abs(x_position_original[j] - x_position_reconstructed[i]) < self.threshold \
                        and abs(y_position_original[j] - y_position_reconstructed[i]) < self.threshold:
                    magnitude_difference.append(abs(magnitude_original[j] - magnitude_reconstructed[i]))
                    true_positive = true_positive + 1

        false_negative = len(x_position_original) - true_positive
        false_positive = len(x_position_reconstructed) - true_positive

        row["original_photometry_object_count"] = len(original_photometry_df)
        row["reconstructed_photometry_object_count"] = len(reconstructed_photometry_df)
        row["recovered_objects"] = true_positive
        row["mean_magnitude_difference"] = sum(magnitude_difference) / len(magnitude_difference) \
            if len(magnitude_difference) else 0
        row["maximum_magnitude_difference"] = max(magnitude_difference) \
            if len(magnitude_difference) else 0
        row["F1_score"] = 2 * true_positive / (2 * true_positive + false_positive + false_negative) \
            if true_positive + false_positive + false_negative > 0 else 0

        if not len(magnitude_difference):
            enb.logger.warn(f"Warning: found zero magnitude differences for "
                            f"{original_raw_path} and {codec.label} ({codec.name})")
