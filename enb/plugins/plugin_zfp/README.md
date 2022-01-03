ZFP
===
[![Travis CI Build Status](https://travis-ci.org/LLNL/zfp.svg?branch=develop)](https://travis-ci.org/LLNL/zfp)
[![Appveyor Build Status](https://ci.appveyor.com/api/projects/status/github/LLNL/zfp?branch=develop&svg=true)](https://ci.appveyor.com/project/salasoom/zfp)
[![Documentation Status](https://readthedocs.org/projects/zfp/badge/?version=release0.5.5)](https://zfp.readthedocs.io/en/release0.5.5/?badge=release0.5.5)
[![Codecov](https://codecov.io/gh/LLNL/zfp/branch/develop/graph/badge.svg)](https://codecov.io/gh/LLNL/zfp)

INTRODUCTION
------------

zfp is an open source C/C++ library for compressed numerical arrays that
support high throughput read and write random access.  zfp also supports
streaming compression of integer and floating-point data, e.g., for
applications that read and write large data sets to and from disk.
zfp is primarily written in C and C++ but also includes Python and
Fortran bindings.

zfp was developed at Lawrence Livermore National Laboratory and is loosely
based on the algorithm described in the following paper:

    Peter Lindstrom
    "Fixed-Rate Compressed Floating-Point Arrays"
    IEEE Transactions on Visualization and Computer Graphics
    20(12):2674-2683, December 2014
    doi:10.1109/TVCG.2014.2346458

zfp was originally designed for floating-point arrays only, but has been
extended to also support integer data and could for instance be used to
compress images and quantized volumetric data.  To achieve high compression
ratios, zfp generally uses lossy but optionally error-bounded compression.
Bit-for-bit lossless compression is also possible through one of zfp's
compression modes.

zfp works best for 2D and 3D arrays that exhibit spatial correlation, such as
continuous fields from physics simulations, images, regularly sampled terrain
surfaces, etc.  Although zfp also provides a 1D array class that can be used
for 1D signals such as audio, or even unstructured floating-point streams,
the compression scheme has not been well optimized for this use case, and
rate and quality may not be competitive with floating-point compressors
designed specifically for 1D streams.  zfp also supports compression of
4D arrays.

zfp is freely available as open source under a BSD license, as outlined in
the file 'LICENSE'.  For more information on zfp and comparisons with other
compressors, please see the
[zfp website](https://computation.llnl.gov/projects/floating-point-compression).
For bug reports, please consult the
[GitHub issue tracker](https://github.com/LLNL/zfp/issues).
For questions, comments, and requests, please contact
[Peter Lindstrom](mailto:pl@llnl.gov).


DOCUMENTATION
-------------

Full
[documentation](http://zfp.readthedocs.io/en/release0.5.5/)
is available online via Read the Docs.  A
[PDF](http://readthedocs.org/projects/zfp/downloads/pdf/release0.5.5/)
version is also available.

COMMANDS
--------

zfp version 0.5.5 (May 5, 2019)
Allowed data type to be compressed: integer 32 & 64 , float 32 & 64
Usage: zfp <options>
General options:
  -h : read/write array and compression parameters from/to compressed header
  -q : quiet mode; suppress output
  -s : print error statistics
Input and output:
  -i <path> : uncompressed binary input file ("-" for stdin)
  -o <path> : decompressed binary output file ("-" for stdout)
  -z <path> : compressed input (w/o -i) or output file ("-" for stdin/stdout)
Array type and dimensions (needed with -i):
  -f : single precision (float type)
  -d : double precision (double type)
  -t <i32|i64|f32|f64> : integer or floating scalar type
  -1 <nx> : dimensions for 1D array a[nx]
  -2 <nx> <ny> : dimensions for 2D array a[ny][nx]
  -3 <nx> <ny> <nz> : dimensions for 3D array a[nz][ny][nx]
  -4 <nx> <ny> <nz> <nw> : dimensions for 4D array a[nw][nz][ny][nx]
Compression parameters (needed with -i):
  -R : reversible (lossless) compression
  -r <rate> : fixed rate (# compressed bits per floating-point value)
  -p <precision> : fixed precision (# uncompressed bits per value)
  -a <tolerance> : fixed accuracy (absolute error tolerance)
  -c <minbits> <maxbits> <maxprec> <minexp> : advanced usage
      minbits : min # bits per 4^d values in d dimensions
      maxbits : max # bits per 4^d values in d dimensions (0 for unlimited)
      maxprec : max # bits of precision per value (0 for full)
      minexp : min bit plane # coded (-1074 for all bit planes)
Execution parameters:
  -x serial : serial compression (default)
  -x omp[=threads[,chunk_size]] : OpenMP parallel_decorator compression
  -x cuda : CUDA fixed rate parallel_decorator compression/decompression
Examples:
  -i file : read uncompressed file and compress to memory
  -z file : read compressed file and decompress to memory
  -i ifile -z zfile : read uncompressed ifile, write compressed zfile
  -z zfile -o ofile : read compressed zfile, write decompressed ofile
  -i ifile -o ofile : read ifile, compress, decompress, write ofile
  -i file -s : read uncompressed file, compress to memory, print stats
  -i - -o - -s : read stdin, compress, decompress, write stdout, print stats
  -f -3 100 100 100 -r 16 : 2x fixed-rate compression of 100x100x100 floats
  -d -1 1000000 -r 32 : 2x fixed-rate compression of 1M doubles
  -d -2 1000 1000 -p 32 : 32-bit precision compression of 1000x1000 doubles
  -d -1 1000000 -a 1e-9 : compression of 1M doubles with < 1e-9 max error
  -d -1 1000000 -c 64 64 0 -1074 : 4x fixed-rate compression of 1M doubles
