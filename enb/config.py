#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Store and expose configuration options
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "18/09/2019"

import sys
import os
import tempfile
import argparse
import functools


class ValidationAction(argparse.Action):
    """Base class for defining custom parser validation actions.
    """

    @classmethod
    def assert_valid_value(cls, value):
        raise NotImplementedError()

    @classmethod
    def check_valid_value(cls, value):
        try:
            cls.assert_valid_value(value)
            return True
        except AssertionError:
            return False

    @classmethod
    def modify_value(cls, value):
        return value

    def __call__(self, parser, namespace, value, option_string=None):
        try:
            value = self.modify_value(value=value)
            self.assert_valid_value(value)
        except Exception as ex:
            parser.print_help()
            print()
            print(f"PARAMETER ERROR [{option_string}]: {ex}")
            parser.exit()
        setattr(namespace, self.dest, value)


class PathAction(ValidationAction):
    @classmethod
    def modify_value(cls, value):
        return os.path.abspath(os.path.realpath(os.path.expanduser(value)))


class ReadableFileAction(PathAction):
    """Validate that an argument is an existing file.
    """

    @classmethod
    def assert_valid_value(cls, value):
        return os.path.isfile(value) and os.access(value, os.R_OK)


class ExistingDirAction(PathAction):
    """ArgumentParser action that verifies that argument is an existing dir
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a readable dir
        """
        assert os.path.isdir(target_dir), f"{target_dir} should be an existing directory"


class ReadableDirAction(ExistingDirAction):
    """ArgumentParser action that verifies that argument is an existing,
    readable dir
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a readable dir
        """
        super().assert_valid_value(target_dir)
        assert os.access(target_dir, os.R_OK), f"Cannot read from directory {target_dir}"


class WritableDirAction(ExistingDirAction):
    """ArgumentParser action that verifies that argument is an existing,
    writable dir
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a readable dir
        """
        super().assert_valid_value(target_dir)
        assert os.access(target_dir, os.W_OK), f"Cannot write into directory {target_dir}"


class WritableOrCreableDirAction(ExistingDirAction):
    """ArgumentParser action that verifies that argument is either an existing dir
    or a path where a new folder can be created
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a writable dir, or its parent exists
        and is writable.
        """
        try:
            ReadableDirAction.assert_valid_value(target_dir)
        except AssertionError:
            parent_dir = os.path.dirname(target_dir)
            WritableDirAction.assert_valid_value(parent_dir)


#
class PositiveIntegerAction(ValidationAction):
    """Check that value is an integer and greater than zero.
    """

    @classmethod
    def assert_valid_value(cls, value):
        assert value == int(value)
        assert value > 0


_options = None


def get_options(from_main=False):
    """Get a Namespace obtained from parsing command line arguments.

    :param from_main: if from_main is False, it is guaranteed that no
      required argument is used in the parser, so that options can be obtained
      without any arguments (e.g., for tests). Set this parameter to True
      when creating CLIs. Note that from_main=True options must be parsed
      before any other module tries to access them.

    :return: a Namespace obtained from parsing command line arguments.
    """
    global _options
    if _options is not None:
        if from_main:
            raise ValueError("Trying to obtain options from_main=True, but _options "
                             "was already present")
        return _options

    calling_script_dir = os.path.realpath(os.path.dirname(sys.argv[0]))

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-v", "--verbose", help="Be verbose? Repeat for more.", action="count", default=0)

    execution_options = parser.add_argument_group(
        "Execution options")
    execution_options.add_argument("-q", "--quick",
                                   help="Be quick? Retrieve a small subset of all files when requested for all.",
                                   action="count", default=0)
    execution_options.add_argument("-f", "--force",
                                   help="Force calculation of pre-existing results. "
                                        "If an error occurs while re-computing "
                                        "a given index, that index is dropped from the persistent support.",
                                   action="count",
                                   default=0)
    execution_options.add_argument("-s", "--sequential",
                                   help="Make computations sequentially instead of distributed",
                                   action="store_true",
                                   default=False)
    execution_options.add_argument("--repetitions", help="Number of repetitions when calculating execution times.",
                                   action=PositiveIntegerAction, default=1, type=int)
    execution_options.add_argument("-c", "--columns",
                                   help="List of selected column names for computation. If one or more column names are provided, "
                                        "all others are ignored. Multiple columns can be expressed, separated by spaces.",
                                   default=None,
                                   nargs="+",
                                   type=str)
    execution_options.add_argument("--exit_on_error",
                                   help="If True, any exception when processing rows aborts the program.",
                                   action="store_true")
    execution_options.add_argument("--discard_partial_results",
                                   help="Discard partial results when an error is found running the experiment? "
                                        "Otherwise, they are output to persistent storage.",
                                   action="store_true")
    execution_options.add_argument("--no_new_results", help="Don't compute any new data. ",
                                   action="store_true", default=False)
    execution_options.add_argument("--chunk_size", "--cs", 
                                   help="Chunk size. Each processed chunk is made persistent "
                                        "before processing the next one.",
                                   default=None, type=int)

    render_options = parser.add_argument_group("Rendering options")
    render_options.add_argument("--no_render", "--nr",
                                help="Don't actually render data",
                                action="store_true",
                                default=False)
    render_options.add_argument("--fig_width", help="Figure width. Larger values make text look smaller.",
                                default=5, type=float)
    render_options.add_argument("--fig_height", help="Figure height. Larger values make text look smaller.",
                                default=4, type=float)
    render_options.add_argument("--global_y_label_pos", help="Relative position of the global Y label. Can be negative",
                                default=-0.01, type=float)
    render_options.add_argument("--legend_column_count", help="Number of columns used in plot legends",
                                default=2, type=int)
    render_options.add_argument("--show_grid", help="Show major axis grid?", action="store_true")
    render_options.add_argument("--displayed_title", help="Show title in rendered plots?", type=str, default=None)

    default_ray_config_file = os.path.join(calling_script_dir, "ray_cluster_head.txt")
    execution_options.add_argument("-r", "--ray_config_file", action=ReadableFileAction,
                                   default=default_ray_config_file,
                                   help="Ray server configuration path (must contain IP:port in its first line)")
    execution_options.add_argument("--ray_cpu_limit",
                                   help="CPU count limit for ray processes",
                                   type=int,
                                   default=None)

    dir_options = parser.add_argument_group("Data dirs")
    # Data dir
    default_base_dataset_dir = os.path.join(calling_script_dir, "datasets")
    dir_options.add_argument("--base_dataset_dir", "-d", help="Base dir for dataset folders.",
                             default=default_base_dataset_dir if os.path.isdir(default_base_dataset_dir) else None,
                             required=from_main and not ReadableDirAction.check_valid_value(
                                 default_base_dataset_dir),
                             action=ReadableDirAction)

    # Persistence dir
    default_persistence_dir = os.path.join(calling_script_dir, f"persistence_{os.path.basename(sys.argv[0])}")
    dir_options.add_argument("--persistence_dir",
                             default=default_persistence_dir,
                             action=WritableOrCreableDirAction,
                             help="Directory where persistence files are to be stored.")

    # Reconstructed version dir
    dir_options.add_argument("--reconstructed_dir",
                             default=None, action=WritableOrCreableDirAction,
                             help="Base directory where reconstructed versions are to be stored")
    dir_options.add_argument("--reconstructed_size",
                             default=None, type=int,
                             help="If not None, the size of the central region to be rendered in "
                                  "each component")

    # Versioned data dir
    dir_options.add_argument("--base_version_dataset_dir", "-vd",
                             action=WritableOrCreableDirAction,
                             default=None,
                             required=False,
                             # required=not WritableOrCreableDirAction.check_valid_value(default_version_dataset_dir),
                             help=f"Base dir for versioned folders.")

    # Temp dir
    for default_tmp_dir in ["/dev/shm", "/var/run", tempfile.gettempdir()]:
        try:
            WritableDirAction.assert_valid_value(default_tmp_dir)
            break
        except AssertionError:
            pass
    else:
        default_tmp_dir = None
    dir_options.add_argument("-t", "--base_tmp_dir",
                             required=from_main and not WritableDirAction.check_valid_value(default_tmp_dir),
                             action=WritableDirAction,
                             default=default_tmp_dir, help=f"Temporary dir.")

    # Base dir for external binaries (e.g., codecs or other tools)
    default_external_binary_dir = os.path.join(calling_script_dir, "bin")
    default_external_binary_dir = default_external_binary_dir \
        if ReadableDirAction.check_valid_value(default_external_binary_dir) else None
    dir_options.add_argument("--external_bin_base_dir", help="External binary base dir.",
                             action=ReadableDirAction, default=default_external_binary_dir,
                             required=False)

    # Output plots dir
    default_output_plots_dir = os.path.join(calling_script_dir, "plots")
    default_output_plots_dir = default_output_plots_dir \
        if WritableOrCreableDirAction.check_valid_value(default_output_plots_dir) else None
    dir_options.add_argument("--plot_dir", help="Directory to store produced plots.",
                             action=WritableOrCreableDirAction, default=default_output_plots_dir,
                             required=from_main and default_output_plots_dir is None)

    # Output analysis dir
    default_analysis_dir = os.path.join(calling_script_dir, "analysis")
    default_analysis_dir = default_analysis_dir \
        if WritableOrCreableDirAction.check_valid_value(default_analysis_dir) else None
    dir_options.add_argument("--analysis_dir", help="Directry to store analysis results.",
                             action=WritableOrCreableDirAction, default=default_analysis_dir,
                             required=from_main and default_analysis_dir is None)

    if from_main:
        _options = parser.parse_args()
    else:
        _options = parser.parse_known_args()[0]

    return _options


def set_options(new_options):
    """Replace the current
    """
    global _options
    if _options is not new_options:
        _options = _options if _options is not None else argparse.Namespace()
        for k, v in new_options.__dict__.items():
            _options.__setattr__(k, v)


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
