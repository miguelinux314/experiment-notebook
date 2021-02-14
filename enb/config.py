#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Store and expose configuration options.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "18/09/2019"

import sys
import os
import tempfile
import argparse
import functools

import enb


singleton_cli = enb.singleton_cli
cli_property = singleton_cli.SingletonCLI.property
calling_script_dir = os.path.realpath(os.path.dirname(os.path.abspath(sys.argv[0])))


class ExecutionOptions(singleton_cli.GlobalOptions):
    @cli_property("f",
                  group_name="Execution Options",
                  help="""Force calculation of pre-existing results. 
        If an error occurs while re-computing 
        a given index, that index is dropped from the persistent support.""",
                  action="count",
                  default=0)
    def force(self):
        pass

    @cli_property("q", action="count", default=0)
    def quick(self):
        """Be quick? Retrieve a small subset of all files when requested for all.
        """
        pass

    @cli_property("s",
                  help="Make computations sequentially instead of distributed",
                  action="store_true",
                  default=False)
    def sequential(self):
        pass

    @cli_property(help="Number of repetitions when calculating execution times.",
                  action=singleton_cli.PositiveIntegerAction, default=1, type=int)
    def repetitions(self):
        pass

    @cli_property("c",
                  help="List of selected column names for computation. If one or more column names are provided, "
                       "all others are ignored. Multiple columns can be expressed, separated by spaces.",
                  default=None,
                  nargs="+",
                  type=str)
    def columns(self):
        pass

    @cli_property(help="If True, any exception when processing rows aborts the program.", action="store_true",
                  default=True)
    def exit_on_error(self):
        pass

    @cli_property(help="Discard partial results when an error is found running the experiment? "
                       "Otherwise, they are output to persistent storage.",
                  action="store_true")
    def discard_partial_results(self):
        pass

    @cli_property(help="Don't compute any new data. ",
                  action="store_true", default=False)
    def no_new_results(self):
        pass

    @cli_property("cs",
                  help="Chunk size. Each processed chunk is made persistent "
                       "before processing the next one.",
                  default=None, type=int)
    def chunk_size(self):
        pass


class RenderingOptions(singleton_cli.GlobalOptions):
    @cli_property("nr",
                  group_name="Rendering Options",
                  help="Don't actually render data",
                  action="store_true",
                  default=False)
    def no_render(self):
        pass

    @cli_property("fw", help="Figure width. Larger values make text look smaller.", default=5, type=float)
    def fig_width(self):
        pass

    @cli_property("fig_height", help="Figure height. Larger values make text look smaller.",
                  default=4, type=float)
    def fig_height(self):
        pass

    @cli_property(help="Relative position of the global Y label. Can be negative",
                  default=-0.01, type=float)
    def global_y_label_pos(self):
        pass

    @cli_property(help="Number of columns used in plot legends",
                  default=2, type=int)
    def legend_column_count(self):
        pass

    @cli_property(help="Show major axis grid?", action="store_true")
    def show_grid(self):
        pass

    @cli_property(help="Show title in rendered plots?", type=str, default=None)
    def displayed_title(self):
        pass


class RayOptions(singleton_cli.GlobalOptions):
    default_ray_config_file = os.path.join(calling_script_dir, "ray_cluster_head.txt")

    @cli_property(group_name="Ray Options",
                  action=singleton_cli.ReadableFileAction,
                  default=default_ray_config_file,
                  help="Ray server configuration path (must contain IP:port in its first line)")
    def ray_config_file(self):
        pass

    @cli_property(help="CPU count limit for ray processes", type=int, default=None)
    def ray_cpu_limit(self):
        pass


class DirOptions(singleton_cli.GlobalOptions):
    # Data dir
    default_base_dataset_dir = os.path.join(calling_script_dir, "datasets")

    @cli_property("d",
                  group_name="Data directories",
                  help="Base dir for dataset folders.",
                  default=default_base_dataset_dir if os.path.isdir(default_base_dataset_dir) else None,
                  action=singleton_cli.ReadableDirAction)
    def base_dataset_dir(self):
        pass

    # Persistence dir
    default_persistence_dir = os.path.join(calling_script_dir, f"persistence_{os.path.basename(sys.argv[0])}")

    @cli_property(default=default_persistence_dir,
                  action=singleton_cli.WritableOrCreableDirAction,
                  help="Directory where persistence files are to be stored.")
    def persistence_dir(self):
        pass

    # Reconstructed version dir
    @cli_property(default=None, action=singleton_cli.WritableOrCreableDirAction,
                  help="Base directory where reconstructed versions are to be stored")
    def reconstructed_dir(self):
        pass

    @cli_property(default=None, type=int,
                  help="If not None, the size of the central region to be rendered in "
                       "each component")
    def reconstructed_size(self):
        pass

    # Versioned data dir
    @cli_property("vd",
                  action=singleton_cli.WritableOrCreableDirAction,
                  default=None,
                  required=False,
                  help=f"Base dir for versioned folders.")
    def base_version_dataset_dir(self):
        pass

    # Temp dir
    for default_tmp_dir in ["/dev/shm", "/var/run", tempfile.gettempdir()]:
        try:
            singleton_cli.WritableDirAction.assert_valid_value(default_tmp_dir)
            break
        except AssertionError:
            pass
    else:
        default_tmp_dir = None

    @cli_property("t", action=singleton_cli.WritableDirAction,
                  default=default_tmp_dir, help=f"Temporary dir.")
    def base_tmp_dir(self):
        pass

    # Base dir for external binaries (e.g., codecs or other tools)
    default_external_binary_dir = os.path.join(calling_script_dir, "bin")
    default_external_binary_dir = default_external_binary_dir \
        if singleton_cli.ReadableDirAction.check_valid_value(default_external_binary_dir) else None

    @cli_property(help="External binary base dir.",
                  action=singleton_cli.ReadableDirAction, default=default_external_binary_dir,
                  required=False)
    def external_bin_base_dir(self):
        pass

    # Output plots dir
    default_output_plots_dir = os.path.join(calling_script_dir, "plots")
    default_output_plots_dir = default_output_plots_dir \
        if singleton_cli.WritableOrCreableDirAction.check_valid_value(default_output_plots_dir) else None

    @cli_property(help="Directory to store produced plots.",
                  action=singleton_cli.WritableOrCreableDirAction,
                  default=default_output_plots_dir)
    def plot_dir(self):
        pass

    # Output analysis dir
    default_analysis_dir = os.path.join(calling_script_dir, "analysis")
    default_analysis_dir = default_analysis_dir \
        if singleton_cli.WritableOrCreableDirAction.check_valid_value(default_analysis_dir) else None

    @cli_property("analysis_dir", help="Directory to store analysis results.",
                  action=singleton_cli.WritableOrCreableDirAction, default=default_analysis_dir)
    def analysis_dir(self):
        pass


def get_options(from_main=False):
    """Deprecated - use enb.config.options isntead.
    """
    global options
    return options


def set_options(new_options):
    """Replace the current
    """
    global options
    if options is not new_options:
        for k, v in new_options.__dict__.items():
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


class AllOptions(ExecutionOptions, RenderingOptions, RayOptions, DirOptions):
    """Compendium of options available by default in enb
    """
    pass


# Modules should use config.options
options = AllOptions()

# Verify singleton instance
assert options is AllOptions()