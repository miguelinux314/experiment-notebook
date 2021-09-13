#!/usr/bin/env python3
"""Snippets testing the aanalysis tools
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/21"

import os
import pandas as pd
import string
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

    # Test numeric value dict plotting
    full_df = pd.DataFrame(columns=["dicts", "i"])
    for i in range(10):
        full_df.loc[len(full_df)] = pd.Series(dict(dicts=dict(a=i, b=10 * i, c=i ** 2 - 2 * i + 3, i=i), i=i))
    for i in range(10):
        full_df.loc[len(full_df)] = pd.Series(dict(dicts=dict(a=i, b=10 * i, i=i), i=i))
    for i in range(10):
        full_df.loc[len(full_df)] = pd.Series(dict(dicts=dict(a=i, i=i), i=i))
    for i in range(10):
        full_df.loc[len(full_df)] = pd.Series(dict(dicts=dict(a=i, c=0, i=i), i=i))

    df = enb.aanalysis.DictNumericAnalyzer().get_df(
        full_df=full_df, target_columns=["dicts"],
        group_by="i")


    def example_combiner_function(d):
        a = d["a"] if "a" in d else 0
        b = d["b"] if "b" in d else 0
        c = d["c"] if "c" in d else 0
        i = d["i"] if "i" in d else 0
        return dict(a_and_b=a + b, b_minus_c=b - c, i=i)


    df = enb.aanalysis.DictNumericAnalyzer(combine_keys_callable=example_combiner_function).get_df(
        full_df=full_df, target_columns=["dicts"])
