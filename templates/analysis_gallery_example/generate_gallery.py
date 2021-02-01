#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the gallery of analyzers
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "01/02/2021"

import os
import subprocess
import glob
import pandas as pd

import enb.config

options = enb.config.get_options()

import enb.aanalysis
import enb.ray_cluster

if __name__ == '__main__':
    enb.ray_cluster.init_ray()

    options.plot_dir = os.path.join(os.path.dirname(__file__), "pdf_plots")
    df = pd.read_csv("iris_dataset.csv")

    # Scalar and scatter plots
    for cls, target_columns, extra_kwargs in [
        (enb.aanalysis.ScalarDistributionAnalyzer, ["sepal_length", "sepal_width"], {"adjust_height": True}),
        (enb.aanalysis.TwoColumnScatterAnalyzer, [("sepal_length", "petal_width")], {"show_global": False}),
    ]:
        for group_by in [None, "class"]:
            dir = os.path.join(options.plot_dir, f"groupby_{group_by}" if group_by else "", cls.__name__)
            os.makedirs(dir, exist_ok=True)
            analyzer = cls()
            analyzer.analyze_df(full_df=df, target_columns=target_columns,
                                group_by=group_by, output_plot_dir=dir, **extra_kwargs)

    # Make a png mirror of the PDF files
    for pdf_path in glob.glob(os.path.join(options.plot_dir, "**", "*.pdf"), recursive=True):
        png_path = pdf_path.replace("pdf_plots", "png_plots").replace(".pdf", ".png")
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        invocation = f"convert -density 400 {pdf_path} {png_path}"
        status, output = subprocess.getstatusoutput(invocation)
        if status != 0:
            raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                status, invocation, output))