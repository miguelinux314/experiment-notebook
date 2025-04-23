#!/usr/bin/env python3
"""Curate a dir of PPM files into another dir with their raw BSQ equivalents, 
using names that reflect their geometry.  
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2025/04/23"

import argparse
import os
import sys

import enb
from enb.compression.pgm import PPMCurationTable


def ppm_to_raw(ppm_dir_path: str | os.PathLike, raw_dir_path: str | os.PathLike):
    PPMCurationTable(original_base_dir=ppm_dir_path,
                     version_base_dir=raw_dir_path,
                     csv_support_path=None).get_df()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PPM to raw BSQ images')
    parser.add_argument("ppm_dir", type=str, help="Directory with the PPM samples. Must exist.")
    parser.add_argument("raw_dir", type=str, help="Directory where the raw BSQ images are stored.")
    opts = parser.parse_args()

    if not os.path.isdir(opts.ppm_dir):
        enb.logger.error(f"PPM dir {opts.ppm_dir} does not exist.")
        sys.exit(1)
    if os.path.exists(opts.raw_dir):
        enb.logger.error(f"Raw BSQ dir {opts.raw_dir} already exists. Refusing to overwrite.")
        sys.exit(1)

    ppm_to_raw(ppm_dir_path=opts.ppm_dir, raw_dir_path=opts.raw_dir)
