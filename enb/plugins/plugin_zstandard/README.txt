https://github.com/facebook/zstd

--- what commit are we importing? branch and date 

*** zstd command line interface 64-bits v1.1.3, by Yann Collet ***
Zstandard allows to compress al data types: float and integer 16, 32 and 64 bpp
Usage :
      zstd [args] [FILE(s)] [-o file]

FILE    : a filename
          with no FILE, or when FILE is - , read standard input
Arguments :
 -#     : # compression level (1-19, default:3) 
 -d     : decompression 
 -D file: use `file` as Dictionary 
 -o file: result stored into `file` (only if 1 input file) 
 -f     : overwrite output without prompting 
--rm    : remove source file(s) after successful de/compression 
 -k     : preserve source file(s) (default) 
 -h/-H  : display help/long help and exit

Advanced arguments :
 -V     : display Version number and exit
 -v     : verbose mode; specify multiple times to increase log level (default:2)
 -q     : suppress warnings; specify twice to suppress errors too
 -c     : force write to standard output, even if it is the console
 -r     : operate recursively on directories 
--ultra : enable levels beyond 19, up to 22 (requires more memory)
--no-dictID : don't write dictID into header (dictionary compression)
--[no-]check : integrity check (default:enabled) 
--test  : test compressed file integrity 
--[no-]sparse : sparse mode (default:enabled on file, disabled on stdout)
 -M#    : Set a memory usage limit for decompression 
--      : All arguments after "--" are treated as files 

Dictionary builder :
--train ## : create a dictionary from a training set of files 
--cover=k=#,d=# : use the cover algorithm with parameters k and d 
--optimize-cover[=steps=#,k=#,d=#] : optimize cover parameters with optional parameters
 -o file : `file` is dictionary name (default: dictionary) 
--maxdict ## : limit dictionary to specified size (default : 112640) 
 -s#    : dictionary selectivity level (default: 9)
--dictID ## : force dictionary ID to specified value (default: random)

Benchmark arguments :
 -b#    : benchmark file(s), using # compression level (default : 1) 
 -e#    : test all compression levels from -bX to # (default: 1)
 -i#    : minimum evaluation time in seconds (default : 3s)
 -B#    : cut file into independent blocks of size # (default: no block)
