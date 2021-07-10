#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuration in enb is centralized through this module with two key aspects:

    - `enb.config.options` is a singleton, dict-like object that
       enables automatic access and change propagation across all enb modules and host enb code,
       i.e., your experiments.
       The following line is typically used, `from enb.config import options`, to
       have a convenient `options` dict-like global.

    - command-line interface (CLI) parsers are automatically created so that options can be set to values
      different than the defaults by passing `-*` and `--*` arguments to the invocation of enb or any
      enb host code. Run any script or enb with the '-h' flag and see all available options.

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


class GlobalOptions(enb.singleton_cli.SingletonCLI):
    """Global options available to all modules.

    New options can be added to this by decorating any function with `@GlobalOptions.property`.
    """
    pass


class GeneralGroup:
    @GlobalOptions.property("v", action="count", default=0)
    def verbose(self, value):
        """Be verbose? Repeat for more.
        """
        pass


class ExecutionOptions:
    @GlobalOptions.property("cpu_limit", "cpu_cunt",
                            group_name="Execution Options",
                            group_description="General execution options.",
                            type=int, default=None)
    def ray_cpu_limit(self, value):
        """Maximum number of virtual CPUs to use in the ray cluster.
        """
        return int(value)

    @GlobalOptions.property("s", "not_parallel",
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

    @GlobalOptions.property("f", "overwrite", action="count", default=0)
    def force(self, value):
        """Force calculation of pre-existing results, if available?

        Note that should an error occur while re-computing a given index,
        that index is dropped from the persistent support.
        """
        return int(value)

    @GlobalOptions.property("q", "fast", action="count", default=0)
    def quick(self, value):
        """Perform a quick test with a subset of the input samples?

        If specified q>0 times, a subset of the first q target indices is employed
        in most get_df methods from ATable instances
        """
        return int(value)

    @GlobalOptions.property("rep", "repetition_count", action=singleton_cli.PositiveIntegerAction, default=1, type=int)
    def repetitions(self, value):
        """Number of repetitions when calculating execution times.

        This value allows computation of more reliable execution times in some experiments, but
        is normally most representative in combination with -s to use a single execution process at a time.
        """
        singleton_cli.PositiveIntegerAction.assert_valid_value(value)

    @GlobalOptions.property("c", "selected_columns", default=None, nargs="+", type=str)
    def columns(self, value):
        """List of selected column names for computation.

        If one or more column names are provided,
        all others are ignored. Multiple columns can be expressed,
        separated by spaces.
        Don't use this argument unless you know what you are doing, or expect potential exceptions.
        """
        assert value, f"At least one column must be defined"

    @GlobalOptions.property(action="store_true", default=True)
    def exit_on_error(self, value):
        """If True, any exception when processing rows aborts the program.
        """
        return bool(value)

    @GlobalOptions.property(action="store_true", default=False)
    def discard_partial_results(self, value):
        """Discard partial results when an error is found running the experiment?

        Otherwise, they are output to persistent storage.
        """
        return bool(value)

    @cli_property("no_new_data", "render_only", action="store_true", default=False)
    def no_new_results(self, value):
        """If True, no new data is computed in the get_df method of most ATable subclasses.

        This can be useful to speed up the rendering process, for instance to try different
        aesthetic plotting options.
        """
        return bool(value)

    @GlobalOptions.property("cs", default=None, type=int)
    def chunk_size(self, value):
        """Chunk size used when running ATable's get_df().
        Each processed chunk is made persistent before processing the next one.
        This parameter can be used to control the trade-off between error tolerance and overall speed.
        """
        pass


class RenderingOptions:
    """Options affecting the rendering of figures.
    """

    @GlobalOptions.property("nr", "norender",
                            group_name="Rendering Options",
                            group_description="Options affecting the rendering of figures.",
                            action="store_true", default=False)
    def no_render(self, value):
        """If set, some rendering options will be skipped.
        """
        return bool(value)

    @GlobalOptions.property("fw", "width",
                            default=5, type=float, action=singleton_cli.PositiveFloatAction)
    def fig_width(self, value):
        """Figure width.

        Larger values may make text look smaller when the image is scaled to a constant size.
        """
        singleton_cli.PositiveFloatAction.assert_valid_value(value)

    @GlobalOptions.property("fh", "height",
                            default=4, type=float, action=singleton_cli.PositiveFloatAction)
    def fig_height(self, value):
        """Figure height.

        Larger values may make text look smaller when the image is scaled to a constant size.
        """
        singleton_cli.PositiveFloatAction.assert_valid_value(value)

    @GlobalOptions.property("ylpos", default=-0.01, type=float)
    def global_y_label_pos(self, value):
        """Relative position of the global Y label.

        Can be negative or positive. Intended as a quick hack when left y-axis ticks are longer or shorter
        than the default assumptions.
        """
        return float(value)

    @GlobalOptions.property("legend_count", default=2, type=int, action=singleton_cli.PositiveIntegerAction)
    def legend_column_count(self, value):
        """Number of columns used in plot legends.
        """
        singleton_cli.PositiveIntegerAction.assert_valid_value(value)

    @GlobalOptions.property(action="store_true")
    def show_grid(self, value):
        """Show axis grid lines?
        """
        return bool(value)

    @GlobalOptions.property("title", "global_title", type=str, default=None)
    def displayed_title(self, value):
        """When this property is not None, displayed plots will typically include its value as the main title.
        """
        return str(value)


class DirOptions:
    """Options regarding default data directories.
    """
    # Data dir
    default_base_dataset_dir = os.path.join(calling_script_dir, "datasets")

    @GlobalOptions.property("d",
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

    @GlobalOptions.property("persistence", default=default_persistence_dir, action=singleton_cli.WritableOrCreableDirAction)
    def persistence_dir(self, value):
        """Directory where persistence files are to be stored.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Reconstructed version dir
    @GlobalOptions.property("reconstructed", default=None, action=singleton_cli.WritableOrCreableDirAction)
    def reconstructed_dir(self, value):
        """Base directory where reconstructed versions are to be stored.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)

    # Versioned data dir
    @GlobalOptions.property("vd", "version_target_dir", action=singleton_cli.WritableOrCreableDirAction, default=None)
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

    @GlobalOptions.property("t", "tmp", "tmp_dir",
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

    @GlobalOptions.property(action=singleton_cli.ReadableDirAction, default=default_external_binary_dir,
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

    @GlobalOptions.property(
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

    @GlobalOptions.property("analysis",
                            action=singleton_cli.WritableOrCreableDirAction, default=default_analysis_dir)
    def analysis_dir(self, value):
        """Directory to store analysis results.
        """
        singleton_cli.WritableOrCreableDirAction.assert_valid_value(value)


# class TemplateOptions(singleton_cli.GlobalOptions):
#     @cli_parsers_builder(""
#         , title="Subcommands"
#         , description="Allows you to either create or modify a template at will."
#         , new_parser=True
#         , parser_alias="template")
#     def template_parser(self, value):
#         pass
#
#     @cli_parsers_builder("n",
#                          group_name="General Options"
#         , parser_parent="template"
#         , action=singleton_cli.ValidationTemplateNameAction
#         , help="Followed by a string defines the name of a template"
#                + " to either be added, modified or deleted."
#         , required=False)
#     def template_name(self, value):
#         pass
#
#     """
#     @cli_parsers_builder("template_name",
#                          parser_parent="template"
#         , positional=True
#         , group_name="General Options"
#         , type=str
#         , help="This should also work.")
#     def template_name(self, value):
#         pass
#     """
#
#     @cli_parsers_builder("c",
#                          group_name="General Options"
#         , parser_parent="template"
#         , default=False
#         , action="store_true"
#         , help="To create a new template.")
#     def create_new_template(self, value):
#         pass
#
#     @cli_parsers_builder("l",
#                          group_name="General Options"
#         , parser_parent="template"
#         , default=False
#         , action="store_true"
#         , help="To list all the actions one can do over a template.")
#     def list_template_options(self, value):
#         pass
#
#     @cli_parsers_builder(""
#         , title="Subcommands"
#         , description="Allows you to add either en Experiment, an"
#                       + " Analysis or a step."
#         , new_parser=True
#         , parser_parent="template"
#         , parser_alias="add")
#     def add_parser(self, value):
#         pass
#
#     @cli_parsers_builder("w",
#                          group_name="General Options"
#         , parser_parent="template"
#         , default="./"
#         , type=str
#         , help="Controller that allows you to define the operation to"
#                + " be exacted over a template."
#         , action=singleton_cli.WritableDirAction
#         , required=False)
#     def working_dir(self, value):
#         pass
#
#     @cli_parsers_builder("l",
#                          group_name="General Options"
#         , parser_parent="add"
#         , help="To list adding options."
#         , default=False
#         , action="store_true")
#     def list_adding_options(self, value):
#         pass
#
#     @cli_parsers_builder("",
#                          group_name="General Options"
#         , new_parser=True
#         , parser_parent="add"
#         , parser_alias="experiment")
#     def experiment_parser(self, value):
#         pass
#
#     @cli_parsers_builder("l",
#                          group_name="General Options"
#         , parser_parent="experiment"
#         , help="To list all existing possible experiments."
#         , default=False
#         , action="store_true")
#     def list_experiments(self, value):
#         pass
#
#     @cli_parsers_builder("e",
#                          group_name="General Options"
#         , parser_parent="experiment"
#         , help="To define the experiment type we would like to add."
#         , type=str
#         , required=False)
#     def experiment_type(self, value):
#         pass
#
#     @cli_parsers_builder("",
#                          group_name="General Options"
#         , new_parser=True
#         , parser_parent="add"
#         , parser_alias="analysis")
#     def analysis_parser(self, value):
#         pass
#
#     @cli_parsers_builder("l",
#                          group_name="General Options"
#         , parser_parent="analysis"
#         , help="To list all existing possible analysis."
#         , default=False
#         , action="store_true")
#     def list_analysis(self, value):
#         pass
#
#     @cli_parsers_builder("a",
#                          group_name="General Options"
#         , parser_parent="analysis"
#         , help="To define the analysis to add."
#         , type=str
#         , required=False)
#     def analysis_type(self, value):
#         pass
#
#     @cli_parsers_builder("",
#                          group_name="General Options"
#         , new_parser=True
#         , parser_parent="add"
#         , parser_alias="step")
#     def step_parser(self, value):
#         pass
#
#

@deprecation.deprecated(deprecated_in="0.2.7", removed_in="0.3.1")
def get_options(from_main=False):
    """Deprecated - use enb.config.options instead.
    """
    global options
    return options


@deprecation.deprecated(deprecated_in="0.2.7", removed_in="0.3.1")
def set_options(new_options):
    """Deprecated - use enb.config.options instead.
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


# Modules should use config.options
options = GlobalOptions()

# Verify singleton instance
assert options is GlobalOptions(), f"The singleton property does not seem to be working ?!"
