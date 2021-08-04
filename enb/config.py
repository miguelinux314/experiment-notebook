#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# The config module

## Introduction

The config module deals with two main aspects:

    1. It provides the enb.config.options object with global configurations shared among enb
       modules and accessible to scripts using enb.
       These options can be accessed and set programmatically (e.g., `enb.config.options.verbose += 1`),
       and also through the CLI (see details below, or run with `-h` a python script that imports enb).

    2. It provides the enb.config.ini object to access properties defined in `.ini` files.
       These affect the default CLI values and can be easily extended by users to support
       file-based configuration. See below for details on this part.

Both `enb.config.options` and `enb.config.ini` are `argparse.Namespace` instances.
After a more detailed description of these two tools,
a summary of configuration setting priority is also provided.

## enb.config.options and CLI interface

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

## enb.config.ini file-based configuration

The enb framework supports configuration files with `.ini` extension and format
compatible with python's configparser (https://docs.python.org/3/library/configparser.html#module-configparser),
e.g., similar to Window's INI files.

File-based configuration is used to determine the default value of enb.config.options and its CLI.
Furthermore, users may easily extend file-based configuration to their own needs.

When enb is imported, the following configuration files are read, in the given order.
Order is important because read properties overwrite any previously set values.

1. The `enb.ini` file provided with the enb library installation.

2. The `enb.ini` at the user's enb configuration dir. This path will be determined using the appdirs library,
   and will depend on the OS. In many linux boxes, this dir is `~/.config/enb`.

3. All `*.ini` files defined in the same folder as the called script, in lexicographical,
   case ignorant, order. No recursive folder search is performed.

## Effective parameter values

Based on the above description, the values in `enb.config.options` will be given by the first
of these options:

1. Programmatically set properties, e.g., `enb.config.options.verbose += 2`.
   The last set value is used.
2. Parameters `-*` and `-**` passed directly to the invoked script.
3. Default CLI parameters specified in any `*.ini` files in the same folder as the invoked script
   (this can be empty).
4. Default CLI parameters specified in any `*.ini` files in enb's configuration file (e.g., `~/.config/enb/enb.ini`).

From there on, many enb functions adhere to the following principle:

1. If a parameter is set to a non-None value, that value is used.
2. If a parameter with default value None is set to None or not specified,
   its value is set based on the properties in `enb.config.options`.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "18/09/2019"

import sys
import os
import glob
import tempfile
import functools
import deprecation
import argparse
import configparser

import enb
from enb import singleton_cli


# Classes needed to provided enb.config.ini

class Ini(metaclass=enb.singleton_cli.Singleton):
    """Class of the enb.config.ini object, that exposes file-defined configurations.
    """
    global_ini_path = os.path.join(enb.enb_installation_dir, "enb.ini")
    user_ini_path = os.path.join(enb.user_config_dir, "enb.ini")
    local_ini_paths = sorted(glob.glob(os.path.join(enb.calling_script_dir, "*.ini")),
                             key=lambda s: os.path.basename(s).lower())

    def __init__(self):
        super().__init__()
        # Keep track of what config files have been used to get the final result
        self.used_config_paths = []

        # Parse configuration files with the specified prioritization
        self.config_parser = configparser.ConfigParser()
        self.update_from_path(self.global_ini_path)
        if os.path.exists(self.user_ini_path):
            self.update_from_path(self.user_ini_path)
        for ini_path in self.local_ini_paths:
            self.update_from_path(ini_path)

    def update_from_path(self, ini_path):
        """Update the current configuration by reading the contents of ini_path.
        """
        self.config_parser.read(ini_path)
        self.used_config_paths.append(ini_path)

    @property
    def sections_by_name(self):
        """Get a list of all configparser.Section instances, including the default section.
        """
        return list(self.config_parser.items())

    def __getitem__(self, item):
        return self.config_parser.__getitem__(item)


# The enb.config.ini instance shared by all modules
ini = Ini()
assert ini is Ini(), "Singleton not working"

# Classes needed to provided enb.config.options

class OptionsBase(enb.singleton_cli.SingletonCLI):
    """Global options for all modules, without any positional or required argument.
    """
    pass


@enb.singleton_cli.property_class(OptionsBase)
class GeneralOptions:
    """Group of uncategorized options.
    """

    @OptionsBase.property("v", action="count", default=0)
    def verbose(self, value):
        """Be verbose? Repeat for more.
        """
        pass


@enb.singleton_cli.property_class(OptionsBase)
class ExecutionOptions:
    """General execution options.
    """

    @OptionsBase.property("cpu_limit", "cpu_cunt", type=int, default=None)
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

    @OptionsBase.property("s", "not_parallel", action="store_true", default=False)
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

    @OptionsBase.property("rep", "repetition_count", "rep_count",
                          action=singleton_cli.PositiveIntegerAction, default=1, type=int)
    def repetitions(self, value):
        """Number of repetitions when calculating execution times.

        This value allows computation of more reliable execution times in some experiments, but
        is normally most representative in combination with -s to use a single execution process at a time.
        """
        singleton_cli.PositiveIntegerAction.assert_valid_value(value)

    @OptionsBase.property("c", "selected_columns",
                          default=None, nargs="+", type=str)
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

    @OptionsBase.property("no_new_data", "render_only", action="store_true", default=False)
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


@enb.singleton_cli.property_class(OptionsBase)
class RenderingOptions:
    """Options affecting the rendering of figures.
    """

    @OptionsBase.property("nr", "norender", action="store_true", default=False)
    def no_render(self, value):
        """If set, some rendering options will be skipped.
        """
        return bool(value)

    @OptionsBase.property("fw", "width", default=5, type=float, action=singleton_cli.PositiveFloatAction)
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


@enb.singleton_cli.property_class(OptionsBase)
class DirOptions:
    """Options regarding default data directories.
    """
    # Data dir
    default_base_dataset_dir = os.path.join(enb.calling_script_dir, "datasets")

    @OptionsBase.property("d",
                          default=default_base_dataset_dir if os.path.isdir(default_base_dataset_dir) else None,
                          action=singleton_cli.ReadableDirAction)
    def base_dataset_dir(self, value):
        """Directory to be used as source of input files for indices in the get_df method
        of tables and experiments.

        It should be an existing, readable directory.
        """
        singleton_cli.ReadableDirAction.assert_valid_value(value)

    # Persistence dir
    default_persistence_dir = os.path.join(enb.calling_script_dir, f"persistence_{os.path.basename(sys.argv[0])}")

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
    default_external_binary_dir = os.path.join(enb.calling_script_dir, "bin")
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
    default_output_plots_dir = os.path.join(enb.calling_script_dir, "plots")
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
    default_analysis_dir = os.path.join(enb.calling_script_dir, "analysis")
    default_analysis_dir = default_analysis_dir \
        if singleton_cli.WritableOrCreableDirAction.check_valid_value(default_analysis_dir) else None

    @OptionsBase.property("analysis",
                          action=singleton_cli.WritableOrCreableDirAction, default=default_analysis_dir)
    def analysis_dir(self, value):
        """Directory to store analysis results.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)


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


# The enb.config.options instance shared by all modules
options = Options()
assert options is Options(), "Singleton not working"


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
