import numpy as np
import fitsio
from astropy.io import fits
from astropy.io.fits import Header
import glob
import enb.sets import sets
import enb.isets as isets
from enb.config import options

class RawToFits(sets.FileVersionTable, sets.FilePropertiesTable):
    def __init__(self, original_base_dir, version_base_dir):
        super().__init__(
            original_base_dir=original_base_dir,
            version_base_dir=version_base_dir,
            original_properties_table=sets.FilePropertiesTable(),
            version_name=self.version_name)    
            
    def Version(input_path):
        RAWS=glob.glob('./raw_data/*.raw')
        
        for i in range(len(RAWS)):
            file=RAWS[i]
            params = file[7:-4].split("-")
            dimensions=params[-1].split('x')
            print(params)
            print(dimensions)
            frames=int(dimensions[-3])
            columns=int(dimensions[-2])
            rows=int(dimensions[-1])
            astype=params[-2]
            name=params[0]
            extension=params[-4]
            
            img=np.fromfile(open(file), dtype = f'{astype}',  count = -1)
            print(img.shape)
            array=np.reshape(img,(frames,columns,rows))

            hdu = fits.PrimaryHDU(array, header=Header.fromfile(f'{file[0:-4]}.txt',sep='\n', endcard=False,padding=False))
            hdu.writeto(f'./fits_data/{name[0:-2]}_{extension}.fits')
            
if __name__ == '__main__':
    print("This example converts all raw files in raw_data into fits_data, preserving "
          "the original fits header")
    input_path='./raw_data'
    RawToFits.Version(input_path)
