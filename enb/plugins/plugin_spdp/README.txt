Source https://userweb.cs.txstate.edu/~burtscher/research/SPDPcompressor/

SPDP is a compression/decompression algorithm that is tailored towards binary IEEE 754 32-bit single-precision (float)
and 64-bit double-precision (double) floating-point data but also works on other data.

The source code can be compiled as follows:
    gcc -O3 SPDP_11.c -o spdp

To compress the file floating_point.bin with a compression level of 5 and store the compressed output in the file floating_point.spdp, enter:
    ./spdp 5 < floating_point.bin > floating_point.spdp

The supported compression levels go from 0 (faster with a lower compression ratio) to 9 (slower with a higher compression ratio).

To decompress the file floating_point.spdp and store the decompressed output in the file floating_point.org, enter:
    ./spdp < floating_point.spdp > floating_point.org

