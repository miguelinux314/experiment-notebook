#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template example of a lossy image compression experiment.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "02/02/2021"

import os
import glob
import subprocess
from enb.config import get_options

options = get_options()

import enb.icompression
import enb.aanalysis

import plugin_jpeg.jpeg_codecs

if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "landsat")

    all_codecs = []
    all_families = []

    # A family is a set of related tasks
    jpeg_ls_family = enb.aanalysis.TaskFamily(label="JPEG-LS")
    for c in (plugin_jpeg.jpeg_codecs.JPEG_LS(max_error=m) for m in range(5)):
        all_codecs.append(c)
        jpeg_ls_family.add_task_name(c.name)
    all_families.append(jpeg_ls_family)

    # Run experiment and produce figures
    exp = enb.icompression.LossyCompressionExperiment(codecs=all_codecs)
    df = exp.get_df()
    enb.aanalysis.TwoColumnLineAnalyzer().analyze_df(
        full_df=df,
        target_columns=[("pae", "psnr_dr"), ("bpppc", "pae"), ("bpppc", "psnr_dr")],
        column_to_properties=exp.joined_column_to_properties,
        group_by=[jpeg_ls_family])

    # pdf to high-def PNG
    for pdf_path in glob.glob(os.path.join(os.path.dirname(__file__), "plots", "**", "*.pdf"), recursive=True):
        output_dir = os.path.abspath(pdf_path).replace(os.path.abspath("./plots"), "./png_plots")
        os.makedirs(output_dir, exist_ok=True)
        png_path = os.path.join(output_dir, os.path.basename(pdf_path).replace(".pdf", ".png"))
        invocation = f"convert -density 400 {pdf_path} {png_path}"
        status, output = subprocess.getstatusoutput(invocation)
        if status != 0:
            raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                status, invocation, output))