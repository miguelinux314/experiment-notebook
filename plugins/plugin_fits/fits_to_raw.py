  
##!/usr/bin/python
# -*- coding: utf-8 -*-

import fitsio
import sets
import glob
from astropy.io import fits
import os
import isets

class FitsVersionTable(sets.FileVersionTable, sets.FilePropertiesTable):
    """Read FITS files and convert them to raw files, sorting them by type (integer or float)
    and by bits per pixel
    """
    version_name = "FitsToRaw"
    
    def __init__(self, original_properties_table):
        tmp_dir='tmp_dir'
        super().__init__(version_name=self.fits_to_raw,
                         original_base_dir=".",
                         original_properties_table=original_properties_table,
                         version_base_dir=tmp_dir)

    def fits_to_raw(self, input_path, output_path):
        hdul = fits.open('CALIFAIC0159.V500.rscube.fits')
        header = hdul[0].header #change in case fits image extension does not correspond to 0
        if header['NAXIS'] == 2:
    		    if header['BITPIX'] < 0:
    			      label = '-f{header['BITPIX']*-1}-{header['NAXIS1']}x{header['NAXIS2']}'
    			      label2= 'float{header['BITPIX']*-1}'
            elif header['BITPIX'] > 0:
    		        label = '-i{header['BITPIX']}-{header['NAXIS1']}x{header['NAXIS2']}'
    			      label2= 'uint{header['BITPIX']}'
        elif header['NAXIS'] == 3:
    		    if header['BITPIX'] < 0:
    			      label ='-f{header['BITPIX']*-1}-{header['NAXIS1']}x{header['NAXIS2']}x{header['NAXIS3']}'
    			      label2= 'float{header['BITPIX']*-1}'
    		    elif header['BITPIX'] >0:
    			      label = '-i{header['BITPIX']}-{header['NAXIS1']}x{header['NAXIS2']}x{header['NAXIS3']}'
    			      label2= 'uint{header['BITPIX']}'
        
        data = fitsio.read('{input_path}')
	path=os.path.join('', '{label2}')
        if not os.path.exists(path):
    		    os.makedirs(path, exist_ok = True)
        raw=isets.dump_array_bsq(data,'{path}raw{output_path}{label}.raw', mode="wb", dtype=label2 ) 
        
if __name__ == "__main__":
    target_indices=glob.glob('*.fits') #read fits files
	  for i in range(len(target_indices)):
		    FitsVersionTable.fits_to_raw(target_indices[i], target_indices[i], target_indices[i])
    
