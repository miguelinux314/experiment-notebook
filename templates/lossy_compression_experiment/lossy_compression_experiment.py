#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template example of a lossy image compression experiment.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "02/02/2021"

import os
import glob
import subprocess
import numpy as np
from enb.config import options

import enb.icompression
import enb.aanalysis

import plugin_jpeg.jpeg_codecs
import plugin_hevc.hevc_codec
import plugin_kakadu.kakadu_codec


def get_families_and_codecs():
    all_codecs = []
    all_families = []
    # A family is a set of related tasks
    # jpeg_ls_family = enb.aanalysis.TaskFamily(label="JPEG-LS")
    # for c in (plugin_jpeg.jpeg_codecs.JPEG_LS(max_error=m) for m in range(1, 6)):
    #     all_codecs.append(c)
    #     jpeg_ls_family.add_task(c.name, f"{c.label} PAE {c.param_dict['m']}")
    # all_families.append(jpeg_ls_family)
    #
    # hevc_qp_family = enb.aanalysis.TaskFamily(label="HEVC QP")
    # for c in (plugin_hevc.hevc_codec.HEVC_lossy(qp=qp) for qp in range(1, 51, 5)):
    #     all_codecs.append(c)
    #     hevc_qp_family.add_task(c.name, c.label)
    # all_families.append(hevc_qp_family)

    # kakadu_br_family = enb.aanalysis.TaskFamily(label="Kakadu BR")
    # for c in (plugin_kakadu.kakadu_codec.Kakadu(bit_rate=br) for br in np.linspace(0.1, 5, 10)):
    #     all_codecs.append(c)
    #     kakadu_br_family.add_task(c.name, c.label)
    # all_families.append(kakadu_br_family)

    kakadu_qf_family = enb.aanalysis.TaskFamily(label="Kakadu QF")
    for c in (plugin_kakadu.kakadu_codec.Kakadu(quality_factor=qf) for qf in range(0, 100, 20)):
        all_codecs.append(c)
        kakadu_qf_family.add_task(c.name, c.label)
    all_families.append(kakadu_qf_family)

    kakadu_psnr_family = enb.aanalysis.TaskFamily(label="Kakadu PSNR")
    for c in (plugin_kakadu.kakadu_codec.Kakadu(psnr=psnr) for psnr in range(40, 60, 10)):
        all_codecs.append(c)
        kakadu_psnr_family.add_task(c.name, c.label)
    all_families.append(kakadu_psnr_family)

    kakadu_mct_family = enb.aanalysis.TaskFamily(label="Kakadu MCT")
    c = plugin_kakadu.kakadu_codec.Kakadu_MCT(lossless=False)
    all_codecs.append(c)
    kakadu_mct_family.add_task(c.name, c.label)
    all_families.append(kakadu_mct_family)

    return all_families, all_codecs


if __name__ == '__main__':
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./data/8bit_images")

    all_families, all_codecs = get_families_and_codecs()

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
        target_columns=["bpppc", "pae", "compression_efficiency_1byte_entropy", "psnr_dr"],
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
