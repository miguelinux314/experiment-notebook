# CHANGELOG

The following updates have been highlighted for each release. Note that `enb` employs a `MAYOR`.`MINOR`.`REVISION`
format. Given a code initially developed for one `enb` version and then executed in another (newer) version:

- If `MAYOR` and `MINOR` are identical, backwards compatibility is provided. Some deprecation warnings might appear,
  which typically require small changes in your scripts.

- If `MAYOR` is identical by `MINOR` differs, minor code changes might be required if any deprecated parts are still
  used. Otherwise, deprecation warnings are turned into full errors.

- If `MAYOR` is larger, specific code changes might be needed for your code. So far, a single `MAYOR` version (0) is
  used. The next mayor version (1) is expected to be backwards compatible with the latest release of the 0 mayor branch.

# Development version v0.4.0

- **Not backward-compatible** changes:
    
    - Several command line options have been removed, and/or moved to `*.ini` files 
      (e.g., in your project folders - use `enb plugin install enb.ini .` to copy a full `*.ini` template)
      and direct object manipulation. These are:

        - `--no_ray`: By default, ray is not the default parallelization engine anymore. To use ray, one needs
          to specifiy `--ssh_cluster_csv_path` or, alternatively, set the `ssh_cluster_csv_path` field in 
          the `[enb.config.options]` section of your `'*.ini'` files.
          Run your script with `-h` for additional
          information on this parameter and/or check the 
          [documentation on cluster configuration](https://miguelinux314.github.io/experiment-notebook/cluster_setup.html).
      
        - A number of plot rendering configuration options have been removed from the CLI and are now
          accessible via the `[enb.aanalysis.Analyzer]` section of `'*.ini'` files, direct class
          or instance manipulation of `enb.aanalyis.Analyzer` classes and/or instances, and as 
          the `**kwargs` argument to Analyzer.get_df(), in turn passed to the `plotdata` module.
          The affected options are those previously defined in `RenderingOptions` (now also deleted):
          
            - `fig_height`, `fig_width`
            - `horizontal_margin`, `vertical_margin`
            - `group_row_margin`
            - `legend_column_count`
            - `show_grid`, `show_subgrid`
            - `global_title` (removed, use `plot_title` instead)
            

General improvements:

    - The position of the legend can now be configured. 
      The `legend_position` parameter can now be passed in `plot_pds_by_group()`'s kwargs, 
      and configured via .ini files (under the `[enb.aanalysis.Analyzer]` section).

    - Compression experiments now compute the execution time as the minimum of all repetitions,
      instead of the average.

Bug fixes:

    - Fixed a "disk leak" problem in `enb.icompression`, which caused deleted files to take space until the script
      finished, due to unclosed file descriptors.
    - The 2D analyzer now correctly sets the y label to the name of the y column instead of the group name.
    - Fixed wrongly displayed warnigns when invoking the CLI with parameters.
    - Caught another potential failing point in aanalysis when fewer than 2 different samples are retrieved, 
      when calculating linear regression parameters.


# Latest stable version

## 2022/04/20 v0.3.6

Important: a new dependency was added in this version; you will need to install `enb` again if you had installed
with `pip install -e path_to_repo` and have only updated `path_to_repo` to the latest version.
This is done automatically if installed from pip.

* New features

    - Added support for plotting histograms of 2d data using colormaps, e.g.,
      see this 
      [example](https://miguelinux314.github.io/experiment-notebook/analyzing_data.html#analysis-numeric-spatial-2d-data)
    - Automatic generation of latex-formatted output tables in `enb.aanalysis.Analyzer` subclasses
      (stored by default under the `analysis/` subfolder of your projects).
    - Added a few new data compression plugins:
        - arithmetic codec (`arithmetic_codec`)
        - a non-block-adaptive huffman codec (`huffman`)
        - SPECK (`speck`)
    - Added the `enb.plugins.install` method that ensures a plugin is installed and is able to automatically import it.
      Check out `enb plugin list` for all plugins available in this fashion.

* General improvements
    - Added a SHA256 table of contrib packages, so that the newest version is downloaded if an outdated
      version is in the cache.
    - Improved progress reporting with animation.
    - Added the `average_identical_x` attribute to `enb.aanalysis.TwoNumericAnalyzer`, which allows a cleaner analysis
      by averaging samples which share the same x value (applies to the 'line' render mode only).
    - Improved the default group name sorting to better understand numeric values.

* Bug fixes

    - Fixed Kakadu plugin Sdims axis swap bug.
    - Fixed `file_or_path` argument in `dump_bsq_array` so that it accepts open files as described in the API.
    - Fixed some cosmetic problems in the `enb.aanalysis` module.
    - Fixed DictNumericAnalyzer so that key_to_x is correctly processed if available.
    - Fixed warning messages from numpy/scipy when trying to compute correlations or statistical descriptions
      with a single data point, or constant data.
    - Fixed the makefiles of the `fpack` and `ndzip` data compression plugins.  
    - When requested, a copy of the compressed and/or reconstructed files is stored in the configured
      folder for LosslessCompressionExperiment subclasses even if reconstruction is not lossless for those files
      (see the `reconstructed_copy_dir` and `compressed_copy_dir`
      arguments of `enb.icompression.CompressionExperiment`)

# Version history

## 2022/02/16 v0.3.5

* New features

    - Introduced the `enb show` command to show some useful information. Run `enb show -h` for more details.
    - Added the `boxplot` and `hbar` render modes to ScalarNumericAnalyzer.
    - Added the `'enb.ini'` plugin that allows installation of an editable configuration file for enb.
    - Added the `'matplotlibrc'` plugin that allows installation of an editable matplotlib style template.
    - Added documentation on how to customize the appearance of plots.
    - The ssh+ray-based cluster can now operate on network-synchronized project folders (e.g., NFS), instead of relying
      on the sshfs library.

* General improvements

    - Enhanced the `combine_groups` option for |Analyzer| subclasses, and its documentation.
    - Accelerated the initialization of ray for the case without remote nodes.
    - Plot styling can now be read from `'enb.ini'`.
    - Added subgrid configuration from `get_df` and `enb.ini` approaches.
    - Updated VVC sources to 15.0.
    - Added debug verbosity useful when loading large csv files with large dictionaries or objects.

* Bug fixes

    - Fixed label positioning in some plots with longer labels.
    - Fixed minor ticks when labels are provided.
    - Fixed dictionary plots.

## 2022/01/05 v0.3.4

Mostly bugfixes and cleanup in this version.

- Stability improvement on Windows platforms.
- General documentation enhancement, including README.
- Fixed small bugs in the `montecarlo-pi` plugin.
- Renamed the `enb.config.options.ray_cpu` attribute into `enb.config.options.cpu_limit`.

## 2022/01/04 v0.3.3

**Important**: Removed all deprecated methods scheduled for removal for v0.3.0 (Aug 31, 2021). This breaks compatibility
with the v0.2.* versions, although most encountered issues can be easily overcome by using the new enb.aanalyis.Analyzer
subclasses and their `get_def()` method instead of the old `analyze_df()`.

* New features

    - Added ssh-based multi-computer processing.

    - Added the `reference_group` parameter to the `get_df` method of `enb.aanalysis.Analayzer` subclasses, wich allows
      displaying differences against the average of one group (`group_by` must be used).

    - The project_root attribute has been added to enb.config.options that points to the directory where the calling
      script is. Persistence paths are now stored relative to this project root, and enb **now changes the current
      working dir to that project root**
      upon initialization (also applies to remote functions).

* General improvements

    - Simplified the installation process on Windows, added support when ray is not prsent.
    - Improved documentation and plugins about lossless and lossy compression templates.
    - Added a lossy compression template.
    - Complete review of the documentation with the new classes.

## 2021/11/29 v0.3.2

* New features

    - Added a wrapper for codecs for a yet-to-be-released variable-to-fixed (V2F) forests.
    - Added a wrapper for the upcoming CCSDS 124.0-B-1.
    - Experiments now create a family_label column to simplify analysis.
    - Added support for sorting group rows based on their average value.
    - Added support for grouping based on enb.experiment.TaskFamily lists to enb.aanalysis.Analyzer.
    - Improved documentation, including the most recent plotting and command-line tools and additions.

* General improvements

    - Updated the user manual with the most recent analyzer classes
    - Updated the documentation for the LCNL/CCSDS 123.0-B-2 codec: the binaries are now publicly available but not
      redistributed with enb.
    - Updated the ScalarNumericAnalyzer so that it can display averages (with or without std error bars) without
      displaying any histogram.

## 2021/09/10 v0.3.1

* New features
    - Added a lossless compression experiment template.
    - Added csv to latex utility function in misc for easier and faster report making.

* General improvements
    - Improved overall stability and aesthetic control over plotting with enb.aanalysis
    - Removed the recordclass package as a dependency, as enb's usage did not justify the package's size
    - Enhanced clarity and robustness of the setup.py script to simplify installation via pip
    - Fixed potential method resolution order inconsistencies between class methods and column setters; now the
      intuitive behavior is better enforced.

## 2021/08/31 v0.3.0

Version 0.3.0 is packed with new features and general performance improvements. At the same time, significant backwards
compatibility is preserved with the 0.2 version family:

- Client code: major class names and their methods (e.g., ATable, Experiment, get_df, etc.) retain their name and
  semantics. Several methods and classes have been renamed and refactored, but these are not likely referenced in client
  code. In summary, your client code should be compatible with 0.3.0 if it was with 0.2.8 as long as it did not rely on
  the library internals.

- Data format: the __atable_index column is now included in the CSV persistence. This trades off some extra disk space
  for faster loading times and a little extra traceability. As a result, CSV persistence files produced with 0.2.8 or
  earlier cannot be loaded with 0.3.0 and later.

- Features: all previous features have been retained, and new ones have been added.

New major functions:

- Created the first functional CLI. Can be run with `enb` or `python -m enb`.
- Added a plugin installation subsystem; try `enb plugin -h` for more information.
- New logging subsystem, which allows for a more flexible message output selection with more elegant code

Improvements and other changes

- Improved performance of the ATable population, storage and loading routines.
- Plotting in aanalysis makes more efficient use of parallelization.
- Added several new image compression codec plugins with floating point support, based on the `h5py` library.
- The sequential option is removed, in favor of setting the maximum number of cpus to 1.

## 2021/07/14 v0.2.8

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

        - All changes should be totally transparent for enb client code. Recall that `from enb.config import options`
          is the preferred way of acquiring the global options instance, then both `x = options.property`
          and `options.property = x` are supported as before
          (except for any additional value checks that may now be performed).

## 2021/06/30 v0.2.7

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

## 2021/05/13 v0.2.6

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

## 2021/04/27 v0.2.5

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

## 2021/03/05 v0.2.4

- Added new codec plugins:
    * Kakadu
    * HEVC lossless
    * FSE
    * Huffman
    * JPEG-XL
