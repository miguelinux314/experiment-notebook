#!/usr/bin/env python3
"""Snippets testing the aanalysis tools
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/21"

import os
import pandas as pd
import enb

if __name__ == "__main__":
    full_df = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "iris_dataset.csv"))
    all_columns = [c for c in full_df.columns if any(s in c for s in ("width", "length"))]
    combine_groups = True

    for group_by in [None, "class"]:
        # Test the scalar numeric analyzer
        analyzer = enb.aanalysis.ScalarNumericAnalyzer()
        analyzer.combine_groups = combine_groups
        analysis_df = analyzer.get_df(
            full_df=full_df, group_by=group_by,
            target_columns=all_columns)

        # Test the two-scalar numeric analyzer
        analyzer = enb.aanalysis.TwoNumericAnalyzer()
        analyzer.combine_groups = combine_groups
        analysis_df = analyzer.get_df(
            full_df=full_df, group_by=group_by,
            target_columns=[(all_columns[0], c) for c in all_columns[1:]])
