#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lossless compression experiment example (uses JPEG-LS)
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "25/11/2020"

import os

from enb.config import get_options

options = get_options(from_main=False)

from enb import icompression
from enb import aanalysis
import plugin_emporda.EmpordaWrapper

if __name__ == '__main__':
    # Setup global options
    options.base_dataset_dir = "./data"

    # Define list of codecs
    codecs = []
    codecs.append(plugin_emporda.EmpordaWrapper.EmpordaWrapper())

    # Create experiment
    exp = icompression.LosslessCompressionExperiment(codecs=codecs)

    # Generate pandas dataframe with results
    df = exp.get_df(
        parallel_row_processing=not options.sequential,
        overwrite=options.force > 0)

    # Plot some results
    analyzer = aanalysis.ScalarDistributionAnalyzer()
    target_columns = ["compression_ratio_dr", "bpppc", "compression_time_seconds"]
    analyzer.analyze_df(
        # Mandatory params
        full_df=df,                           # the dataframe produced by exp
        target_columns=target_columns,        # the list of ATable column names 
        # Optional params
        output_csv_file=os.path.join(         # save some statistics 
            options.analysis_dir, "lossless_compression_analysis.csv"),
        column_to_properties=exp.joined_column_to_properties, # contains plotting hints
        group_by="task_label",                # one can group by any column name                    
    )
