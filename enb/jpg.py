#!/usr/bin/env python3
"""JPEG manipulation (e.g., curation) tools.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2023/11/09"

import enb

class JPEGCurationTable(enb.png.PNGCurationTable):
    """Given a directory tree containing JPEG images, copy those images into
    a new directory tree in raw BSQ format adding geometry information tags to
    the output names recognized by `enb.isets.load_array_bsq`.
    """
    dataset_files_extension = "jpg"
