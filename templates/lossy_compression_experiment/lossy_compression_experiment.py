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
import plugin_mcalic.mcalic_codecs
import plugin_hevc.hevc_codec

if __name__ == '__main__':
    # options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "landsat")
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./data/8bit_images")

    all_codecs = []
    all_families = []
    # A family is a set of related tasks
    jpeg_ls_family = enb.aanalysis.TaskFamily(label="JPEG-LS")
    for c in (plugin_jpeg.jpeg_codecs.JPEG_LS(max_error=m) for m in range(5)):
        all_codecs.append(c)
        jpeg_ls_family.add_task(c.name, f"{c.label} PAE {c.param_dict['m']}")
    all_families.append(jpeg_ls_family)

    # One can add as many families as lines should be depicted
    # mcalic_family = enb.aanalysis.TaskFamily(label="M-CALIC")
    # for c in (plugin_mcalic.mcalic_codecs.MCALIC_Magli(max_error=m) for m in range(5)):
    #     all_codecs.append(c)
    #     mcalic_family.add_task(c.name, f"{c.label} PAE {c.param_dict['max_error']}")
    # all_families.append(mcalic_family)

    hevc_family = enb.aanalysis.TaskFamily(label="HEVC")
    for c in (plugin_hevc.hevc_codec.HEVC_lossy(qp=m, config_path="./plugin_hevc/hevc_lossy_400_ver2.cfg") for m in range(4,30,4)):
        all_codecs.append(c)
        hevc_family.add_task(c.name, c.label)
    all_families.append(hevc_family)

    # One can easily define pretty plot labels for all codecs individually, even when
    # one or more parameter families are used
    label_by_group_name = dict()
    for family in all_families:
        label_by_group_name.update(family.name_to_label)

    # Run experiment and produce figures
    exp = enb.icompression.LossyCompressionExperiment(codecs=all_codecs)
    df = exp.get_df()
    enb.aanalysis.ScalarDistributionAnalyzer().analyze_df(
        full_df=df,
        target_columns=["bpppc", "pae", "compression_efficiency_2byte_entropy", "psnr_dr"],
        output_csv_file="analysis.csv",
        column_to_properties=exp.joined_column_to_properties,
        group_by="task_name",
        adjust_height=True,
        y_labels_by_group_name=label_by_group_name,
    )
    enb.aanalysis.TwoColumnLineAnalyzer().analyze_df(
        full_df=df,
        target_columns=[("bpppc", "pae"), ("bpppc", "psnr_dr")],
        column_to_properties=exp.joined_column_to_properties,
        show_markers=True,
        show_h_range_bar=True,
        show_h_std_bar=True,
        group_by=all_families,
        legend_column_count=2)

    # pdf to high-def PNG
    for pdf_path in glob.glob(os.path.join(os.path.abspath(os.path.dirname(__file__)), "plots", "**", "*.pdf"), recursive=True):
        output_dir = os.path.dirname(os.path.abspath(pdf_path)).replace(os.path.abspath("./plots"), "./png_plots")
        os.makedirs(output_dir, exist_ok=True)
        png_path = os.path.join(output_dir, os.path.basename(pdf_path).replace(".pdf", ".png"))
        invocation = f"convert -density 400 {pdf_path} {png_path}"
        status, output = subprocess.getstatusoutput(invocation)
        if status != 0:
            raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                status, invocation, output))