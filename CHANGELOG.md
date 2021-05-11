# (under development) v0.2.6

- FileVersionTable subclasses now can choose not to check the expected output files and use all produced
  files in the versioned dir instead.
- Added FITS to raw version table
- Added ScalarToScalarAnalyzer to plot dictionary cell data. Shadowed bands based on std can now be depicted.
- Improved HEVC and VVC compilation scripts
- Improved default wrapper codec names when no hexdump signature is desired 
- Several minor fix-ups to plot rendering and general stability
- Improved support for datasets consisting of symbolic links to a single copy of the dataset
- Docs displayed on the public site automatically point to the dev branch now

# 2021/04/27 v0.2.5

- Improved enb compatibility with Windows and MacOS

- Added new codec plugins:
    * VVC
    * HEVC in lossy mode
    * Kakadu JPEG2000:
        - lossless
        - lossy with target rate and target PSNR support
    * Added Makefiles for Windows and MacOS for supporting codecs
    
- Added support for floating-point images (numpy f16, f32, f64)
- Added support for FITs images

# 2021/03/05 v0.2.4

- Added new codec plugins:
    * Kakadu
    * HEVC lossless
    * FSE
    * Huffman
    * JPEG-XL
