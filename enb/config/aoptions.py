#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Implementation of the classes for the enb.config.options and CLI interface

Option configuration in enb is centralized through enb.config.options. Several key aspects should be highlighted:

    - Properties defined in `enb.config.options` are used by enb modules, and can also be used by
      scripts using enb (host scripts).

    - Many core enb functions have optional arguments with default None values.
      Those functions will often substitute None for the corresponding value in enb.config.options,
      e.g., to locate the plot output directory.

    - Scripts using enb (host scripts) may alter values in enb.config.options, e.g., before calling enb methods.
      Properties are accessed and modified with `enb.config.options.property`
      and `enb.config.property = value`, respectively. You may want to use the `from enb.config import options` line
      in your host scripts to enable less verbosity.

    - The CLI can be used to set initial values of enb.config.options properties using `-*` and `--*` arguments.
      Running with `-h` any script that imports enb will show you detailed help on all available options and
      their default values.

    - The default values for enb.config.options and its CLI is obtained through enb.config.ini, described below.

An important note should be made about the interaction between enb.config.options and ray.
When ray spawns new (local or remote) processes to serve as workers, the Options singleton
is initialized for each of those process, with the catch that ray does **not** pass the user's CLI parameters.
Therefore, different enb.config.option values would be present in the parent script and the ray workers.
To mitigate this problem, an `options` parameter is defined and passed to many these functions,
e.g., with `f.remote(options=ray.put(enb.config.options))` if f is your `@ray.remote`-decorated function.
The `@enb.config.propagates_options` decorator provides a slightly cleaner way of automating
this mitigation.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__since__ = "04/08/2019"

import os
import tempfile
import functools
import deprecation
import enb
from . import singleton_cli as _singleton_cli


class OptionsBase(_singleton_cli.SingletonCLI):
    """Global options for all modules, without any positional or required argument.
    """
    pass


@_singleton_cli.property_class(OptionsBase)
class GeneralOptions:
    """Group of uncategorized options.
    """

    @OptionsBase.property("v", action="count")
    def verbose(self, value):
        """Be verbose? Repeat for more.
        """
        pass

    @OptionsBase.property("ini", nargs="*", type=str, default=[])
    def extra_ini_paths(self, value):
        """Additional .ini files to be used to attain file-based configurations,
        in addition to the default ones (system, user and project).
        If defined more than once, the last definition sets the list instead of appending
        to a common list of extra ini paths.
        """
        pass


@_singleton_cli.property_class(OptionsBase)
class ExecutionOptions:
    """General execution options.
    """

    @OptionsBase.property("cpu_limit", "cpu_cunt", type=int)
    def ray_cpu_limit(self, value):
        """Maximum number of virtual CPUs to use in the ray cluster.
        If set to None or any number n <= 0, then no limits are set in terms of virtual CPU usage.

        IMPORTANT: this value is only considered when initializing a ray cluster. Therefore, changing
        it afterwards will not change ray cpu limits.
        """
        if value is None:
            return value
        value = int(value)
        if value <= 0:
            value = None
        return value

    @OptionsBase.property("s", "not_parallel", action="store_true")
    def sequential(self, value):
        """Make computations sequentially instead of distributed?

        When -s is set, local mode is use when initializing ray.

        This can be VERY useful to detect what parts of your code may be causing
        an exception while running a get_df() method.

        Furthermore, it can also help to limit the memory consumption of an experiment,
        which is also useful in case exceptions are due to lack of RAM.
        """
        return bool(value)

    @OptionsBase.property("f", "overwrite", action="count")
    def force(self, value):
        """Force calculation of pre-existing results, if available?

        Note that should an error occur while re-computing a given index,
        that index is dropped from the persistent support.
        """
        return int(value)

    @OptionsBase.property("q", "fast", action="count")
    def quick(self, value):
        """Perform a quick test with a subset of the input samples?

        If specified q>0 times, a subset of the first q target indices is employed
        in most get_df methods from ATable instances
        """
        return int(value)

    @OptionsBase.property("rep", "repetition_count", "rep_count",
                          action=_singleton_cli.PositiveIntegerAction)
    def repetitions(self, value):
        """Number of repetitions when calculating execution times.

        This value allows computation of more reliable execution times in some experiments, but
        is normally most representative in combination with -s to use a single execution process at a time.
        """
        _singleton_cli.PositiveIntegerAction.assert_valid_value(value)

    @OptionsBase.property("c", "selected_columns", nargs="+", type=str)
    def columns(self, value):
        """List of selected column names for computation.

        If one or more column names are provided,
        all others are ignored. Multiple columns can be expressed,
        separated by spaces.
        Don't use this argument unless you know what you are doing, or expect potential exceptions.
        """
        assert value, f"At least one column must be defined"

    @OptionsBase.property(action="store_true")
    def exit_on_error(self, value):
        """If True, any exception when processing rows aborts the program.
        """
        return bool(value)

    @OptionsBase.property(action="store_true")
    def discard_partial_results(self, value):
        """Discard partial results when an error is found running the experiment?

        Otherwise, they are output to persistent storage.
        """
        return bool(value)

    @OptionsBase.property("no_new_data", "render_only", action="store_true")
    def no_new_results(self, value):
        """If True, ATable's get_df method relies entirely on the loaded persistence data, no new rows are computed.

        This can be useful to speed up the rendering process, for instance to try different
        aesthetic plotting options.
        """
        return bool(value)

    @OptionsBase.property("cs", type=int)
    def chunk_size(self, value):
        """Chunk size used when running ATable's get_df().
        Each processed chunk is made persistent before processing the next one.
        This parameter can be used to control the trade-off between error tolerance and overall speed.
        """
        pass


@_singleton_cli.property_class(OptionsBase)
class RenderingOptions:
    """Options affecting the rendering of figures.
    """

    @OptionsBase.property("nr", "norender", action="store_true")
    def no_render(self, value):
        """If set, some rendering options will be skipped.
        """
        return bool(value)

    @OptionsBase.property("fw", "width", action=_singleton_cli.PositiveFloatAction)
    def fig_width(self, value):
        """Figure width.

        Larger values may make text look smaller when the image is scaled to a constant size.
        """
        _singleton_cli.PositiveFloatAction.assert_valid_value(value)

    @OptionsBase.property("fh", "height", action=_singleton_cli.PositiveFloatAction)
    def fig_height(self, value):
        """Figure height.

        Larger values may make text look smaller when the image is scaled to a constant size.
        """
        _singleton_cli.PositiveFloatAction.assert_valid_value(value)

    @OptionsBase.property("ylpos", type=float)
    def global_y_label_pos(self, value):
        """Relative position of the global Y label.

        Can be negative or positive. Intended as a quick hack when left y-axis ticks are longer or shorter
        than the default assumptions.
        """
        return float(value)

    @OptionsBase.property("legend_count", action=_singleton_cli.PositiveIntegerAction)
    def legend_column_count(self, value):
        """Number of columns used in plot legends.
        """
        _singleton_cli.PositiveIntegerAction.assert_valid_value(value)

    @OptionsBase.property(action="store_true")
    def show_grid(self, value):
        """Show axis grid lines?
        """
        return bool(value)

    @OptionsBase.property("title", "global_title", type=str)
    def displayed_title(self, value):
        """When this property is not None, displayed plots will typically include its value as the main title.
        """
        return str(value)


@_singleton_cli.property_class(OptionsBase)
class DirOptions:
    """Options regarding default data directories.
    """

    @OptionsBase.property("d", action=_singleton_cli.ReadableDirAction, default=enb.default_base_dataset_dir)
    def base_dataset_dir(self, value):
        """Directory to be used as source of input files for indices in the get_df method
        of tables and experiments.

        It should be an existing, readable directory.
        """
        _singleton_cli.ReadableDirAction.assert_valid_value(value)

    @OptionsBase.property("persistence", action=_singleton_cli.WritableOrCreableDirAction,
                          default=enb.default_persistence_dir)
    def persistence_dir(self, value):
        """Directory where persistence files are to be stored.
        """
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Reconstructed version dir
    @OptionsBase.property("reconstructed", action=_singleton_cli.WritableOrCreableDirAction)
    def reconstructed_dir(self, value):
        """Base directory where reconstructed versions are to be stored.
        """
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Versioned data dir
    @OptionsBase.property("vd", "version_target_dir", action=_singleton_cli.WritableOrCreableDirAction,
                          default=enb.default_base_dataset_dir)
    def base_version_dataset_dir(self, value):
        """Base dir for versioned folders.
        """
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Temp dir
    for default_tmp_dir in ["/dev/shm", "/var/run", tempfile.gettempdir()]:
        try:
            _singleton_cli.WritableDirAction.assert_valid_value(default_tmp_dir)
            break
        except AssertionError:
            pass
    else:
        default_tmp_dir = os.path.expanduser("~/enb_tmp")

    @OptionsBase.property("t", "tmp", "tmp_dir",
                          action=_singleton_cli.WritableOrCreableDirAction,
                          default=default_tmp_dir)
    def base_tmp_dir(self, value):
        """Temporary dir used for intermediate data storage.

        This can be useful when experiments make heavy use of tmp and memory is limited,
        avoiding out-of-RAM crashes at the cost of potentially slower execution time.

        The dir is created when defined if necessary.
        """
        os.makedirs(value, exist_ok=True)
        _singleton_cli.WritableDirAction.assert_valid_value(value)

    # Base dir for external binaries (e.g., codecs or other tools)
    default_external_binary_dir = os.path.join(enb.calling_script_dir, "bin")
    default_external_binary_dir = default_external_binary_dir \
        if _singleton_cli.ReadableDirAction.check_valid_value(default_external_binary_dir) else None

    @OptionsBase.property(action=_singleton_cli.ReadableDirAction, default=default_external_binary_dir,
                          required=False)
    def external_bin_base_dir(self, value):
        """External binary base dir.

        In case a centralized repository is defined at the project or system level.
        """
        _singleton_cli.ReadableDirAction.assert_valid_value(value)

    # Output plots dir
    default_output_plots_dir = os.path.join(enb.calling_script_dir, "plots") \
        if not enb.is_enb_cli else "./plots"

    @OptionsBase.property(
        action=_singleton_cli.WritableOrCreableDirAction,
        default=default_output_plots_dir)
    def plot_dir(self, value):
        """Directory to store produced plots.
        """
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Output analysis dir
    default_analysis_dir = os.path.join(enb.calling_script_dir, "analysis") \
        if not enb.is_enb_cli else "./analysis"

    @OptionsBase.property("analysis",
                          action=_singleton_cli.WritableOrCreableDirAction, default=default_analysis_dir)
    def analysis_dir(self, value):
        """Directory to store analysis results.
        """
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)


class Options(OptionsBase, GeneralOptions, ExecutionOptions, RenderingOptions, DirOptions):
    """Class of the `enb.config.options` object, which exposes
    options for all modules, allowing CLI-based parameter setting.

    Classes wishing to expand the set of global options can be defined above,
    using the @OptionsBase.property decorator for new properties.
    Making :class:`Options` inherit from those classes is optional,
    but allows IDEs to automatically
    detect available properties in `enb.config.options`.

    Parameters in this class should defined so that no positional or otherwise mandatory
    arguments. This is due to interactions with ray for parallelization purposes, which
    results in `sys.argv` differing in the orchestrating and host processes.
    """
    pass


@deprecation.deprecated(deprecated_in="0.2.7", removed_in="0.3.0")
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


options = Options()
assert options is Options(), "Singleton not working"
