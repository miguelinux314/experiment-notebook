#!/usr/bin/env python3
"""Unit tests for the icompression module
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/4/6"

import unittest
import tempfile
import os
import sys
import numpy as np
import shutil

import enb.icompression
import test_all
from enb.config import options

from enb import icompression
from enb import isets
from codec_implementations import trivial_codecs


class ConstantOutputCodec(icompression.LosslessCodec):
    """Codec that reconstructs an image with the same geometry
    but all pixels identical to a constant provided at initialization
    time
    """

    def __init__(self, reconstruct_value):
        """
        :param reconstruct_value: value that all pixels of
          the reconstructed images have.
        """
        super().__init__()
        self.reconstruct_value = reconstruct_value

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        dt = isets.iproperties_row_to_numpy_dtype(image_properties_row=original_file_info)
        a = np.full((original_file_info["width"],
                     original_file_info["height"],
                     original_file_info["component_count"]),
                    fill_value=self.reconstruct_value, dtype=dt)
        isets.dump_array_bsq(array=a, file_or_path=reconstructed_path)

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        shutil.copyfile(original_path, compressed_path)


class TestIcompression(unittest.TestCase):

    def test_mse_pae(self):
        """Test MSE and PAE calculation for simple images
        for all supported data types.
        """
        width = 37
        height = 64
        component_count = 7
        original_constant = 10

        for signed in [True, False]:
            for bytes_per_sample in [1, 2, 4]:
                for big_endian in [True, False]:
                    if bytes_per_sample == 1 and not big_endian:
                        continue
                    dtype = ((">" if big_endian else "<") if bytes_per_sample > 1 else "") \
                            + ("i" if signed else "u") \
                            + str(bytes_per_sample)
                    sample_tag = ("s" if signed else "u") \
                                 + str(8 * bytes_per_sample) \
                                 + ("be" if big_endian else "le")

                    fill_values = [original_constant] if not signed else [-original_constant, original_constant]
                    for fill_value in fill_values:
                        array = np.full((width, height, component_count),
                                        fill_value=fill_value, dtype=dtype)
                        for error in [-3, 3]:
                            with tempfile.TemporaryDirectory() as tmp_dir, \
                                    tempfile.TemporaryDirectory() as persistence_dir, \
                                    tempfile.NamedTemporaryFile(
                                        dir=tmp_dir,
                                        suffix=f"-{component_count}x{height}x{width}_{sample_tag}.raw") as tmp_file:
                                isets.dump_array_bsq(array=array, file_or_path=tmp_file.name)

                                coc = ConstantOutputCodec(reconstruct_value=fill_value + error)
                                options.persistence_dir = persistence_dir
                                ce = icompression.LossyCompressionExperiment(
                                    codecs=[coc],
                                    dataset_paths=[tmp_file.name],
                                )
                                df = ce.get_df()
                                assert (df["pae"] == abs(error)).all(), \
                                    (df["pae"], abs(error))
                                assert (np.abs(df["mse"] - error ** 2) < (2 * sys.float_info.epsilon)).all(), \
                                    (df["mse"], abs(error))


class TestGeneralLosslessExperiment(unittest.TestCase):

    def test_lossless(self):
        """Test the enb.icompression.GeneralLosslessExperiment class
        """
        width = 37
        height = 64
        component_count = 7
        original_constant = 10
        dtype = ">u1"

        fill_value = original_constant
        array = np.full((width, height, component_count),
                        fill_value=fill_value, dtype=dtype)
        with tempfile.TemporaryDirectory() as tmp_dir, \
                tempfile.TemporaryDirectory() as persistence_dir, \
                tempfile.NamedTemporaryFile(
                    dir=tmp_dir,
                    suffix=f".exotic") as tmp_file:
            isets.dump_array_bsq(array=array, file_or_path=tmp_file.name)
            coc = ConstantOutputCodec(reconstruct_value=fill_value)
            options.persistence_dir = persistence_dir
            ce = icompression.GeneralLosslessExperiment(
                codecs=[coc],
                dataset_paths=[tmp_file.name],
            )
            df = ce.get_df()
            assert (df["lossless_reconstruction"] == True).all()


class TestSpectralAngle(unittest.TestCase):
    def get_expected_angles_deg(self, img_a, img_b):
        """Manually obtain the vector angles in degrees"""
        width, height, component_count = img_a.shape
        assert img_a.shape == img_b.shape

        img_a = img_a.copy().astype("i4")
        img_b = img_b.copy().astype("i4")

        angles = []
        for x in range(width):
            for y in range(height):
                a = img_a[x, y, :]
                b = img_b[x, y, :]
                num = np.dot(a, b)
                den = np.sqrt(np.dot(a, a)) * np.sqrt(np.dot(b, b))

                angle = np.arccos(num / den)
                angles.append(np.rad2deg(angle))
        return angles

    def test_spectral_angle(self):
        for constant_offset in [1, 5, 10]:
            width, height, component_count = 2, 3, 4
            bytes_per_sample, signed, big_endian = 2, True, True
            row = dict(signed=signed, bytes_per_sample=bytes_per_sample, big_endian=big_endian, float=False)
            original_array = np.zeros((width, height, component_count),
                                      dtype=isets.iproperties_row_to_numpy_dtype(row))
            for x in range(width):
                for y in range(height):
                    for z in range(component_count):
                        original_array[x, y, z] = 100 * z + 10 * y + x
            reconstructed_array = original_array + constant_offset
            expected_angles = self.get_expected_angles_deg(original_array, reconstructed_array)

            tag = isets.iproperties_to_name_tag(
                width=width, height=height, component_count=component_count,
                big_endian=big_endian, bytes_per_sample=bytes_per_sample, signed=signed)

            with tempfile.TemporaryDirectory() as tmp_dir:
                with tempfile.NamedTemporaryFile(suffix="-" + tag + ".raw", dir=tmp_dir) as tmp_file:
                    isets.dump_array_bsq(original_array, tmp_file.name)
                    sa_exp = icompression.SpectralAngleTable(
                        codecs=[trivial_codecs.OffsetLossyCodec(constant_offset)],
                        dataset_paths=[tmp_file.name],
                        csv_experiment_path=os.path.join(tmp_dir, "exp_persistence.csv"),
                        csv_dataset_path=os.path.join(tmp_dir, "dataset_persistence.csv"))

                    df = sa_exp.get_df()

                    abs_diff_average_sa = abs(df.iloc[0]["mean_spectral_angle_deg"]
                                              - (sum(expected_angles) / len(expected_angles)))
                    abs_diff_max_sa = abs(df.iloc[0]["max_spectral_angle_deg"]
                                          - max(expected_angles))

                    assert abs_diff_average_sa < 1e-5, f"Wrong mean spectral angle (diff={abs_diff_average_sa})"
                    assert abs_diff_max_sa < 1e-5, f"Wrong maximum spectral angle (diff={abs_diff_max_sa})"

class TestQuantizationWrapperCodec(unittest.TestCase):
    def test_pae(self):
        class DummyCodec(enb.icompression.LosslessCodec):
            """Dummy copy-based codec
            """
            def compress(self, original_path: str, compressed_path: str, original_file_info=None):
                shutil.copyfile(original_path, compressed_path)
            def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
                shutil.copyfile(compressed_path, reconstructed_path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            width, height, component_count = 128, 128, 12
            array = np.zeros((width, height, component_count), dtype=">u1")
            i = 0
            for z in range(component_count):
                for y in range(height):
                    for x in range(width):
                        array[x, y, z] = i
                        i += 1

            original_path = os.path.join(tmp_dir, f"img-u8be-{component_count}x{height}x{width}.raw")
            compressed_path = os.path.join(tmp_dir, f"img-u8be-{component_count}x{height}x{width}.comp")
            reconstructed_path = os.path.join(tmp_dir, f"img-u8be-{component_count}x{height}x{width}.rec")

            enb.isets.dump_array_bsq(array, original_path)

            for qstep in (1, 2, 3, 10):
                for p in (compressed_path, reconstructed_path):
                    if os.path.exists(p):
                        os.remove(p)
                q_wrapped_codec = enb.icompression.QuantizationWrapperCodec(codec=DummyCodec(), qstep=1)
                q_wrapped_codec.compress(original_path, compressed_path)
                q_wrapped_codec.decompress(compressed_path, reconstructed_path)
                reconstructed_array = enb.isets.load_array(reconstructed_path)

                assert np.max(array.astype(np.int64) - reconstructed_array.astype(np.int64)) <= qstep // 2








if __name__ == '__main__':
    unittest.main()
