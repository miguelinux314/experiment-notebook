fpzip version 1.3.0 (December 20, 2019)
Allowed data type to be compressed: float 32
Usage: fpzip [options] [<infile] [>outfile]
Options:
  -d : decompress
  -q : quiet mode
  -i <path> : input file (default=stdin)
  -o <path> : output file (default=stdout)
  -t <float|double> : scalar type (default=float)
  -p <precision> : number of bits of precision (default=full)
  -1 <nx> : dimensions of 1D array a[nx]
  -2 <nx> <ny> : dimensions of 2D array a[ny][nx]
  -3 <nx> <ny> <nz> : dimensions of 3D array a[nz][ny][nx]
  -4 <nx> <ny> <nz> <nf> : dimensions of multi-field 3D array a[nf][nz][ny][nx]
