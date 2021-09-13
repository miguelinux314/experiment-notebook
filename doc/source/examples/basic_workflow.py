#!/usr/bin/env python3
"""Example showing the basic workflow of the ``enb`` library.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/09/13"

import os
import glob
import enb.atable
import enb.aanalysis


class WikiAnalysis(enb.atable.ATable):
    @enb.atable.column_function("line_count")
    def set_line_count(self, file_path, row):
        with open(file_path, "r") as input_file:
            row["line_count"] = sum(1 for line in input_file)

    @enb.atable.column_function(enb.atable.ColumnProperties(
        name="word_count", label="Word count", plot_min=0))
    def set_line_count(self, file_path, row):
        with open(file_path, "r") as input_file:
            row[_column_name] = len(input_file.read().split())

    @enb.atable.column_function(enb.atable.ColumnProperties("status"))
    def set_dead_person(self, file_path, row):
        with open(file_path, "r") as input_file:
            row[_column_name] = "dead" if "death_place" in input_file.read() else "alive"


def main():

    # Step 1: get a list of all data samples
    sample_paths = glob.glob("./data/wiki/*.txt")

    # Step 2: run experiment to gather data
    table = WikiAnalysis(csv_support_path="persistence_basic_workflow.csv")
    result_df = table.get_df(target_indices=sample_paths)

    # Step 3: plot results
    #   Distribution of line counts
    scalar_analyzer = enb.aanalysis.ScalarDistributionAnalyzer()
    scalar_analyzer.analyze_df(
        full_df=result_df,
        target_columns=["line_count"],
        output_plot_dir="plots",
        output_csv_file="analysis/line_count_analysis.csv")
    #   Scatter plot: line count vs word count
    scatter_analyzer = enb.aanalysis.TwoColumnScatterAnalyzer()
    scatter_analyzer.analyze_df(
        full_df=result_df,
        target_columns=[("line_count", "word_count")],
        output_plot_dir="plots",
        column_to_properties=table.column_to_properties)
    #   Distribution of word count grouped by status
    scalar_analyzer.analyze_df(
        full_df=result_df,
        target_columns=["word_count"],
        group_by="status",
        output_plot_dir="plots",
        output_csv_file="analysis/word_count_analysis.csv")


if __name__ == '__main__':
    main()
