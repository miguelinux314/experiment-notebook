#!/usr/bin/env python3
"""Unit tests for the aatable classes
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/05/07"

import os
import unittest
import pandas as pd
import tempfile
import enb


class TestScalarToScalar(unittest.TestCase):
    """Test the plotting of scalar to scalar dictionaries.
    """
    def test_scalar_to_scalar(self):
        df = pd.DataFrame(columns=["dicts"])
        for i in range(10):
            df.loc[len(df)] = pd.Series(dict(dicts=dict(a=i, b=10 * i, c=i ** 2 - 2 * i + 3)))
        for i in range(10):
            df.loc[len(df)] = pd.Series(dict(dicts=dict(a=i, b=10 * i)))
        for i in range(10):
            df.loc[len(df)] = pd.Series(dict(dicts=dict(a=i)))
        for i in range(10):
            df.loc[len(df)] = pd.Series(dict(dicts=dict(a=i, c=0)))

        with tempfile.TemporaryDirectory() as tmp_dir:
            analyzer = enb.aanalysis.ScalarDictAnalyzer()
            analyzer.analyze_df(
                full_df=df,
                target_columns=["dicts"],
                column_to_properties={"dicts": enb.atable.ColumnProperties(
                    "dicts", has_dict_values=True)},
                output_csv_file=os.path.join(tmp_dir, "ignore.csv"),
                output_plot_dir=tmp_dir)


if __name__ == "__main__":
    unittest.main()