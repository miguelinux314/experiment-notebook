#!/usr/bin/env python3
"""Example showing the basic workflow of the ``enb`` library.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/09/13"

import glob
import enb.atable
import enb.aanalysis


class WikiAnalysis(enb.atable.ATable):
    # Methods that start with column_ are automatically recognized as such.
    # They just need to return the intended value.
    def column_line_count(self, file_path, row):
        with open(file_path, "r") as input_file:
            return sum(1 for line in input_file)

    # More information about a column can be provided
    # Several column names and/or enb.atable.ColumnProperties instances
    # can also be passed as *args to the decorator to define multiple columns
    @enb.atable.column_function(
        enb.atable.ColumnProperties(name="word_count", label="Word count", plot_min=0),
        "status")
    def set_word_count(self, file_path, row):
        with open(file_path, "r") as input_file:
            row["word_count"] = len(input_file.read().split())
            row["status"] = "dead" if "death_place" in input_file.read() else "alive"


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
