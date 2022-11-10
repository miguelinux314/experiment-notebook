#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template and use example for the enb.sets.FileVersionTable class.

Takes a set of *.txt files and performs a simplistic normalization.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "26/10/2022"

import enb


class TextNormalizationTable(enb.sets.FileVersionTable):
    dataset_files_extension = "txt"

    def version(self, input_path, output_path, row):
        with open(input_path, "r") as input_file, open(output_path, "w") as output_file:
            contents = input_file.read()
            output_file.write("\n".join(l.lower().strip() for l in contents.splitlines()))


if __name__ == '__main__':
    tnt = TextNormalizationTable(original_base_dir="original_data", version_base_dir="versioned_data",
                                 csv_support_path="")
    tnt.get_df()