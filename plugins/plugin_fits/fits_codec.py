##!/usr/bin/python
# -*- coding: utf-8 -*-

import fitsio
import glob
from astropy.io import fits
import os
import isets
import sets

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
    	hdul = fits.open('CALIFAIC0159.V500.rscube.fits')
    	header = hdul[0].header #change in case fits image extension does not correspond to 0
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
    	if not os.path.exists(label2):
    		os.makedirs(label2)
    	raw=isets.dump_array_bsq(data,label2+'/'+'raw'+output_path+label+'.raw', mode="wb", dtype=label2 ) 

if __name__ == "__main__":
	target_indices=glob.glob('*.fits') #read fits files
	for i in range(len(target_indices)):
		FitsVersionTable.version(target_indices[i], target_indices[i], target_indices[i])

