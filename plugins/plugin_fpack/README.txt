FPACK and FUNPACK can be downloadd and the documentation can be found at https://heasarc.gsfc.nasa.gov/fitsio/fitsio.html

SYNOPSIS
       funpack [OPTION]... FILE...

DESCRIPTION
       fpack  is a utility program for optimally compressing images in the FITS data format.  This programs is analogous to the GZIP utility program except that it
       is optimized for FITS format images and offer a wider choice of compression options.
       
OPTIONS
       -r     Rice compression (default).

       -h     Hcompress compression.

       -g     or -g1  GZIP_1 (per-tile) compression.

       -g2    GZIP_2 (per-tile) compression (with byte shuffling).

       -p     PLIO compression (only for positive 8 or 16-bit integer images).

       -d     Tile the image without compression (debugging mode).

       -w     Compress the whole image as a single large tile.

       -t axes
              Comma separated list of tile dimensions (default is row by row).
       -q level
              Quantized level spacing when converting floating point images to scaled integers. (+value relative to sigma of background noise; -value is absolute).
              Default q value of 4 gives a compression ratio of about 6 with very high fidelity (only 0.26% increase in noise).  Using q values of  2,  or  1  will
              give  compression ratios of about 8, or 10, respectively (with 1.0% or 4.1% noise increase).  The scaled quantized values are randomly dithered using
              a seed value determined from the system clock at run time.  Use -q0 instead of -q to suppress random dithering.  Use -qz instead of -q to not  dither
              zero-valued  pixels.   Use  -qt or -qzt to compute random dithering seed from first tile checksum.  Use -qN or -qzN, (N in range 1 to 10000) to use a
              specific dithering seed.  Floating-point images can be losslessly compressed by selecting the GZIP algorithm and specifying -q 0, but this is  slower
              and often produces much less compression than the default quantization method.

       -i2f   Convert  integer  images  to floating point, then quantize and compress using the specified q level.  When used appropriately, this lossy compression
              method can give much better compression than the normal lossless compression methods without significant  loss  of  information.   The  -n3ratio  and
              -n3min flags control the minimum noise thresholds; Images below these thresholds will be losslessly compressed.
            
       -n3ratio
              Minimum ratio of background noise sigma divided by q.  Default = 2.0.

       -n3min Minimum background noise sigma. Default = 6. The -i2f flag will be ignored if the noise level in the image does not exceed both thresholds.

       -s scale
              Scale factor for lossy Hcompress (default = 0 = lossless) (+values relative to RMS noise; -value is absolute)

       -n noise
              Rescale scaled-integer images to reduce noise and improve compression.

       -v     Verbose mode; list each file as it is processed.

       -T     Show compression algorithm comparison test statistics; files unchanged.

       -R file
              Write the comparison test report (above) to a text file.

       -table Compress FITS binary tables using prototype method, as well as compress any image HDUs. This option is intended for experimental use.

       -tableonly
              Compress only FITS binary tables using prototype method; do not compress any image HDUs. This option is intended for experimental use.

       -F     Overwrite input file by output file with same name.

       -D     Delete input file after writing output.

       -Y     Suppress prompts to confirm -F or -D options.

       -S     Output compressed FITS files to STDOUT.

       -L     List contents; files unchanged.

       -C     Don't update FITS checksum keywords.

       -H     Show this message.

       -V     Show version number.


