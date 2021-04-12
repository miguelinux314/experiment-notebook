  
##!/usr/bin/python
# -*- coding: utf-8 -*-

import numpy as np
import fitsio
import glob
from astropy.io import fits
import os 
import enb.sets as sets
import enb.isets as isets


class FitsVersionTable(sets.FileVersionTable, sets.FilePropertiesTable):
    "Read FITS files and convert them to raw files, sorting them by type (integer or float)	and by bits per pixel"
    version_name= "FitsToRaw"

    def __init__(self, original_properties_table):
        tmp_dir='tmp_dir'
        super().__init__(version_name=self.version,
			original_base_dir=".",
			original_properties_table=original_properties_table,
			version_base_dir=tmp_dir)
	
    def version(self, input_path, output_path):
        hdul = fits.open(input_path)
        header = hdul[0].header #change in case fits image extension does not correspond to 0
        data = fitsio.read(input_path)
        if header['NAXIS'] == 2:
            if header['BITPIX'] < 0:
                label = f'-f{header["BITPIX"]*-1}-{header["NAXIS1"]}x{header["NAXIS2"]}'
                label2 = f'float{header["BITPIX"]*-1}'
            if header['BITPIX'] > 0:
                label = f'-i{header["BITPIX"]}-{header["NAXIS1"]}x{header["NAXIS2"]}'
                label2 = f'uint{header["BITPIX"]}'
            data = np.expand_dims(data, axis=2)
        if header['NAXIS'] == 3:
            if header['BITPIX'] < 0:
                label = f'-f{header["BITPIX"]*-1}-{header["NAXIS1"]}x{header["NAXIS2"]}x{header["NAXIS3"]}'
                label2 = f'float{header["BITPIX"]*-1}'
            if header['BITPIX'] > 0:
                label = f'-i{header["BITPIX"]}-{header["NAXIS1"]}x{header["NAXIS2"]}x{header["NAXIS3"]}'
                label2 = f'uint{header["BITPIX"]}'

        path=os.path.join('', f'{label2}')
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        raw=isets.dump_array_bsq(data,f'{path}/{output_path}{label}.raw', mode="wb", dtype=f'{label2}')
		
if __name__ == "__main__":
    target_indices=glob.glob('*.fit*') #read fits files
    for i in range(len(target_indices)):
        FitsVersionTable.version(target_indices[i], target_indices[i], target_indices[i])
		
		
		
		
