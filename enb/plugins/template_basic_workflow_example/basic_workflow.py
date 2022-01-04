#!/usr/bin/env python3
"""Example showing the basic workflow of the ``enb`` library in a simple ATable subclass.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/09/13"

import os
import glob
import shutil
import enb.atable
import enb.aanalysis


class WikiTable(enb.atable.ATable):
    # Methods that start with column_ are automatically recognized as such.
    # They just need to return the intended value.
    def column_line_count(self, file_path, row):
        with open(file_path, encoding="utf-8", mode="r") as input_file:
            return sum(1 for line in input_file)

    # More information about a column can be provided
    # Several column names and/or enb.atable.ColumnProperties instances
    # can also be passed as *args to the decorator to define multiple columns
    @enb.atable.column_function(
        enb.atable.ColumnProperties(name="word_count", label="Word count", plot_min=0),
        "status")
    def set_word_count(self, file_path, row):
        with open(file_path, mode="r", encoding="utf-8") as input_file:
            contents = input_file.read()
            row["word_count"] = len(contents.split())
            row["status"] = "dead" if "death_place" in contents.lower() else "alive"


def main():
    # Step 1: get a list of all data samples
    sample_paths = glob.glob("./data/wiki/*.txt")

    # Step 2: run experiment to gather data
    table = WikiTable() # csv_support_path="persistence_basic_workflow.csv")
    result_df = table.get_df(target_indices=sample_paths)

    # Show part of the returned table for the documentation.
    print(result_df[["index", "line_count"]])


    # Step 3: plot results
    #   Distribution of line counts
    analysis_df = enb.aanalysis.ScalarNumericAnalyzer().get_df(
        full_df=result_df,
        target_columns=["line_count"])
    os.makedirs("analysis", exist_ok=True)
    analysis_df.to_csv("analysis/line_count_analysis.csv")

    #   Distribution of word count grouped by status
    analysis_df = enb.aanalysis.ScalarNumericAnalyzer().get_df(
        full_df=result_df,
        target_columns=["word_count"],
        group_by="status",
        show_global=False)
    os.makedirs("analysis", exist_ok=True)
    analysis_df.to_csv("analysis/word_count_analysis.csv")

    #   Scatter plot: line count vs word count
    enb.aanalysis.TwoNumericAnalyzer().get_df(
        full_df=result_df,
        target_columns=[("line_count", "word_count")],
        column_to_properties=table.column_to_properties)


if __name__ == '__main__':
    main()
