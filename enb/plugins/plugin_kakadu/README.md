# Kakadu Plugin

This module provides an enb plugin in `kakadu_codec.py`, which is a wrapper for Kakadu's JPEG2000 binaries. 

In order to use this codec it is necessary to download the binaries from Kakadu's website: https://kakadusoftware.com/documentation-downloads/downloads/, or compile them from source if you have it available. We are not allowed to distribute either.

## Instalation (with admin privileges)

Two simple steps after you have the binaries.

1. Copy `kdu_compress` and `kdu_expand` into the same folder as `kakadu_codec.py`.
2. Copy kakadu's dynamic library `libkdu_v80R.so` (or whatever version you are using) to your system library, e.g., to `/usr/lib`.

## Instalation (without admin privileges)

If copying to `/usr/lib` or similar is not possible, you can always edit the `LD_LIBRARY_PATH` environment variable 
and add the path where `libkdu_v80R.so`is, e.g.,

```bash
export LD_LIBRARY_PATH="/dir/with/lib/:$LD_LIBRARY_PATH"
```

Note how previous contents of `LD_LIBRARY_PATH` are preserved.
