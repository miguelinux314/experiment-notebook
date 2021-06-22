# 2021/06/21 v0.2.7

* New functions:
  
  * Added support to plot columns that contain dictionaries with numeric values (see enb.aanalysis.ScalarDictAnalyzer): 
    
    - String keys are supported. In this case, they are assumed to be class names, and are shown by default 
      as elements across the x_axis.
      
    - Number to number mappings are also supported. Typical examples are 
      histograms, probability mass functions (PMFs/discrete PDFs), and cumulative distribution functions (CDFs). 
      These can be expressed as a dict-like object mapping x to P(x). 
      
    - The `combine_keys` argument can be used to easily plot PMFs/PDFs as histograms, rebin existing histrograms,
      or regroup class names (e.g., one could have data for `arms`, `head`, `legs`, `feet` 
      as class names (dictionary key values), and easily combine them into `upper_body` and `lower_body` before
      analysis.
      
    - More generally, any object that supports the comparison interface can be used for the key values, as these
      are sorted by default.
      
  * Added a codec support:
      - enb.isets.FITSWrapper can now be used to easily define codecs that need .fit/.fits files as an input.
      - Added Fpack, Fpzip, zfp codecs for FITs data.
      - Added standalone Zstandard codec.
  
  * iset-based tables can now inherit from enb.isets.SampleDistributionTable to automatically compute dictionaries
    containing probability mass functions.
    
* Bug fixes:
      
  - Fixed potential problems when defining subclasses of enb.sets.FileVersionTable. One should now be able to freely
    mix and match versioning tables without syntax errors.
    
  - Fixed FITS codec endianness
  

# 2021/05/13 v0.2.6

* New functions:
  
  - FileVersionTable subclasses now can choose not to check the expected output files and use all produced
    files in the versioned dir instead.
  - Added FITS to raw version table
  
* Function improvements:
  
  - Improved HEVC and VVC compilation scripts
  - Improved support for datasets consisting of symbolic links to a single copy of the dataset
  - Improved default wrapper codec names when no hexdump signature is desired
  
* Plotting improvements:
  
  - Improved the general plot function to increase control over displayed colors.
  - Added ScalarToScalarAnalyzer to plot dictionary cell data. Shadowed bands based on std can now be depicted.
  - Several minor fix-ups to plot rendering and general stability

* Docs are now displayed on the public site automatically point to the dev banch

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
