#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration in enb is centralized through this module.

Several key aspects should be highlighted:

    - Properties (attributes) defined in `enb.config.options` are mostly employed for default argument
      values in many `enb` modules. Host code (i.e., scripts using `enb`) may use and modify them in any desired way.

    - Properties are accessed and modified with `options.property` and `options.property = value`, respectively.

    - Command-line interface (CLI) parsers are automatically created and invoked once when the enb library is first
      imported. Default option values can be set with `-*` and `--*` arguments to any host code or `enb` entry point.

An important note should be made about the interaction between this module and ray.
When ray spawns new (local or remote) processes to serve as workers, the Options singleton
is initialized for each of those process, with the catch that ray uses different arguments.
To mitigate this problem, one can:

    1. Pass options as a parameter to remote functions, e.g., with ray.put(options)

    2. Use the `@enb.config.propagates_options` decorator for local functions
       that admit an `options` keyword argument. This way, the global `enb.confiog.options` singleton instance
       is correctly set to the same values as the orchestrating process.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "18/09/2019"

import sys
import os
import tempfile
import functools

import deprecation

import enb

singleton_cli = enb.singleton_cli
cli_property = singleton_cli.SingletonCLI.property
# cli_parsers_builder = singleton_cli.SingletonCLI.parsers_builder
calling_script_dir = os.path.realpath(os.path.dirname(os.path.abspath(sys.argv[0])))


class OptionsBase(enb.singleton_cli.SingletonCLI):
    """Base class for the global options available to all modules. This is needed so that @OptionsBase.property
    is properly defined.

    New options can be added to this by decorating any (self,value) method with `@GlobalOptions.property`.
    """
    pass


class GeneralGroup:
    @OptionsBase.property("v", action="count", default=0)
    def verbose(self, value):
        """Be verbose? Repeat for more.
        """
        pass


class ExecutionOptions:
    @OptionsBase.property("cpu_limit", "cpu_cunt",
                          group_name="Execution Options",
                          group_description="General execution options.",
                          type=int, default=None)
    def ray_cpu_limit(self, value):
        """Maximum number of virtual CPUs to use in the ray cluster.
        """
        return int(value)

    @OptionsBase.property("s", "not_parallel",
                          action="store_true", default=False)
    def sequential(self, value):
        """Make computations sequentially instead of distributed?

        When -s is set, local mode is use when initializing ray.

        This can be VERY useful to detect what parts of your code may be causing
        an exception while running a get_df() method.

        Furthermore, it can also help to limit the memory consumption of an experiment,
        which is also useful in case exceptions are due to lack of RAM.
        """
        return bool(value)

    @OptionsBase.property("f", "overwrite", action="count", default=0)
    def force(self, value):
        """Force calculation of pre-existing results, if available?

        Note that should an error occur while re-computing a given index,
        that index is dropped from the persistent support.
        """
        return int(value)

    @OptionsBase.property("q", "fast", action="count", default=0)
    def quick(self, value):
        """Perform a quick test with a subset of the input samples?

        If specified q>0 times, a subset of the first q target indices is employed
        in most get_df methods from ATable instances
        """
        return int(value)

    @OptionsBase.property("rep", "repetition_count", action=singleton_cli.PositiveIntegerAction, default=1, type=int)
    def repetitions(self, value):
        """Number of repetitions when calculating execution times.

        This value allows computation of more reliable execution times in some experiments, but
        is normally most representative in combination with -s to use a single execution process at a time.
        """
        singleton_cli.PositiveIntegerAction.assert_valid_value(value)

    @OptionsBase.property("c", "selected_columns", default=None, nargs="+", type=str)
    def columns(self, value):
        """List of selected column names for computation.

        If one or more column names are provided,
        all others are ignored. Multiple columns can be expressed,
        separated by spaces.
        Don't use this argument unless you know what you are doing, or expect potential exceptions.
        """
        assert value, f"At least one column must be defined"

    @OptionsBase.property(action="store_true", default=True)
    def exit_on_error(self, value):
        """If True, any exception when processing rows aborts the program.
        """
        return bool(value)

    @OptionsBase.property(action="store_true", default=False)
    def discard_partial_results(self, value):
        """Discard partial results when an error is found running the experiment?

        Otherwise, they are output to persistent storage.
        """
        return bool(value)

    @cli_property("no_new_data", "render_only", action="store_true", default=False)
    def no_new_results(self, value):
        """If True, ATable's get_df method relies entirely on the loaded persistence data, no new rows are computed.

        This can be useful to speed up the rendering process, for instance to try different
        aesthetic plotting options.
        """
        return bool(value)

    @OptionsBase.property("cs", default=None, type=int)
    def chunk_size(self, value):
        """Chunk size used when running ATable's get_df().
        Each processed chunk is made persistent before processing the next one.
        This parameter can be used to control the trade-off between error tolerance and overall speed.
        """
        pass


class RenderingOptions:
    """Options affecting the rendering of figures.
    """

    @OptionsBase.property("nr", "norender",
                          group_name="Rendering Options",
                          group_description="Options affecting the rendering of figures.",
                          action="store_true", default=False)
    def no_render(self, value):
        """If set, some rendering options will be skipped.
        """
        return bool(value)

    @OptionsBase.property("fw", "width",
                          default=5, type=float, action=singleton_cli.PositiveFloatAction)
    def fig_width(self, value):
        """Figure width.

        Larger values may make text look smaller when the image is scaled to a constant size.
        """
        singleton_cli.PositiveFloatAction.assert_valid_value(value)

    @OptionsBase.property("fh", "height",
                          default=4, type=float, action=singleton_cli.PositiveFloatAction)
    def fig_height(self, value):
        """Figure height.

        Larger values may make text look smaller when the image is scaled to a constant size.
        """
        singleton_cli.PositiveFloatAction.assert_valid_value(value)

    @OptionsBase.property("ylpos", default=-0.01, type=float)
    def global_y_label_pos(self, value):
        """Relative position of the global Y label.

        Can be negative or positive. Intended as a quick hack when left y-axis ticks are longer or shorter
        than the default assumptions.
        """
        return float(value)

    @OptionsBase.property("legend_count", default=2, type=int, action=singleton_cli.PositiveIntegerAction)
    def legend_column_count(self, value):
        """Number of columns used in plot legends.
        """
        singleton_cli.PositiveIntegerAction.assert_valid_value(value)

    @OptionsBase.property(action="store_true")
    def show_grid(self, value):
        """Show axis grid lines?
        """
        return bool(value)

    @OptionsBase.property("title", "global_title", type=str, default=None)
    def displayed_title(self, value):
        """When this property is not None, displayed plots will typically include its value as the main title.
        """
        return str(value)


class DirOptions:
    """Options regarding default data directories.
    """
    # Data dir
    default_base_dataset_dir = os.path.join(calling_script_dir, "datasets")

    @OptionsBase.property("d",
                          group_name="Data paths",
                          group_description="Options regarding default data directories.",
                          default=default_base_dataset_dir if os.path.isdir(default_base_dataset_dir) else None,
                          action=singleton_cli.ReadableDirAction)
    def base_dataset_dir(self, value):
        """Directory to be used as source of input files for indices in the get_df method
        of tables and experiments.

        It should be an existing, readable directory.
        """
        singleton_cli.ReadableDirAction.assert_valid_value(value)

    # Persistence dir
    default_persistence_dir = os.path.join(calling_script_dir, f"persistence_{os.path.basename(sys.argv[0])}")

    @OptionsBase.property("persistence", default=default_persistence_dir,
                          action=singleton_cli.WritableOrCreableDirAction)
    def persistence_dir(self, value):
        """Directory where persistence files are to be stored.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Reconstructed version dir
    @OptionsBase.property("reconstructed", default=None, action=singleton_cli.WritableOrCreableDirAction)
    def reconstructed_dir(self, value):
        """Base directory where reconstructed versions are to be stored.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Versioned data dir
    @OptionsBase.property("vd", "version_target_dir", action=singleton_cli.WritableOrCreableDirAction, default=None)
    def base_version_dataset_dir(self, value):
        """Base dir for versioned folders.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Temp dir
    for default_tmp_dir in ["/dev/shm", "/var/run", tempfile.gettempdir()]:
        try:
            singleton_cli.WritableDirAction.assert_valid_value(default_tmp_dir)
            break
        except AssertionError:
            pass
    else:
        default_tmp_dir = os.path.expanduser("~/enb_tmp")

    @OptionsBase.property("t", "tmp", "tmp_dir",
                          action=singleton_cli.WritableOrCreableDirAction,
                          default=default_tmp_dir)
    def base_tmp_dir(self, value):
        """Temporary dir used for intermediate data storage.

        This can be useful when experiments make heavy use of tmp and memory is limited,
        avoiding out-of-RAM crashes at the cost of potentially slower execution time.

        The dir is created when defined if necessary.
        """
        os.makedirs(value, exist_ok=True)
        singleton_cli.WritableDirAction.assert_valid_value(value)

    # Base dir for external binaries (e.g., codecs or other tools)
    default_external_binary_dir = os.path.join(calling_script_dir, "bin")
    default_external_binary_dir = default_external_binary_dir \
        if singleton_cli.ReadableDirAction.check_valid_value(default_external_binary_dir) else None

    @OptionsBase.property(action=singleton_cli.ReadableDirAction, default=default_external_binary_dir,
                          required=False)
    def external_bin_base_dir(self, value):
        """External binary base dir.

        In case a centralized repository is defined at the project or system level.
        """
        singleton_cli.ReadableDirAction.assert_valid_value(value)

    # Output plots dir
    default_output_plots_dir = os.path.join(calling_script_dir, "plots")
    default_output_plots_dir = default_output_plots_dir \
        if singleton_cli.WritableOrCreableDirAction.check_valid_value(default_output_plots_dir) else None

    @OptionsBase.property(
        action=singleton_cli.WritableOrCreableDirAction,
        default=default_output_plots_dir)
    def plot_dir(self, value):
        """Directory to store produced plots.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Output analysis dir
    default_analysis_dir = os.path.join(calling_script_dir, "analysis")
    default_analysis_dir = default_analysis_dir \
        if singleton_cli.WritableOrCreableDirAction.check_valid_value(default_analysis_dir) else None

    @OptionsBase.property("analysis",
                          action=singleton_cli.WritableOrCreableDirAction, default=default_analysis_dir)
    def analysis_dir(self, value):
        """Directory to store analysis results.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)


class Options(OptionsBase, GeneralGroup, ExecutionOptions, RenderingOptions, DirOptions):
    """Global options for all modules, without any positional or required argument.

    Classes wishing to expand the set of global options can be defined above,
    using the `@OptionsBase.property` decorator for new properties.
    Making :class:`Options` inherit from those classes is optional,
    but allows IDEs to automatically
    detect available properties in `enb.config.options`.

    Parameters in this class should defined so that no positional or otherwise mandatory
    arguments. This is due to interactions with ray for parallelization purposes, which
    results in `sys.argv` differing in the orchestrating and host processes.
    """
    pass


options = Options()
# Sanity check: verify singleton instance
assert options is Options(), f"The singleton property does not seem to be working ?!"

@deprecation.deprecated(deprecated_in="0.2.7", removed_in="0.3.1")
def get_options(from_main=False):
    """Deprecated - use `from enb.config import options`.
    """
    global options
    return options


def set_options(new_option_dict):
    """Update global options with a dictionary of values
    """
    global options
    if options is not new_option_dict:
        for k, v in new_option_dict.__dict__.items():
            options.__setattr__(k, v)


def propagates_options(f):
    """Decorator for local (as opposed to ray.remote) functions so that they
    propagate options properly to child workers.
    The decorated function must accept an "options" argument.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        set_options(kwargs["options"])
        return f(*args, **kwargs)

    return wrapper