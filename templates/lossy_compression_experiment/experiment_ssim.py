#!/usr/bin/env python

import os
import glob
import subprocess
from enb.config import options

import enb.icompression
import enb.aanalysis

import lossy_compression_experiment

if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "8bit_images")

    all_families, all_codecs = lossy_compression_experiment.get_families_and_codecs()

    # One can easily define pretty plot labels for all codecs individually, even when
    # one or more parameter families are used
    label_by_group_name = dict()
    for family in all_families:
        label_by_group_name.update(family.name_to_label)

    # Run experiment and produce figures
    exp = enb.icompression.StructuralSimilarity(codecs=all_codecs)
    df = exp.get_df()
    enb.aanalysis.ScalarDistributionAnalyzer().analyze_df(
        full_df=df,
        target_columns=["ssim", "ms_ssim"],
        output_csv_file="analysis.csv",
        column_to_properties=exp.joined_column_to_properties,
        group_by="task_name",
        adjust_height=True,
        y_labels_by_group_name=label_by_group_name,
    )
    enb.aanalysis.TwoColumnLineAnalyzer().analyze_df(
        full_df=df,
        target_columns=[("bpppc", "ssim"), ("bpppc", "ms_ssim")],
        column_to_properties=exp.joined_column_to_properties,
        show_markers=True,
        show_h_range_bar=True,
        show_h_std_bar=True,
        group_by=all_families,
        legend_column_count=2)

    # pdf to high-def PNG
    for pdf_path in glob.glob(os.path.join(os.path.abspath(os.path.dirname(__file__)), "plots", "**", "*.pdf"),
                              recursive=True):
        output_dir = os.path.dirname(os.path.abspath(pdf_path)).replace(os.path.abspath("./plots"), "./png_plots")
        os.makedirs(output_dir, exist_ok=True)
        png_path = os.path.join(output_dir, os.path.basename(pdf_path).replace(".pdf", ".png"))
        invocation = f"convert -density 400 {pdf_path} {png_path}"
        status, output = subprocess.getstatusoutput(invocation)
        if status != 0:
            raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                status, invocation, output))
