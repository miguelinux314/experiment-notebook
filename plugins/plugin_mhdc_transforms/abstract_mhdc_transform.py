#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template class for transformation using mhdctransform
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "25/05/2020"

import os
import tempfile
import filecmp
import shutil

from enb.config import get_options

options = get_options(from_main=False)

import enb.sets
import enb.isets
import enb.icompression
import enb.ray_cluster
import enb.tcall
import enb.atable as atable

default_mhdc_binary_path = os.path.join(os.path.dirname(__file__), "mhdctransform")


def output_path_to_si_path(output_path, transform_number):
    return f"{output_path}_SI.mhdc_t{transform_number}"


class MHDCGeometryTable(enb.isets.ImageGeometryTable):
    @enb.atable.redefines_column
    def set_signed(self, file_path, row):
        """"""
        row[_column_name] = True


class MHDCPropertiesTable(MHDCGeometryTable, enb.isets.ImagePropertiesTable):
    """Properties table for forward MHDC-transformed images"""
    pass


class MHDCTransformTable(enb.sets.FileVersionTable, enb.isets.ImagePropertiesTable):
    mhdc_transform_path = default_mhdc_binary_path
    
    invocation_output_folder = None

    @property
    def transform_number(self):
        raise NotImplementedError("Subclasses must return the appropriate transform number")

    @property
    def compacted_bytes_per_sample(self):
        """ Number of bytes per sample used in the final transformed files.
        If None is returned, the nominal bytes per sample of the original data
        are maintained.
        """
        return None

    def get_specific_params(self, input_path, output_path):
        """Return a string of parameters specific to this transform,
        or an empty string if none are needed.
        """
        return ""

    def compact_samples(self, transformed_path, compacted_path, row):
        """The mhdctransform binary always outputs in 4-bytes-per-sample, signed format.
        This method compacts this information into s16b.

        :param transformed_path: path to the data in s32b
        :param compacted_path: path to the data in s16b (can be the same as trasformed_path,
          in that case it is overwriten)
        """
        input_row = row.copy()
        input_row["bytes_per_sample"] = 4
        input_row["signed"] = True
        s32b_array = enb.isets.load_array_bsq(file_or_path=transformed_path, image_properties_row=input_row)

        output_row = row.copy()
        output_row["signed"] = True
        if self.compacted_bytes_per_sample is not None:
            output_row["bytes_per_sample"] = self.compacted_bytes_per_sample
        output_dtype = enb.isets.iproperties_row_to_numpy_dtype(output_row)
        enb.isets.dump_array_bsq(array=s32b_array, file_or_path=compacted_path, dtype=output_dtype)

    def version(self, input_path, output_path, row):
        assert os.path.exists(self.mhdc_transform_path), \
            f"mhdc transform binary not found at '{self.mhdc_transform_path}' - please reset and retry"
        invocation = f"/usr/bin/time -v {self.mhdc_transform_path} " \
                     f"--Size {row['component_count']} {row['height']} {row['width']} " \
                     f"--Bitdepth {8 * row['bytes_per_sample']} " \
                     f"--SampleType {1 if row['signed'] else 0} " \
                     f"--SpectralTransform {self.transform_number} --Direction 0 " \
                     f"{self.get_specific_params(input_path=input_path, output_path=output_path)} " \
                     f"{input_path} " \
                     f"{output_path_to_si_path(output_path=output_path, transform_number=self.transform_number)} " \
                     f"{output_path}"
        status, output, reported_time = enb.tcall.get_status_output_time(invocation)

        # s32b is hardcoded in mhdctransform - revert to original bytes per sample
        self.compact_samples(transformed_path=output_path, compacted_path=output_path, row=row)

        if self.invocation_output_folder is not None:
            os.makedirs(self.invocation_output_folder, exist_ok=True)
            invocation_output_path = os.path.join(
                self.invocation_output_folder,
                self.__class__.__name__ + "_" + os.path.abspath(os.path.realpath(input_path)).replace(os.sep, "_"))
            with open(invocation_output_path, "w") as invocation_output_file:
                invocation_output_file.write(f"Input_path: {input_path}\n "
                                             f"Invocation: {invocation}\n "
                                             f"Status: {status}\n "
                                             f"Output: {output}")

        return reported_time

    @atable.redefines_column
    def set_signed(self, file_path, row):
        """MHDC-transformed images are always signed
        """
        row[_column_name] = True


class InverseMHDCTransformTable(enb.sets.FileVersionTable, enb.isets.ImageGeometryTable):
    """VersionTable that applies an inverse MHDC transform and verifies that the result
    is lossless.
    """
    mhdc_transform_path = default_mhdc_binary_path

    @property
    def transform_number(self):
        raise NotImplementedError("Subclasses must return the appropriate transform number "
                                  "(should be the same as for the Direct version")

    @property
    def compacted_bytes_per_sample(self):
        """ Number of bytes per sample used in the final transformed files.
        If None is returned, the nominal bytes per sample of the original data
        are maintained.
        """
        return None

    def expand_sample(self, compacted_path, expanded_path, original_row):
        """Apply the inverse of MHDCTransformTable.compact_samples, i.e.,
        transform data into s32b format.
        """
        input_row = original_row.copy()
        input_row["signed"] = True
        array = enb.isets.load_array_bsq(file_or_path=compacted_path, image_properties_row=input_row)
        output_row = original_row.copy()
        output_row["bytes_per_sample"] = 4
        output_row["signed"] = True
        hardcoded_type = enb.isets.iproperties_row_to_numpy_dtype(image_properties_row=output_row)
        enb.isets.dump_array_bsq(array=array, file_or_path=expanded_path, dtype=hardcoded_type)

    def version(self, input_path, output_path, row):
        si_path = output_path_to_si_path(output_path=input_path, transform_number=self.transform_number)
        assert os.path.exists(si_path), f"Side information {si_path} does not exist but is necessary."

        with tempfile.NamedTemporaryFile(dir=options.base_tmp_dir) as tmp_input:
            original_row = row.copy()

            if self.compacted_bytes_per_sample is None:
                enb.isets.ImageGeometryTable.set_bytes_per_sample.__globals__.update(_column_name="bytes_per_sample")
                enb.isets.ImageGeometryTable.set_bytes_per_sample(
                    self.original_properties_table, file_path=input_path, row=original_row)
                del enb.isets.ImageGeometryTable.set_bytes_per_sample.__globals__["_column_name"]
            else:
                original_row["bytes_per_sample"] = self.compacted_bytes_per_sample
            enb.isets.ImageGeometryTable.set_signed.__globals__.update(_column_name="signed")
            enb.isets.ImageGeometryTable.set_signed(
                self.original_properties_table, file_path=input_path, row=original_row)
            del enb.isets.ImageGeometryTable.set_signed.__globals__["_column_name"]

            # Transform back to hardcoded s32b
            self.expand_sample(compacted_path=input_path, expanded_path=tmp_input.name,
                               original_row=original_row)

            invocation = f"{self.mhdc_transform_path} " \
                         f"--Size {original_row['component_count']} {original_row['height']} {original_row['width']} " \
                         f"--Bitdepth {8 * original_row['bytes_per_sample']} " \
                         f"--SampleType {1 if original_row['signed'] else 0} " \
                         f"--SpectralTransform {self.transform_number} --Direction 1 " \
                         f"{tmp_input.name} " \
                         f"{output_path_to_si_path(output_path=input_path, transform_number=self.transform_number)} " \
                         f"{output_path}"
            status, output, invocation_time = enb.tcall.get_status_output_time(invocation)
            return invocation_time


class MDHCLosslessCompressionExperiment(enb.icompression.LosslessCompressionExperiment):
    def __init__(self, codecs, dataset_paths=None, csv_experiment_path=None, csv_dataset_path=None,
                 overwrite_file_properties=False, parallel_dataset_property_processing=None,
                 reconstructed_dir_path=None, *args, **kwargs):
        dataset_info_table = MHDCPropertiesTable(
            csv_support_path=csv_dataset_path)

        super().__init__(codecs=codecs, dataset_paths=dataset_paths, csv_experiment_path=csv_experiment_path,
                         csv_dataset_path=csv_dataset_path, dataset_info_table=dataset_info_table,
                         overwrite_file_properties=overwrite_file_properties,
                         parallel_dataset_property_processing=parallel_dataset_property_processing,
                         reconstructed_dir_path=reconstructed_dir_path,
                         *args, **kwargs)

    @property
    def transform_number(self):
        raise NotImplementedError()

    @enb.atable.redefines_column
    def set_compressed_data_size(self, index, row):
        si_path = output_path_to_si_path(
            output_path=row[enb.sets.FilePropertiesTable.index_name],
            transform_number=self.transform_number)
        assert os.path.exists(si_path), f"Side information {si_path} not found. Is it really a RWA-transformed set?"
        row[_column_name] = os.path.getsize(row.compression_results.compressed_path) \
                            + os.path.getsize(si_path)


def apply_transform(
        input_dir, output_dir, forward_class, inverse_class,
        forward_properties_csv=None, inverse_properties_csv=None,
        repetitions=10, run_sequential=True):
    """Apply an MHDC transform to input_dir and save the results to output_dir.

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

    :return: fwd_df, inv_df, i.e., the dataframes obtained with get_df
      for forward_class and inverse_class, respectively.
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
            print(f"[F]orward MHDC<{forward_class.__name__}> to {len(original_target_files)} images")
        original_geometry_table = enb.isets.ImageGeometryTable(
            csv_support_path=os.path.join(options.persistence_dir, "original_properties.csv"))
        forward_table = forward_class(
            original_base_dir=options.base_dataset_dir, version_base_dir=options.base_version_dataset_dir,
            original_properties_table=original_geometry_table, version_name=forward_class.__name__,
            csv_support_path=os.path.join(options.persistence_dir, "versioned_properties.csv"))
        forward_df = forward_table.get_df(target_indices=original_target_files,
                                          parallel_versioning=not run_sequential,
                                          overwrite=options.force,
                                          parallel_row_processing=True)

        if options.verbose:
            print(f"[I]nverse MHDC<{inverse_class.__name__}> to {len(original_target_files)} images")
        transformed_target_files = enb.sets.get_all_test_files(base_dataset_dir=options.base_version_dataset_dir)
        with tempfile.NamedTemporaryFile(dir=tmp_dir) as tmp_csv_support:
            shutil.copy(forward_table.csv_support_path, tmp_csv_support.name)
            fwd_ig_table = enb.isets.ImageGeometryTable(csv_support_path=tmp_csv_support.name)
            inverse_table = inverse_class(
                original_base_dir=options.base_version_dataset_dir,
                version_base_dir=reconstructed_dir_path,
                original_properties_table=fwd_ig_table,
                version_name=inverse_class.__name__,
                csv_support_path=os.path.join(
                    options.persistence_dir, "inverse_versioned_properties.csv"))
            inverse_df = inverse_table.get_df(parallel_versioning=not run_sequential,
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
            os.makedirs(os.path.dirname(os.path.abspath(forward_properties_csv)), exist_ok=True)
            shutil.copyfile(forward_table.csv_support_path, forward_properties_csv)
        if inverse_properties_csv is not None:
            os.makedirs(os.path.dirname(os.path.abspath(inverse_properties_csv)), exist_ok=True)
            shutil.copyfile(inverse_table.csv_support_path, inverse_properties_csv)

        return forward_df, inverse_df
