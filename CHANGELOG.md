# Under development v0.2.9

* New functions

    - Added a functional CLI for installing and searching plugins
  
    - Added several new image compression codec plugins with floating point support, based on the `h5py` library.
  
    - Added recursive subclass search in `misc.py`


# 2021/07/14 v0.2.8

* New functions:

    - Added `enb.atable.SummaryTable` as a way to arbitrarily group dataframe rows and compute aggregated columns on
      them. This has great potential for both analysis and plotting.

    - Some core plugins are now automatically included with `enb` distributions. That is, you will find them
      at `enb/plugins`, where `enb/` is the installation destination folder (e.g., your venv). However, integration is
      not yet complete, and **plugins still need to be manually built**. To facilitate the task,
      the `build_all_plugins.sh` script has been temporarily included as well.

    - Added several new codecs with floating point support.

    - Added the `enb.aanalysis.pdf_to_png` method to easily convert folders with pdf figures into folders with png
      figures. The source and origin folders may be the same.


* General improvements:

    - Improved general stability to different parts of `aanalysis.py`.

    - The `test_all_codecs.py` script has been revamped to more easily describe codec availability of each data format
      class.

        - Now, codecs just need to have been defined (e.g., by an appropriate import).
        - Error logs are output as a new column to the script's persistence output and can be checked in case of need.
        - Note that the `build_all_plugins.sh` is **not** executed automatically, so codec availability may fail until
          it is.

    - Revamped the configuration module `enb.config` with the `options` singleton:

        - Grouping and documentation is automatically taken from the classes and property methods. See the
          new `@enb.singleton_cli.property_class(base_cls)` decorator for more information on this.

        - Improved value verifier/setter system. In addition to CLI-parsing, it allows finer-grain input value
          validation and shaping.

        - All changes should be totally transparent for enb host code. Recall that `from enb.config import options`
          is the preferred way of acquiring the global options instance, then both `x = options.property`
          and `options.property = x` are supported as before
          (except for any additional value checks that may now be performed).
          
# 2021/06/30 v0.2.7

* New functions:

    * Added support to plot columns that contain dictionaries with numeric values (see
      enb.aanalysis.ScalarDictAnalyzer):

        - String keys are supported. In this case, they are assumed to be class names, and are shown by default as
          elements across the x_axis.

        - Number to number mappings are also supported. Typical examples are histograms, probability mass functions (
          PMFs/discrete PDFs), and cumulative distribution functions (CDFs). These can be expressed as a dict-like
          object mapping x to P(x).

        - The `combine_keys` argument can be used to easily plot PMFs/PDFs as histograms, rebin existing histrograms, or
          regroup class names (e.g., one could have data for `arms`, `head`, `legs`, `feet`
          as class names (dictionary key values), and easily combine them into `upper_body` and `lower_body` before
          analysis.

        - More generally, any object that supports the comparison interface can be used for the key values, as these are
          sorted by default.

    * Added codec support:
      
        - enb.isets.FITSWrapper can now be used to easily define codecs that need `.fit`/`.fits` files as an input.
        - Added FPACK, FPZIP, ZFP, Zstandard codecs for FITS (potentially float) data.
        - Added standalone Zstandard codec.

    * enb.iset-based tables can now inherit from enb.isets.SampleDistributionTable to automatically compute dictionaries
      containing probability mass functions.

    * Disabled ray's dashboard by default to speed up script startup and termination time.

* Bug fixes:

    - Fixed potential problems when defining subclasses of enb.sets.FileVersionTable. One should now be able to freely
      mix and match versioning tables without syntax errors.

    - Fixed FITS codec endianness

# 2021/05/13 v0.2.6

* New functions:

    - FileVersionTable subclasses now can choose not to check the expected output files and use all produced files in
      the versioned dir instead.
    - Added FITS to raw version table

* Function improvements:

    - Improved HEVC and VVC compilation scripts
    - Improved support for datasets consisting of symbolic links to a single copy of the dataset
    - Improved default wrapper codec names when no hexdump signature is desired

* Plotting improvements:

    - Improved the general plot function to increase control over displayed colors.
    - Added `enb.aanalysis.ScalarToScalarAnalyzer` to plot dictionary cell data. Shadowed bands based on std can now be
      depicted.
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
