#!/usr/bin/env python3
"""Curate a dir of PNG files into another dir with their raw BSQ equivalents, 
using names that reflect their geometry.  
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2025/04/23"

import argparse
import os
import sys

import enb
from enb.compression.png import PNGCurationTable


def png_to_raw(png_dir_path: str | os.PathLike, raw_dir_path: str | os.PathLike):
    PNGCurationTable(original_base_dir=png_dir_path,
                     version_base_dir=raw_dir_path,
                     csv_support_path=None).get_df()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PNG to raw BSQ images')
    parser.add_argument("png_dir", type=str, help="Directory with the PNG samples. Must exist.")
    parser.add_argument("raw_dir", type=str, help="Directory where the raw BSQ images are stored.")
    opts = parser.parse_args()

    if not os.path.isdir(opts.png_dir):
        enb.logger.error(f"PNG dir {opts.png_dir} does not exist.")
        sys.exit(1)
    if os.path.exists(opts.raw_dir):
        enb.logger.error(f"Raw BSQ dir {opts.raw_dir} already exists.")
        sys.exit(1)
        
    png_to_raw(png_dir_path=opts.png_dir, raw_dir_path=opts.raw_dir)
