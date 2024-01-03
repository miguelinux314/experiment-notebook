#!/usr/bin/env python3
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
To mitigate this problem, the @`enb.parallel_ray.remote` decorator is provided in substitution of :meth:`ray.remote`
so that options at the time of calling the remote method are available to that method at
its regular location (enb.config.options).
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/08/04"

import os
import tempfile
import functools
import deprecation

from .. import default_base_dataset_dir
from .. import default_persistence_dir
from .. import default_output_plots_dir
from .. import default_analysis_dir
from .. import calling_script_dir
from . import ini
from . import singleton_cli as _singleton_cli

# Allowed message types
_logging_level_names = ["core", "error", "warning", "message", "verbose", "informative", "debug"]


class OptionsBase(_singleton_cli.SingletonCLI):
    """Global options for all modules, without any positional or required argument.
    """

    @property
    def non_default_properties(self):
        non_default_properties = dict()
        for k, v in self._name_to_property.items():
            try:
                if v == ini.get_key("enb.config.options", k):
                    continue
            except KeyError:
                pass
            non_default_properties[k] = v
        non_default_properties["verbose"] = self.verbose
        return non_default_properties

    def normalize_dir_value(self, value):
        if value[0] == os.sep:
            value = os.path.relpath(value, self.project_root)
        return value

    def __str__(self):
        s = "Summary of enb.config.options:\n\t- "
        s += "\n\t- ".join(f"{k:30s} = {repr(v)}"
                           for k, v in sorted(self.non_default_properties.items())
                           if k[0] != "_")
        return s


@_singleton_cli.property_class(OptionsBase)
class GeneralOptions:
    """Group of uncategorized options.
    """

    @OptionsBase.property("v", action="count")
    def verbose(self, value):
        """Be verbose? Repeat for more. Change at any time to increase the logger's verbosity.
        """
        from .. import log

        log.logger.selected_log_level = log.get_level(
            name=log.logger.level_message.name, lower_priority=float(value))

        return value

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

    @OptionsBase.property(type=int)
    def cpu_limit(self, value):
        """Maximum number of CPUs to use for computation in this machine
        See https://miguelinux314.github.io/experiment-notebook/cluster_setup.html for
        details on how to set the resources employed in remote computation nodes.
        """
        if value is None:
            return value
        value = int(value)
        if value <= 0:
            value = None
        return value

    @OptionsBase.property("f", "overwrite", action="count")
    def force(self, value):
        """Force calculation of pre-existing results, if available?

        Note that should an error occur while re-computing a given index,
        that index is dropped from the persistent support.
        """
        return int(value)

    @OptionsBase.property("q", action="count")
    def quick(self, value):
        """Perform a quick test with a subset of the input samples?

        If specified q>0 times, a subset of the first q target indices is employed
        in most get_df methods from ATable instances
        """
        return int(value)

    @OptionsBase.property("render_only", action="store_true")
    def no_new_results(self, value):
        """If True, ATable's get_df method relies entirely on the loaded persistence data, no new rows are computed.
        This can be useful to speed up the rendering process, for instance to try different
        aesthetic plotting options. Use this option only if you know you need it.
        """
        return bool(value)

    @OptionsBase.property(type=int)
    def chunk_size(self, value):
        """Chunk size used when running ATable's get_df().
        Each processed chunk is made persistent before processing the next one.
        This parameter can be used to control the trade-off between error tolerance and overall speed.
        """
        return int(value)

    @OptionsBase.property(action=_singleton_cli.PositiveIntegerAction)
    def repetitions(self, value):
        """Number of repetitions when calculating execution times.

        This value allows computation of more reliable execution times in some experiments, but
        is normally most representative in combination with -s to use a single execution process at a time.
        """
        _singleton_cli.PositiveIntegerAction.assert_valid_value(value)
        return int(value)

    @OptionsBase.property(action="store_true")
    def report_wall_time(self, value):
        """If this flag is activated, the wall time instead of the CPU time is reported by default by
        tcall.get_status_output_time.
        """
        return bool(value)

    @OptionsBase.property(action="store_true")
    def force_sanity_checks(self, value):
        """If this flag is used, extra sanity checks are performed by enb during the execution of this script.
        The trade-off for rare error condition detection is a slower execution time.
        """
        return bool(value)

    @OptionsBase.property(nargs="+", type=str)
    def selected_columns(self, value):
        """List of selected column names for computation.

        If one or more column names are provided,
        all others are ignored. Multiple columns can be expressed,
        separated by spaces.
        """
        assert value, f"If provided, at least one column must be defined"

    @OptionsBase.property(type=float)
    def progress_report_period(self, value):
        """Default minimum time in seconds between progress report updates,
         when get_df() is invoked and computation is being processed in parallel.
         """
        return float(value)

    @OptionsBase.property(action="store_true")
    def disable_progress_bar(self, value):
        """If this flag is enabled, no progress bar is employed
        (useful to minimize the stdout volume of long-running experiments).
        """
        return bool(value)


@_singleton_cli.property_class(OptionsBase)
class DirOptions:
    """Options regarding default data directories.
    """

    @OptionsBase.property(action=_singleton_cli.ReadableDirAction, default=calling_script_dir)
    def project_root(self, value):
        """Project root path. It should not normally be modified.
        """
        _singleton_cli.ReadableDirAction.assert_valid_value(value)

    @OptionsBase.property(action=_singleton_cli.ReadableOrCreableDirAction, default=default_base_dataset_dir)
    def base_dataset_dir(self, value):
        """Directory to be used as source of input files for indices in the get_df method
        of tables and experiments.

        It should be an existing, readable directory.
        """
        value = self.normalize_dir_value(value=value)
        _singleton_cli.ReadableOrCreableDirAction.assert_valid_value(value)
        return value

    @OptionsBase.property(action=_singleton_cli.WritableOrCreableDirAction,
                          default=default_persistence_dir)
    def persistence_dir(self, value):
        """Directory where persistence files are to be stored.
        """
        value = self.normalize_dir_value(value=value)
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)
        return value

    # Reconstructed version dir
    @OptionsBase.property(action=_singleton_cli.WritableOrCreableDirAction)
    def reconstructed_dir(self, value):
        """Base directory where reconstructed versions are to be stored.
        """
        value = self.normalize_dir_value(value=value)
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)
        return value

    # Versioned data dir
    @OptionsBase.property(action=_singleton_cli.WritableOrCreableDirAction,
                          default=default_base_dataset_dir)
    def base_version_dataset_dir(self, value):
        """Base dir for versioned folders.
        """
        value = self.normalize_dir_value(value=value)
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)
        return value

    # Temp dir
    for default_tmp_dir in ["/dev/shm", "/var/run", tempfile.gettempdir()]:
        try:
            _singleton_cli.WritableDirAction.assert_valid_value(default_tmp_dir)
            break
        except AssertionError:
            pass
    else:
        default_tmp_dir = os.path.expanduser("~/enb_tmp")

    @OptionsBase.property(action=_singleton_cli.WritableOrCreableDirAction,
                          default=default_tmp_dir)
    def base_tmp_dir(self, value):
        """Temporary dir used for intermediate data storage.

        This can be useful when experiments make heavy use of tmp and memory is limited,
        avoiding out-of-RAM crashes at the cost of potentially slower execution time.

        The dir is created when defined if necessary.
        """
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Base dir for external binaries (e.g., codecs or other tools)
    default_external_binary_dir = os.path.join(calling_script_dir, "bin")
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
    @OptionsBase.property(
        action=_singleton_cli.WritableOrCreableDirAction,
        default=default_output_plots_dir)
    def plot_dir(self, value):
        """Directory to store produced plots.
        """
        value = self.normalize_dir_value(value=value)
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)
        return value

    # Output analysis dir
    @OptionsBase.property(action=_singleton_cli.WritableOrCreableDirAction, default=default_analysis_dir)
    def analysis_dir(self, value):
        """Directory to store analysis results.
        """
        value = self.normalize_dir_value(value=value)
        _singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)
        return value


@_singleton_cli.property_class(OptionsBase)
class RayOptions:
    """Options related to the ray library, used for parallel/distributed computing
    only when --ssh_cluster_csv_path (or, equivalently --ssh_csv) are employed.
    """

    @OptionsBase.property("ssh_csv", type=str, default=None)
    def ssh_cluster_csv_path(self, value):
        """Path to the CSV file containing a enb ssh cluster configuration.
        See https://miguelinux314.github.io/experiment-notebook/installation.html.
        """
        if not os.path.exists(value):
            print(f"Selected ssh_cluster_csv_path={repr(value)}, but it is not a valid file. "
                  f"Setting to None instead.")
            value = None
        return value

    @OptionsBase.property(action="store_true")
    def disable_swap(self, value):
        """If this flag is used, then swap memory will not be allowed by ray. By default, swap memory is enabled.
        Note that your system may become unstable if swap memory is used (specially a big portion thereof).
        """
        return bool(value)

    @OptionsBase.property(type=str)
    def worker_script_name(self, value):
        """Base name of ray's worker scripts, invoked to run tasks in parallel processes.
        You don't need to change this unless you want to use custom ray workers.
        """
        if value != os.path.basename(value):
            raise SyntaxError("The worker_script_name parameter must be a base name, i.e., a file name "
                              f"including any extension, and without any path indication. Found {value} instead")
        return str(value)

    @OptionsBase.property(type=str)
    def preshutdown_wait_seconds(self, value):
        """A wait period can be held before shutting down ray. This allows displaying messages produced by
        child processes (e.g., stack traces) in case of abrupt termination of enb client code.
        """
        return float(value) if float(value) <= 0 else 0

    @OptionsBase.property(action=_singleton_cli.PositiveIntegerAction)
    def ray_port(self, value):
        """Ray port and first port that need to be open in case a cluster
        is to be set up. Refer to https://miguelinux314.github.io/experiment-notebook/installation.html
        for further information on this.
        """
        _singleton_cli.PositiveIntegerAction.assert_valid_value(value)
        return int(value)

    @OptionsBase.property(action=_singleton_cli.PositiveIntegerAction)
    def ray_port_count(self, value):
        """Total number of consecutive ports that can be assumed to be open after `ray_port`.
        For instance, if `ray_port` is 11000 and `ray_port_count` is 1000, then
        ports 11000-11999 will be used for parallelization and (if so-configured) enb clusters.
        """
        _singleton_cli.PositiveIntegerAction.assert_valid_value(value)
        return int(value)

    @OptionsBase.property(action="store_true")
    def no_remote_mount_needed(self, value):
        """If this flag is used, the calling script's project root path is assumed to
        be valid AND synchronized (e.g., via NFS). By default, remote mounting via sshfs and vde2 is employed.
        """
        return bool(value)


@_singleton_cli.property_class(OptionsBase)
class LoggingOptions(OptionsBase):
    """Options controlling what and how is printed and/or logged to files.
    """

    @OptionsBase.property(type=str, choices=_logging_level_names)
    def selected_log_level(self, value):
        """Maximum log level / minimum priority required when printing messages.
        """
        return str(value)

    @OptionsBase.property(type=str, choices=_logging_level_names)
    def default_print_level(self, value):
        """Selects the default log level equivalent to a regular print-like message. It is most effective
        when combined with log_print set to True.
        """
        return str(value)

    @OptionsBase.property(type=bool, choices=[True, False])
    def log_level_prefix(self, value):
        """If True, logged messages include a prefix, e.g., based on their priority.
        """
        from .. import log

        log.logger.show_prefixes = bool(value)
        return log.logger.show_prefixes

    @OptionsBase.property(type=str, choices=_logging_level_names)
    def show_prefix_level(self, value):
        from .. import log

        log.logger.show_prefix_level = log.logger.get_level(value)


class Options(GeneralOptions, ExecutionOptions, DirOptions, RayOptions, LoggingOptions):
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


@deprecation.deprecated(deprecated_in="0.2.7", removed_in="0.3.1")
def get_options(from_main=False):
    """Deprecated - use `from enb.config import options`.
    """
    return Options()


def set_options(new_option_dict):
    """Update global options with a dictionary of values
    """
    if Options() is not new_option_dict:
        for k, v in new_option_dict.__dict__.items():
            Options().__setattr__(k, v)


def propagates_options(f):
    """Decorator for local (as opposed to ray.remote) functions so that they
    propagate options properly to child workers.
    The decorated function must accept an "options" argument.
    Furthermore, the current working dir is set to the project root so that
    any relative paths stored are correctly handled.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        os.chdir(kwargs["options"].project_root)
        set_options(kwargs["options"])
        return f(*args, **kwargs)

    return wrapper
