Author: Enrico Magli

This zip archive contains executable files for the MCALIC encoder and decoder (both lossless and near-lossless versions), as described in:

E. Magli, G. Olmo, E. Quacchio, "Optimized Onboard Lossless and Near-Lossless Compression of Hyperspectral Data Using CALIC," IEEE Geoscience and Remote Sensing Letters, vol. 1, n. 1,pp. 21-25, Jan. 2004

Use of these executables is allowed for free for research activities, not commercial use. The executables are provided "as is", without any guarantee. I take no responsibility for the quality of the software provided, and am in no event liable for damages of any kind incurred or suffered as a result of its use. Moreover, though I would very much like to, I do not have time to provide support for the software.

That said, the binaries will run under Linux. They have been compiled under Red Hat 7.3, 2.4.20-28.7smp, gcc 2.96 using -O3.

The input file *MUST* be in BIL format (even though it can be internally converted by the software to BSQ), 2 bytes per sample in little endian format. All samples *MUST* be between 0 and 32767; negative values will generate errors. Therefore, signed and unsigned short integers will be identical on the file.

The syntax is as follows. For the lossless encoder:

Mcalic_enc input_file compressed_file bands lines pixels bits_per_pixel format 
Mcalic_enc reconstructed_file compressed_file bands lines pixels bits_per_pixel format 

For the near-lossless encoder:

Mcalic_enc_nl input_file compressed_file bands lines pixels bits_per_pixel maxerr format 
Mcalic_enc_nl reconstructed_file compressed_file bands lines pixels bits_per_pixel maxerr format 



bits_per_pixel: must be 16 (8 will handle data on 1 byte per sample, but this is totally untested)
format: 0/1. Zero will treat the BIL input file converting internally to BSQ. One will use the original BIL format.
maxerr: the maximum absolute error for near-lossless compression.

Note that the near-lossless encoder will also write the decoded version on a file named seqRec.

Known bug: the software will not handle images whose spatial size exceeds a given number of pixels. I have had occasional problems with some large images, but never had the time to fix the software. For reasonable spatial sizes, e.g. 1024x1024 pixels, the programs will work nicely.

