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


class ExistingOrCreableDirAction(ExistingDirAction):
    """ArgumentParser action that verifies that argument is either an existing dir
    or a path where a new folder can be created
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a readable dir
        """
        try:
            ReadableDirAction.assert_valid_value(target_dir)
            return
        except AssertionError:
            parent_dir = os.path.dirname(target_dir)
            WritableDirAction.assert_valid_value(parent_dir)


_options = None


def get_options(allow_required=False):
    """Get a Namespace obtained from parsing command line arguments.

    :param allow_required: If allow_required is False, it is guaranteed that no
      required argument is used in the parser, so that options can be obtained
      without any arguments (e.g., for tests). Set this parameter to True
      when creating CLIs.

    :return: a Namespace obtained from parsing command line arguments.
    """
    global _options
    if _options is not None:
        return _options

    calling_dir = os.path.realpath(os.path.dirname(sys.argv[0]))

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-v", "--verbose", help="Be verbose? Repeat for more.", action="count", default=0)

    execution_options = parser.add_argument_group(
        "Execution options")
    execution_options.add_argument("-q", "--quick",
                                   help="Be quick? Retrieve a small subset of all files when requested for all.",
                                   action="count", default=0)
    execution_options.add_argument("-f", "--force",
                                   help="Force calculation of pre-existing results.",
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

    default_ray_config_file = os.path.join(calling_dir, "ray_cluster_head.txt")
    execution_options.add_argument("-r", "--ray_config_file", action=ReadableFileAction,
                                   default=default_ray_config_file,
                                   help="Ray server configuration path (must contain IP:port in its first line)")

    dir_options = parser.add_argument_group("Data dirs")
    # Data dir
    default_base_dataset_dir = os.path.join(calling_dir, "datasets")
    dir_options.add_argument("--base_dataset_dir", "-d", help=f"Base dir for dataset folders.",
                             default=default_base_dataset_dir if os.path.isdir(default_base_dataset_dir) else None,
                             required=allow_required and not ReadableDirAction.check_valid_dir(
                                 default_base_dataset_dir),
                             action=ReadableDirAction)

    # Versioned data dir
    default_version_dataset_dir = os.path.join(calling_dir, "versioned_datasets")
    dir_options.add_argument("--base_version_dataset_dir", "-vd",
                             action=ExistingOrCreableDirAction,
                             default=default_version_dataset_dir,
                             required=allow_required and False,
                             # required=not ExistingOrCreableDirAction.check_valid_dir(default_version_dataset_dir),
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
                             required=allow_required and not WritableDirAction.check_valid_dir(default_tmp_dir),
                             action=WritableDirAction,
                             default=default_tmp_dir, help=f"Temporary dir.")

    # Base dir for external binaries (e.g., codecs or other tools)
    default_external_binary_dir = os.path.join(calling_dir, "bin")
    default_external_binary_dir = default_external_binary_dir if os.path.isdir(default_external_binary_dir) else None
    dir_options.add_argument("--bin", "--external_bin_base_dir", help="External binary base dir.",
                             action=ReadableDirAction, default=default_external_binary_dir,
                             required=allow_required and False)

    _options = parser.parse_known_args()[0]
    return _options

# # Output dir where CSV files are to be output
# output_csv_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)),
#                               "output_csv")
# os.makedirs(output_csv_dir, exist_ok=True)
#
# # Path to the CSV file were all results are stored
# dataset_properties_csv_path = os.path.join(output_csv_dir, "dataset_properties.csv")
# # Experiment results csv
# output_experiment_csv_path = os.path.join(output_csv_dir, "experiment_results.csv")
# # Experiment + file information csv
# output_combined_experiment_csv_path = os.path.join(output_csv_dir, "experiment_and_file_info.csv")
#
# # Output dir for plots
# output_plot_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)),
#                                "output_plots")
# os.makedirs(output_plot_dir, exist_ok=True)
