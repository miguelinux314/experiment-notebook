#!/usr/bin/env python3
"""Unit tests for sets.py
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/10/05"

import unittest
import tempfile
import glob
import os
import shutil
import filecmp
import numpy as np

import enb
import enb.atable
import enb.sets as sets
from enb.config import options


class TestSets(unittest.TestCase):

    def test_file_properties(self):
        """Test that file properties are correctly obtained and retrieved.
        """
        target_indices = [p for p in glob.glob(
            os.path.join(enb.calling_script_dir, "*.py"))
                          if os.path.isfile(p)]

        # dataset_df = get_result_df()
        with tempfile.NamedTemporaryFile(suffix=".csv") as tmp_file:
            dataset_properties_table = sets.FilePropertiesTable(
                csv_support_path=tmp_file.name)

            # Attempt loading from an empty file, verify it is empty because fill=False
            try:
                empty_property_table = dataset_properties_table.get_df(
                    fill=False, target_indices=target_indices)
            except ValueError:
                assert len(target_indices) == 0

            assert len(empty_property_table) == 0, empty_property_table
            assert empty_property_table.isnull().all().all()

            # Run the actual loading sequence
            dataset_properties_df = dataset_properties_table.get_df(
                target_indices=target_indices)
            assert len(dataset_properties_df) == len(target_indices)

            # Obtain again, forcing load from the temporary file without any additional computations
            new_df = dataset_properties_table.get_df(
                target_indices=target_indices, fill=False, overwrite=False)
            assert (dataset_properties_df.columns == new_df.columns).all()

            for c in dataset_properties_df.columns:
                try:
                    if not (dataset_properties_df[c] == new_df[c]).all():
                        # Floating point values might be unstable
                        try:
                            assert np.abs(dataset_properties_df[c] - new_df[
                                c]).max() < 1e-12
                        except TypeError:
                            # Stability within dictionaries is not verified,
                            # but only dictionaries can raise this error
                            assert (dataset_properties_df[c].apply(
                                lambda c: isinstance(c, dict))).all()
                except ValueError as ex:
                    raise RuntimeError(
                        "The original and loaded datasets differ") from ex

    def test_trivial_version_table(self):
        """Test versioning with a table that simply copies the original file.
        """

        class TrivialVersionTable(sets.FileVersionTable):
            """Trivial FileVersionTable that makes an identical copy of the original
            """

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.dataset_files_extension = "py"

            def version(self, input_path, output_path, row):
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy(input_path, output_path)
                assert os.path.getsize(input_path) == os.path.getsize(
                    output_path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            options.persistence_dir = tmp_dir
            fpt = sets.FilePropertiesTable(base_dir=options.project_root)
            fpt.dataset_files_extension = "py"
            fpt_df = fpt.get_df()
            fpt_df["original_file_path"] = fpt_df["file_path"]
            tvt = TrivialVersionTable(version_base_dir=tmp_dir,
                                      version_name="trivial",
                                      original_base_dir=options.project_root)
            tvt_df = tvt.get_df()
            for input_path in (
                    p for p in glob.glob(
                os.path.join(options.project_root, "**", "*.py"), recursive=True)
                               if os.path.isfile(p)):
                assert filecmp.cmp(input_path,
                                   tvt.original_to_versioned_path(input_path))


            lsuffix = "_original"
            rsuffix = f"_{tvt.version_name}"
            joint_df = fpt_df.set_index("original_file_path").join(
                tvt_df.set_index("original_file_path"),
                lsuffix=lsuffix, rsuffix=rsuffix)

            assert not np.any(joint_df.applymap(lambda x: x is None))

            for column in [c for c in joint_df.columns.values if lsuffix in c]:
                if column.replace(lsuffix, "") in fpt.indices:
                    continue
                version_column = column.replace(lsuffix, rsuffix)
                if not column.startswith("corpus"):
                    assert np.all(joint_df[column] == joint_df[version_column]) \
                           or column.startswith("row_created") \
                           or column.startswith("row_update"), \
                        f"Columns {column} and {version_column} differ: " \
                        f"{joint_df[joint_df[column] != joint_df[version_column]][[column, version_column]].iloc[0]}"


if __name__ == '__main__':
    unittest.main()
