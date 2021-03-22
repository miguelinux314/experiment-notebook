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
import glob
import numpy as np




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

    def dump_array_bsq(array, file_or_path, mode="wb", dtype=None):
        """Dump an array indexed in [x,y,z] order into a band sequential (BSQ) ordering,
        i.e., the concatenation of each component (z axis), each component in raster
        order.
        :param file_or_path: It can be either a file-like object, or a string-like
        object. If it is a file, contents are writen without altering the file
        pointer beforehand. In this case, the file is not closed afterwards.
        If it is a string-like object, it will be interpreted
        as a file path, open as determined by the mode parameter.
        :param mode: if file_or_path is a path, the output file is opened in this mode
        :param dtype: if not None, the array is casted to this type before dumping
        :param force_big_endian: if True, a copy of the array is made and its bytes are swapped before outputting
        data to file. This parameter is ignored if dtype is provided.
        """
        try:
            assert not file_or_path.closed, f"Cannot dump to a closed file"
            open_here = False
        except AttributeError:
            file_or_path = open(file_or_path, mode)
            open_here = True

        if dtype is not None and array.dtype != dtype:
            array = array.astype(dtype)

        array = array.swapaxes(0, 2)
        array.tofile(file_or_path)

        if open_here:
            file_or_path.close()

target_indices=glob.glob('*.fits') #FITS files list

for i in range(len(target_indices)):
    hdul = fits.open(target_indices[i])
    header = hdul[0].header
    
    if header['NAXIS'] == 2:
		if header['BITPIX']<0:
			label=str(header['NAXIS1'])+str('x')+ str(header['NAXIS2'])+str('_f')+ str(header['BITPIX']*-1)
		elif header['BITPIX']>0:
			label=str(header['NAXIS1'])+str('x')+ str(header['NAXIS2'])+str('_i')+ str(header['BITPIX'])
	elif header['NAXIS']==3:
		if header['BITPIX']<0:
			label=str(header['NAXIS1'])+str('x')+ str(header['NAXIS2'])+str('x')+ str(header['NAXIS3'])+str('_f')+ str(header['BITPIX']*-1)
		elif header['BITPIX']>0:
			label=str(header['NAXIS1'])+str('x')+ str(header['NAXIS2'])+str('x')+ str(header['NAXIS3'])+str('_i')+ str(header['BITPIX'])
            
	filename=target_indices[i]
	data=fitsio.read(filename)
	#dump_array_bsq()
	
fpt = sets.FilePropertiesTable()
fpt_df = fpt.get_df(target_indices=target_indices)
fpt_df["original_file_path"] = fpt_df["file_path"]

tvt = TrivialVersionTable(original_properties_table=fpt)
tvt_df = tvt.get_df(target_indices=target_indices)

#fitsio.write('CAL_g.fit', data, compress='gzip', qlevel=None)
