import numpy as np
import fitsio
from astropy.io import fits
import os
import glob


class FitsToRaw:
    
    def Version():
        FITS=glob.glob('./fits_data/*.fit*')

        for i in range(len(FITS)):
            hdul = fits.open(FITS[i])
            print(FITS[i])
            hdul_index=0
            header = hdul[hdul_index].header 
            while hdul[hdul_index].header["NAXIS"] == 0:
                hdul_index += 1  
    
            if FITS[i].lower().endswith(".fit"):            
                input_ext = ".fit"
                dir_name=FITS[i].replace('./fits_data/','')
                file_name=dir_name.replace(input_ext,'')
            elif FITS[i].lower().endswith(".fits"):
                input_ext = ".fits"   
                dir_name=FITS[i].replace('./fits_data/','')
                file_name=dir_name.replace(input_ext,'')
            
            for j in range(len(hdul)-hdul_index):        
                data=hdul[hdul_index].data.transpose()
                header = hdul[hdul_index].header
                if header['NAXIS'] == 2:
                    if header['BITPIX'] < 0:
                        name_label = f'-float{header["BITPIX"] * -1}-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        type_name = f'float{header["BITPIX"] * -1}'
                    if header['BITPIX'] > 0:
                        name_label = f'-uint{header["BITPIX"]}-1x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        type_name = f'uint{header["BITPIX"]}'
                    data = np.expand_dims(data, axis=2)
                elif header['NAXIS'] == 3:
                    if header['BITPIX'] < 0:
                        name_label = f'-float{header["BITPIX"] * -1}-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        type_name = f'float{header["BITPIX"] * -1}'
                    if header['BITPIX'] > 0:
                        name_label = f'-uint{header["BITPIX"]}-{header["NAXIS3"]}x{header["NAXIS2"]}x{header["NAXIS1"]}'
                        type_name = f'uint{header["BITPIX"]}'                
                else:
                    raise Exception(f"Invalid header['NAXIS'] = {header['NAXIS']}")
        
                output_folder=f'./raw_data/{type_name}/'
                os.makedirs(os.path.dirname(f'{output_folder}'), exist_ok=True)
                data=data.swapaxes(0,2)
                data.astype(type_name).tofile(f'{output_folder}/{file_name}-extension{j}-{name_label}.raw')
                header.totextfile(f'{output_folder}/{file_name}-extension{j}-{name_label}.txt')
                hdul_index += 1

if __name__ == '__main__':
    print("This example converts all .fit files in fits_data into raw_data, preserving "
          "the directory hierarchy.")

    FitsToRaw.Version()
