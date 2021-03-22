##!/usr/bin/python
# -*- coding: utf-8 -*-

import fitsio
import sets
import glob
from astropy.io import fits
import os


class FitsVersionTable(sets.FileVersionTable, sets.FilePropertiesTable):
    """Fits FileVersionTable that makes an identical copy of the original
    """
    version_name = "TrivialCopy"
    
    def __init__(self, original_properties_table):
    	tmp_dir='tmp_dir'
    	super().__init__(version_name=self.version_name,
                         original_base_dir=".",
                         original_properties_table=original_properties_table,
                         version_base_dir=tmp_dir)

    def version(self, input_path, output_path):
    	hdul = fits.open(input_path)
    	header = hdul[0].header
    	if header['NAXIS'] == 2:
    		if header['BITPIX'] < 0:
    			label = '_f'+ str(header['BITPIX']*-1)+'-'+ str(header['NAXIS1'])+'x'+ str(header['NAXIS2'])
    			label2= 'float'+ str(header['BITPIX']*-1)
    		elif header['BITPIX'] > 0:
    			label = '_i'+ str(header['BITPIX'])+'-'+str(header['NAXIS1'])+'x'+ str(header['NAXIS2'])
    			label2= 'uint'+ str(header['BITPIX'])
    	elif header['NAXIS'] == 3:
    		if header['BITPIX'] < 0:
    			label ='_f'+ str(header['BITPIX']*-1)+'-'+str(header['NAXIS1'])+'x'+ str(header['NAXIS2'])+'x'+ str(header['NAXIS3'])
    			label2= 'float'+ str(header['BITPIX']*-1)
    		elif header['BITPIX'] >0:
    			label = '_i'+ str(header['BITPIX'])+'-'+str(header['NAXIS1'])+'x'+ str(header['NAXIS2'])+'x'+ str(header['NAXIS3'])
    			label2= 'uint'+ str(header['BITPIX'])
    	filename=input_path
    	data = fitsio.read(filename)
	os.mkdir('./'+label2)
    	raw=FitsVersionTable.dump_array_bsq(data, label2+'/'+'raw'+output_path+label+'.raw', mode="wb", dtype=label2 ) #>f means big-endian single-precision float, float64 or uint16 are also valid formats
    	
            

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
   
    	
 	
if __name__ == "__main__":
	target_indices='.fits' #file to read
	FitsVersionTable.version(input_path, input_path, output_path)


