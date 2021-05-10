import numpy as np
import fitsio
from astropy.io import fits
from astropy.io.fits import Header
import glob


class RawToFits:
    def Version():
        RAWS=glob.glob('./raws/*.raw')

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
            
            img=np.fromfile(open(file), dtype = f'{astype}',  count = -1)
            array=np.reshape(img,(frames,columns,rows))

            hdu = fits.PrimaryHDU(array, header=Header.fromfile(f'{file[0:-4]}.txt',sep='\n', endcard=False,padding=False))
            hdu.writeto(f'./fits/{name[0:-2]}.fits')
            
if __name__ == '__main__':
    print("This example converts all raw files in raw_data into fits_data, preserving "
          "the original fits header")

    RawToFits.Version()
