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

    def __call__(self, parser, namespace, values, option_string=None):
        target_dir = values
        try:
            self.assert_valid_value(target_dir)
        except AssertionError as ex:
            parser.print_help()
            print()
            print(f"PARAMETER ERROR [{option_string}]: {ex}")
            parser.exit()
        setattr(namespace, self.dest, target_dir)


class ReadableFileAction(ValidationAction):
    """Validate that an argument is an existing file.
    """

    @classmethod
    def assert_valid_value(cls, value):
        return os.path.isfile(value) and os.access(value, os.R_OK)


class ExistingDirAction(ValidationAction):
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
            return
        except AssertionError:
            parent_dir = os.path.dirname(target_dir)
            WritableDirAction.assert_valid_value(parent_dir)


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
    execution_options.add_argument("--no_render", "--nr",
                                   help="Don't actually render data",
                                   action="store_true",
                                   default=False)
    execution_options.add_argument("-c", "--columns",
                                   help="List of selected column names for computation. If one or more column names are provided, "
                                        "all others are ignored. Multiple columns can be expressed, separated by spaces.",
                                   default=None,
                                   nargs="+",
                                   type=str)
    execution_options.add_argument("--discard_partial_results",
                                   help="Discard partial results when an error is found running the experiment? "
                                        "Otherwise, they are output to persistent storage.",
                                   action="store_true")

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

    # Versioned data dir
    default_version_dataset_dir = os.path.join(calling_script_dir, "versioned_datasets")
    dir_options.add_argument("--base_version_dataset_dir", "-vd",
                             action=WritableOrCreableDirAction,
                             default=default_version_dataset_dir,
                             required=from_main and False,
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
