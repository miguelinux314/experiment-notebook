#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for sets.py
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "05/10/2019"

import unittest
import tempfile
import glob
import os
import numpy as np
import shutil

import test_all
import enb.sets as sets

target_indices = [sets.get_canonical_path(f) for f in glob.glob("**/*.py", recursive=False)
                  if os.path.isfile(f) and os.path.getsize(f)]



class TestSets(unittest.TestCase):

    def test_file_properties(self):
        """Test that file properties are correctly obtained and retrieved.
        """
        for parallel in [True, False]:
            # dataset_df = get_result_df()
            tmp_fid, tmp_path = tempfile.mkstemp(suffix=".csv")
            try:
                dataset_properties_table = sets.FilePropertiesTable(csv_support_path=tmp_path)

                # Attempt loading from an empty file, verify it is empty
                empty_property_table = dataset_properties_table.get_df(
                    target_indices=target_indices, fill=False, parallel_row_processing=parallel)
                assert len(empty_property_table) == len(target_indices)

                assert np.all(empty_property_table[[
                    c for c in empty_property_table.columns
                    if c not in dataset_properties_table.indices]].applymap(lambda x: x is None)), \
                    empty_property_table

                # Run the actual loading sequence
                dataset_properties_df = dataset_properties_table.get_df(
                    target_indices=target_indices, parallel_row_processing=parallel)

                # Obtain again, forcing load from the temporary file
                new_df = dataset_properties_table.get_df(
                    target_indices=target_indices,
                    fill=False, overwrite=False, parallel_row_processing=parallel)
                assert (dataset_properties_df.columns == new_df.columns).all()
                for c in dataset_properties_df.columns:
                    if not (dataset_properties_df[c] == new_df[c]).all():
                        # Floating point values might be unstable
                        try:
                            assert np.abs(dataset_properties_df[c] - new_df[c]).max() < 1e-12
                        except TypeError:
                            # Stability within dictionaries is not verified,
                            # but only dictionaries can raise this error
                            assert (dataset_properties_df[c].apply(lambda c: isinstance(c, dict))).all()

            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    def test_trivial_version_table(self):
        """Test versioning with a table that simply copies the original file.
        """

        tmp_dir = tempfile.mkdtemp()
        try:
            class TrivialVersionTable(sets.FileVersionTable, sets.FilePropertiesTable):
                """Trivial FileVersionTable that makes an identical copy of the original
                """
                version_name = "TrivialCopy"

                def __init__(self, original_properties_table):
                    super().__init__(version_name=self.version_name,
                                     original_base_dir=".",
                                     original_properties_table=original_properties_table,
                                     version_base_dir=tmp_dir)

                def version(self, input_path, output_path, row):
                    shutil.copy(input_path, output_path)

            fpt = sets.FilePropertiesTable()
            fpt_df = fpt.get_df(target_indices=target_indices)
            fpt_df["original_file_path"] = fpt_df["file_path"]

            tvt = TrivialVersionTable(original_properties_table=fpt)
            tvt_df = tvt.get_df(target_indices=target_indices)

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
                    assert np.all(joint_df[column] == joint_df[version_column]), \
                        f"Columns {column} and {version_column} differ"

        finally:
            shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    unittest.main()