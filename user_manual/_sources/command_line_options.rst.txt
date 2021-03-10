Command-line options
====================

When executing your experiments using enb, you can use the command-line interface (CLI)
features it includes.

A set of predefined parameters are available in `enb.config.options`, the single instance
of the :class:`enb.config.AllOptions` class.

Your code can then access and modify those global options programmatically with code like

.. code-block::python
    import enb.config.options as options
    print(f"Verbose: {options.verbose}")

Users of `enb` can extend the :class:`enb.config.AllOptions` to add additional variables.

When running a script that import enb.config, "-h" can be passed as argument to show
the following message (might differ from the master branch and depends on your paths)

Verbose
-------

Do you want to switch error/trace messages on/off? use -v and then check for `options.verbose`.

.. code-block:: RST

    General Options:
      --verbose, --v        Be verbose? Repeat for more. (default: 0)

Execution options
-----------------

The following options control the way in which the experiments are executed.

.. code-block:: RST

    Execution Options:
      --force, --f          Force calculation of pre-existing results. If an error
                            occurs while re-computing a given index, that index is
                            dropped from the persistent support. (default: 0)
      --quick, --q          Be quick? Retrieve a small subset of all files when
                            requested for all. (default: 0)
      --sequential, --s     Make computations sequentially instead of distributed
                            (default: False)
      --repetitions REPETITIONS
                            Number of repetitions when calculating execution times.
                            (default: 1)
      --columns COLUMNS [COLUMNS ...], ---c COLUMNS [COLUMNS ...]
                            List of selected column names for computation. If one or
                            more column names are provided, all others are ignored.
                            Multiple columns can be expressed, separated by spaces.
                            (default: None)
      --exit_on_error       If True, any exception when processing rows aborts the
                            program. (default: False)
      --discard_partial_results
                            Discard partial results when an error is found running the
                            experiment? Otherwise, they are output to persistent
                            storage. (default: False)
      --no_new_results      Don't compute any new data. (default: False)
      --chunk_size CHUNK_SIZE, --cs CHUNK_SIZE
                            Chunk size. Each processed chunk is made persistent before
                            processing the next one. (default: None)

Plot rendering
--------------

These options are offered so that you can control different aspects
of the produced plots. It is most effective when used programmatically,
but it can also be used via the CLI

.. code-block:: RST

    Rendering Options:
      --no_render, --nr     Don't actually render data (default: False)
      --fig_width FIG_WIDTH, --fw FIG_WIDTH
                            Figure width. Larger values make text look smaller.
                            (default: 5)
      --fig_height FIG_HEIGHT, --fig_height FIG_HEIGHT
                            Figure height. Larger values make text look smaller.
                            (default: 4)
      --global_y_label_pos GLOBAL_Y_LABEL_POS
                            Relative position of the global Y label. Can be negative
                            (default: -0.01)
      --legend_column_count LEGEND_COLUMN_COUNT
                            Number of columns used in plot legends (default: 2)
      --show_grid           Show major axis grid? (default: False)
      --displayed_title DISPLAYED_TITLE
                            Show title in rendered plots? (default: None)

Ray
---

The ray library (https://github.com/ray-project/ray)  allows execution of tasks in
multiple cores, which can exist in one or more machines. By default, all cores
of the local machine are employed.

.. code-block:: RST

    Ray Options:
      --ray_config_file RAY_CONFIG_FILE
                            Ray server configuration path (must contain IP:port in its
                            first line) (default:
                            /experiment-
                            notebook.git/enb/ray_cluster_head.txt)
      --ray_cpu_limit RAY_CPU_LIMIT
                            CPU count limit for ray processes (default: None)

Data directories
----------------

There are a few predefined directory roles that can be used across the library.
Probably the most important one is the `--base_dataset_dir`` option, which determines
where input samples are looked for by default.

.. code-block:: RST

    Data directories:
      --base_dataset_dir BASE_DATASET_DIR, --d BASE_DATASET_DIR
                            Base dir for dataset folders. (default: None)
      --persistence_dir PERSISTENCE_DIR
                            Directory where persistence files are to be stored.
                            (default: /experiment-notebook.git/enb/persistence_config.py)
      --reconstructed_dir RECONSTRUCTED_DIR
                            Base directory where reconstructed versions are to be
                            stored (default: None)
      --reconstructed_size RECONSTRUCTED_SIZE
                            If not None, the size of the central region to be rendered
                            in each component (default: None)
      --base_version_dataset_dir BASE_VERSION_DATASET_DIR, --vd BASE_VERSION_DATASET_DIR
                            Base dir for versioned folders. (default: None)
      --base_tmp_dir BASE_TMP_DIR, --t BASE_TMP_DIR
                            Temporary dir. (default: /dev/shm)
      --external_bin_base_dir EXTERNAL_BIN_BASE_DIR
                            External binary base dir. (default: None)
      --plot_dir PLOT_DIR   Directory to store produced plots. (default:
                            /experiment-notebook.git/enb/plots)
      --analysis_dir ANALYSIS_DIR, --analysis_dir ANALYSIS_DIR
                            Directory to store analysis results. (default:
                            /experiment-notebook.git/enb/analysis)
