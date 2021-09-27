#!/usr/bin/env python3
"""Generate the gallery of analyzers
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/02/01"

import os
import subprocess
import glob
import pandas as pd
import ast

import enb.config
import enb.experiment

options = enb.config.get_options()

import enb.aanalysis
import enb.icompression
import enb.ray_cluster

if __name__ == '__main__':
    enb.ray_cluster.init_ray()

    # # Scalar and scatter plots - using the Iris flower dataset
    input_csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input_csv")
    options.plot_dir = os.path.join(os.path.dirname(__file__), "pdf_plots")
    iris_df = pd.read_csv(os.path.join(input_csv_dir, "iris_dataset.csv"))
    for cls, target_columns, extra_kwargs in [
        (enb.aanalysis.ScalarDistributionAnalyzer, ["sepal_length", "sepal_width"], {"adjust_height": True}),
        (enb.aanalysis.TwoColumnScatterAnalyzer, [("sepal_length", "petal_width")], {"show_global": False}),
    ]:
        for group_by in [None, "class"]:
            dir = os.path.join(options.plot_dir, f"groupby_{group_by}" if group_by else "", cls.__name__)
            os.makedirs(dir, exist_ok=True)
            analyzer = cls()
            analyzer.analyze_df(full_df=iris_df, target_columns=target_columns,
                                group_by=group_by, output_plot_dir=dir, **extra_kwargs)

    # Line plots - using a real compression example, reusing persistence data
    base_dir = os.path.join(input_csv_dir, "lossy_persistence_example")
    csv_path = os.path.join(base_dir, "CCSDS123LossyCompressionExperiment_persistence.csv")
    lossy_df = pd.read_csv(csv_path)
    ## Define families of tasks
    all_task_names = lossy_df["task_name"].unique()
    task_families = [
        enb.experiment.TaskFamily(label=label, task_names=task_names)
        for label, task_names in [
            ("CCSDS 123 Hybrid",
             [t for t in all_task_names if "CCSDS_LCNL_AdjustedGreenBook" in t and "entropy_coder_type=1" in t]),
            ("JPEG_LS", [t for t in all_task_names if "JPEG_LS" in t]),
            ("M-CALIC", [t for t in all_task_names if "MCALIC_Magli" in t])
        ]
    ]
    ## Get scatter plots
    enb.aanalysis.TwoColumnLineAnalyzer().analyze_df(
        full_df=lossy_df,
        target_columns=[("bpppc", "pae"), ("bpppc", "psnr_dr")],
        column_to_properties=enb.icompression.LossyCompressionExperiment.column_to_properties,
        group_by=task_families,
        show_global=False,
        show_markers=True)

    # Dictionary value plotting
    ## Use HEVC mode selection results
    hevc_df = pd.read_csv(os.path.join(input_csv_dir, "hevc_frame_prediction.csv"))
    ## These two lines are automatically applied by get_df of the appropriate experiment
    hevc_df["mode_count"] = hevc_df["mode_count"].apply(ast.literal_eval)
    hevc_df["block_size"] = hevc_df["param_dict"].apply(lambda d: f"Block size {ast.literal_eval(d)['block_size']}")
    column_to_properties = dict(mode_count=enb.atable.ColumnProperties(
        name="mode_count", label="HEVC intra prediction", has_dict_values=True,
        plot_min=0, plot_max=None))
    # Plot the data
    for combine_keys in [None, "histogram40col", "histogram8col"]:
        enb.aanalysis.ScalarDictAnalyzer().analyze_df(
            full_df=hevc_df,
            column_to_properties=column_to_properties,
            target_columns="mode_count",
            group_name_order=[f"Block size {2 ** i}" for i in range(1, 7)],
            combine_keys=combine_keys,
            show_global=False,
            output_plot_dir=os.path.join(options.plot_dir, f"combine_keys_{combine_keys}"),
            group_by="block_size", show_h_bars=True,
            show_std_band=combine_keys is not None,
            show_std_bar=False,
            global_y_label="CUs using this mode")

    # Make a png mirror of all the PDF files (not within enb, yet)
    for pdf_path in glob.glob(os.path.join(options.plot_dir, "**", "*.pdf"), recursive=True):
        png_path = pdf_path.replace("pdf_plots", "png_plots").replace(".pdf", ".png")
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        invocation = f"convert -density 400 {pdf_path} {png_path}"
        status, output = subprocess.getstatusoutput(invocation)
        if status != 0:
            raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                status, invocation, output))
