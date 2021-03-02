# Kakadu Plugin
On `kakadu_codec.py` a wrapper for Kakadu's JPEG2000 binaries is implemented. 

In order to use this codec it is necessary to download the executables from Kakadu's website: https://kakadusoftware.com/documentation-downloads/downloads/

## Instalation
For this wrapper only `kdu_compress` and `kdu_expand` are required and should be placed in this folder. 
- Linux: configure the PATH and LD_LIBRARY_PATH to the `libkdu_v80R.so` shared library. This can be done by running the following commands:
```bash
PATH=$PATH:{PATH_TO_FILE}
LD_LIBRARY_PATH=$LD_LIBRARY_PATH:{PATH_TO_FILE}
export PATH
export LD_LIBRARY_PATH
```
