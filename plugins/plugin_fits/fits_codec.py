#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import with_statement, print_function
import sys, os
import tempfile
import warnings
from numpy import arange, array
from pkg_resources import resource_filename
import fitsio
from fitsio import FITS, FITSHDR
#from ._fitsio_wrap import cfitsio_use_standard_strings
import sets
import os
from enb import icompression
from enb.config import get_options




class TrivialVersionTable(sets.FileVersionTable, sets.FilePropertiesTable):
    """Trivial FileVersionTable that makes an identical copy of the original
    """
    version_name = "TrivialCopy"

    def __init__(self, original_properties_table):
        super().__init__(version_name=self.version_name,
                         original_base_dir=".",
                         original_properties_table=original_properties_table,
                         version_base_dir=tmp_dir)

    def version(self, input_path, output_path, row):
        shutil.copy(input_path, output_path)

fpt = sets.FilePropertiesTable()
fpt_df = fpt.get_df(target_indices=target_indices)
fpt_df["original_file_path"] = fpt_df["file_path"]

tvt = TrivialVersionTable(original_properties_table=fpt)
tvt_df = tvt.get_df(target_indices=target_indices)


#filename='./CALIFAIC0159.V500.rscube.fits' #FLOAT
#data= fitsio.read(filename)

#fitsio.write('CAL_g.fit', data, compress='gzip', qlevel=None)
