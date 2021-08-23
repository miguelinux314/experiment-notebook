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

    analyzer = enb.aanalysis.ScalarValueAnalyzer()

    analysis_df = analyzer.get_df(full_df=full_df, group_by="class")
