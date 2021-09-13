Source https://github.com/fknorr/ndzip

ndzip leverages SIMD- and thread parallelism to compress and decompress multidimensional univariate grids 
of single- and double-precision IEEE 754 floating-point data at speeds close to memory bandwidth. Its primary 
use case is speeding up distributed HPC applications by increasing effective interconnect and bus bandwidth.

The optimized implementation of ndzip requires AVX2. To obtain the compressor use:

cmake -B build -DCMAKE_CXX_FLAGS="-march=native”
cmake --build build --target compress

Then you should find the compressor under build/compress. Note that only Linux has been tested as a platform so far, if you're working with Windows, you will have to use WSL.

Usage: ./compress [options]

Options:
  --help                  show this help
  -d [ --decompress ]     decompress (default compress)
  -n [ --array-size ] arg array size (one value per dimension, first-major)
  -t [ --data-type ] arg  float|double (default float)
  -e [ --encoder ] arg    cpu|cpu-mt (default cpu)
  -i [ --input ] arg      input file (default '-' is stdin)
  -o [ --output ] arg     output file (default '-' is stdout)
  --no-mmap               do not use memory-mapped I/O




