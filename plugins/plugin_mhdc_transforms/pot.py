#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper for the POT transform
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "25/05/2020"

import os
import tempfile
import filecmp
import shutil
import time

from enb.config import get_options

options = get_options(from_main=False)

import enb.sets
import enb.isets
import enb.ray_cluster
import enb.tcall
import enb.atable as atable


class POTVersionTable(enb.sets.FileVersionTable, enb.isets.ImagePropertiesTable):
    mhdc_transform_path = os.path.join("POT", "mhdctransform")

    def output_path_to_si_path(self, output_path):
        return f"{output_path}_SI.pot"

    def version(self, input_path, output_path, row):
        assert os.path.exists(self.mhdc_transform_path), \
            f"mhdc transform binary not found at {self.mhdc_transform_path} - reset and retry"
        invocation = f"/usr/bin/time -v {self.mhdc_transform_path} " \
                     f"--Size {row['component_count']} {row['height']} {row['width']} " \
                     f"--Bitdepth {8 * row['bytes_per_sample']} " \
                     f"--SampleType {1 if row['signed'] else 0} " \
                     f"--SpectralTransform 2 --Direction 0 " \
                     f"{input_path} {self.output_path_to_si_path(output_path)} {output_path}"
        status, output, reported_time = enb.tcall.get_status_output_time(invocation)

        # s32b is hardcoded in mhdctransform - revert to oritingal bytes per sample
        input_row = row.copy()
        input_row["bytes_per_sample"] = 4
        input_row["signed"] = True
        s32b_array = enb.isets.load_array_bsq(file_or_path=output_path, image_properties_row=input_row)

        output_row = row.copy()
        output_row["signed"] = True
        output_dtype = enb.isets.iproperties_row_to_numpy_dtype(output_row)
        enb.isets.dump_array_bsq(array=s32b_array, file_or_path=output_path, dtype=output_dtype)

        return reported_time

    @atable.redefines_column
    def set_signed(self, file_path, row):
        """POT-transformed images are always signed
        """
        row[_column_name] = True


class InversePOTVersionTable(enb.sets.FileVersionTable, enb.isets.ImageGeometryTable):
    """VersionTable that applies the inverse POT and verifies that the result
    is lossless.
    """
    mhdc_transform_path = POTVersionTable.mhdc_transform_path

    def version(self, input_path, output_path, row):
        si_path = POTVersionTable.output_path_to_si_path(self, output_path=input_path)
        assert os.path.exists(si_path), f"POT side information {si_path} does not exist but is necessary."

        with tempfile.NamedTemporaryFile(dir=options.base_tmp_dir) as tmp_input:
            original_row = row.copy()
            enb.isets.ImageGeometryTable.set_bytes_per_sample.__globals__.update(_column_name="bytes_per_sample")
            enb.isets.ImageGeometryTable.set_bytes_per_sample(
                self.original_properties_table, file_path=input_path, row=original_row)
            del enb.isets.ImageGeometryTable.set_bytes_per_sample.__globals__["_column_name"]
            enb.isets.ImageGeometryTable.set_signed.__globals__.update(_column_name="signed")
            enb.isets.ImageGeometryTable.set_signed(
                self.original_properties_table, file_path=input_path, row=original_row)
            del enb.isets.ImageGeometryTable.set_signed.__globals__["_column_name"]

            # Transform back to hardcoded s32b
            input_row = original_row.copy()
            input_row["signed"] = True
            array = enb.isets.load_array_bsq(file_or_path=input_path, image_properties_row=input_row)
            output_row = original_row.copy()
            output_row["bytes_per_sample"] = 4
            output_row["signed"] = True
            hardcoded_type = enb.isets.iproperties_row_to_numpy_dtype(image_properties_row=output_row)
            enb.isets.dump_array_bsq(array=array, file_or_path=tmp_input.name, dtype=hardcoded_type)

            invocation = f"{self.mhdc_transform_path} " \
                         f"--Size {original_row['component_count']} {original_row['height']} {original_row['width']} " \
                         f"--Bitdepth {8 * original_row['bytes_per_sample']} " \
                         f"--SampleType {1 if original_row['signed'] else 0} " \
                         f"--SpectralTransform 2 --Direction 1 " \
                         f"{tmp_input.name} {POTVersionTable.output_path_to_si_path(self, input_path)} {output_path}"
            status, output, invocation_time = enb.tcall.get_status_output_time(invocation)
            return invocation_time


def apply_pot(input_dir, output_dir, forward_properties_csv=None, inverse_properties_csv=None,
              repetitions=10, run_sequential=True):
    """Apply the POT to input_dir and save the results to output_dir.

    :param input_dir: input directory to be transformed (recursively)
    :param output_dir: path to the output transformed dir
    :param forward_properties_csv: if not None, properties of the transformed images
      are stored here (including fwd transform time)
    :param inverse_properties_csv: if not None, properties of the reconstructed images
      are stored here (including inverse transform time)
    :param repetitions: number of repetitions used to calculate execution time
      (for both forward and inverse transform)
    :param run_sequential: if True, transformations are run in sequential mode
      (as opposed to parallel) so that time measurements can be taken

    :raises AssertionError: if transformation/reconstruction is not lossless

    :return: fwd_pot_df, inv_pot_df, i.e., the dataframes obtained with get_df
      for POTVersionTAble and InversePOTVersionTable, respectively.
    """
    assert repetitions >= 1

    with tempfile.TemporaryDirectory(dir=options.base_tmp_dir) as tmp_dir:
        assert os.path.isdir(input_dir)
        os.makedirs(output_dir, exist_ok=True)

        options.persistence_dir = tmp_dir
        options.base_dataset_dir = input_dir
        options.base_version_dataset_dir = output_dir
        options.repetitions = repetitions
        options.sequential = 1 if run_sequential else 0
        reconstructed_dir_path = os.path.join(tmp_dir, "reconstructed_dir")
        os.makedirs(reconstructed_dir_path, exist_ok=True)

        enb.ray_cluster.init_ray()

        original_target_files = enb.sets.get_all_test_files()

        if options.verbose:
            print(f"[F]orward POT to {len(original_target_files)} images")
        ig_table = enb.isets.ImageGeometryTable(
            csv_support_path=os.path.join(options.persistence_dir, "original_image_geometry.csv"))
        pot_table = POTVersionTable(
            original_base_dir=options.base_dataset_dir, version_base_dir=options.base_version_dataset_dir,
            original_properties_table=ig_table, version_name="POT",
            csv_support_path=os.path.join(options.persistence_dir, "pot_versioned_properties.csv"))
        pot_df = pot_table.get_df(target_indices=original_target_files,
                                  parallel_versioning=not run_sequential,
                                  overwrite=options.force,
                                  parallel_row_processing=True)

        if options.verbose:
            print(f"[I]nverse POT to {len(original_target_files)} images")
        transformed_target_files = enb.sets.get_all_test_files(base_dataset_dir=options.base_version_dataset_dir)
        with tempfile.NamedTemporaryFile(dir=tmp_dir) as tmp_csv_support:
            shutil.copy(pot_table.csv_support_path, tmp_csv_support.name)
            pot_ig_table = enb.isets.ImageGeometryTable(csv_support_path=tmp_csv_support.name)
            ipot_table = InversePOTVersionTable(
                original_base_dir=options.base_version_dataset_dir,
                version_base_dir=reconstructed_dir_path,
                original_properties_table=pot_ig_table,
                version_name="inverse_pot",
                csv_support_path=os.path.join(
                    options.persistence_dir, "inverse_pot_versioned_properties.csv"))
            ipot_df = ipot_table.get_df(parallel_versioning=not run_sequential,
                                        parallel_row_processing=True,
                                        target_indices=transformed_target_files)

        if options.verbose:
            print(f"[C]hecking lossless to {len(original_target_files)}  images")
        checked_count = 0
        for original_path in original_target_files:
            reconstructed_path = os.path.abspath(os.path.realpath(original_path)).replace(
                options.base_dataset_dir, reconstructed_dir_path)
            assert filecmp.cmp(original_path, reconstructed_path), \
                f"Not lossless transform {original_path}<->{reconstructed_path}"
            checked_count += 1
        assert checked_count == len(original_target_files)

        if forward_properties_csv is not None:
            shutil.copyfile(pot_table.csv_support_path, forward_properties_csv)
        if inverse_properties_csv is not None:
            shutil.copyfile(ipot_table.csv_support_path, inverse_properties_csv)

        return pot_df, ipot_df

if __name__ == '__main__':
    default_input_dir = "./green_book_corpus"
    default_output_dir = "/data/research-materials/pot_green_book2"
    persistence_dir = "./persistence"
    repetition_count = 10
    run_sequential = True

    plugin_mhdc_transforms.pot.apply_pot(
        input_dir=os.path.abspath(os.path.realpath(
            options.base_dataset_dir if options.base_dataset_dir
            else default_input_dir)),
        output_dir=os.path.abspath(os.path.realpath(
            options.base_version_dataset_dir if options.base_version_dataset_dir
            else default_output_dir)),
        forward_properties_csv=os.path.join(persistence_dir, "pot_versioned_properties.csv"),
        inverse_properties_csv=os.path.join(persistence_dir, "ipot_versioned_properties.csv"),
        run_sequential=run_sequential,
        repetitions=repetition_count)