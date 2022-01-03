#!/usr/bin/env python3
"""Automatic analysis and report of pandas :class:`pandas.DataFrames`
(e.g., produced by :class:`enb.experiment.Experiment` instances)
using pyplot.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/01/01"

import ast
import functools
import os
import math
import collections
import collections.abc
import tempfile
import numbers
import pdf2image
import numpy as np
import scipy.stats

import enb.atable
from enb.atable import clean_column_name
from enb import plotdata
from enb.config import options
from enb.experiment import TaskFamily


@enb.config.aini.managed_attributes
class Analyzer(enb.atable.ATable):
    """Base class for all enb analyzers.

    A |DataFrame| instance with analysis results can be obtained by calling get_df.
    In addition, if render_plots is used in that function, one or more figures will be
    produced. What plots are generated (if any) is based on the values of
    the self.selected_render_modes list, which must contain only elements in self.valid_render_modes.

    Data analysis is done through a surrogate :class:`enb.aanalysis.AnalyzerSummary` subclass,
    which is used to obtain the returned analysis results. Subclasses of :class:`enb.aanalysis.Analyzer`
    then perform any requested plotting.

    Rendering is performed for all modes contained self.selected_render_modes, which
    must be in self.valid_render_modes.

    The `@enb.config.aini.managed_attributes` decorator overwrites the class ("static") properties
    upon definition, with values taken from .ini configuration files. The decorator can be added
    to any Analyzer subclass, and parameters can be managed within the full-qualified name of the class,
    e.g., using a "[enb.aanalysis.Analyzer]" section header in any of the .ini files detected by enb.
    """
    # List of allowed rendering modes for the analyzer
    valid_render_modes = set()
    # Selected render modes (by default, all of them)
    selected_render_modes = set(valid_render_modes)
    # Main title to be displayed
    plot_title = None
    # Show the number of elements in each group?
    show_count = True
    # Show a group containing all elements?
    show_global = False
    # If a reference group is used as baseline, should it be shown in the analysis itself?
    show_reference_group = False
    # Main marker size
    main_marker_size = 4
    # Secondary (e.g., individual data) marker size
    secondary_marker_size = 2
    # Main plot element alpha
    main_alpha = 0.5
    # Secondary plot element alpha (often overlaps with data using main_alpha)
    secondary_alpha = 0.5
    # If a semilog y axis is used, y_min will be at least this large to avoid math domain errors
    semilog_y_min_bound = 1e-5
    # Thickness of the main plot lines
    main_line_width = 2
    # Thickness of secondary plot lines
    secondary_line_width = 1
    # Margin between group rows (if there is more than one)
    group_row_margin = 0.2
    # If more than group is displayed, when applicable, adjust plots to use the same scale in every subplot?
    common_group_scale = True
    # If applicable, show a horizontal +/- 1 standard deviation bar centered on the average
    show_x_std = False
    # If applicable, show a vertical +/- 1 standard deviation bar centered on the average
    show_y_std = False
    # If more than one group is present, they are shown in the same subplot
    # instead of in different rows
    combine_groups = False
    # If True, display group legends when applicable
    show_legend = True

    def __init__(self, csv_support_path=None, column_to_properties=None, progress_report_period=None):
        super().__init__(csv_support_path=csv_support_path,
                         column_to_properties=column_to_properties,
                         progress_report_period=progress_report_period)
        self.valid_render_modes = set(self.valid_render_modes)
        self.selected_render_modes = set(self.selected_render_modes)
        for mode in self.selected_render_modes:
            if mode not in self.valid_render_modes:
                raise SyntaxError(f"Selected mode {repr(mode)} not in the "
                                  f"list of available modes ({repr(self.valid_render_modes)}")

    def get_df(self, full_df, target_columns,
               selected_render_modes=None,
               output_plot_dir=None, group_by=None, reference_group=None, column_to_properties=None,
               show_global=None, show_count=True, **render_kwargs):
        """
        Analyze a :class:`pandas.DataFrame` instance, optionally producing plots, and returning the computed
        dataframe with the analysis results.

        Rendering is performed for all modes contained self.selected_render_modes, which
        must be in self.valid_render_modes.

        You can use the @enb.aanalysis.Analyzer.normalize_parameters decorator when overwriting this method,
        to automatically transform None values into their defaults.

        :param full_df: full DataFrame instance with data to be plotted and/or analyzed.
        :param target_columns: columns to be analyzed. Typically, a list of column names, although
          each subclass may redefine the accepted format (e.g., pairs of column names). If None,
          all scalar, non string columns are used.
        :param selected_render_modes: a potentially empty list of mode names, all of which
          must be in self.valid_render_modes. Each mode represents a type of analysis or plotting.
        :param group_by: if not None, the name of the column to be used for grouping.
        :param reference_group: if not None, the reference group name against which data are to be analyzed.
        :param output_plot_dir: path of the directory where the plot/plots is/are to be saved.
          If None, the default output plots path given by `enb.config.options` is used.
        :param column_to_properties: dictionary with ColumnProperties entries. ATable instances provide it
          in the :attr:`column_to_properties` attribute, :class:`Experiment` instances can also use the
          :attr:`joined_column_to_properties` attribute to obtain both the dataset and experiment's
          columns.
        :param show_global: if True, a group containing all elements is also included in the analysis

        :return: a |DataFrame| instance with analysis results
        """
        if self.csv_support_path is not None and os.path.exists(self.csv_support_path):
            # Analyzer classes store their persistence, but they erase when get_df is called,
            # so that analysis is always performed (which is as expected, since the experiment
            # results being analyzed cannot be assumed to be the same as the previous invocation
            # of this analyzer's get_df method).
            os.remove(self.csv_support_path)
            enb.logger.info(f"Removed {self.csv_support_path} to allow analysis with {self.__class__.__name__}.")

        srm = selected_render_modes

        def normalized_wrapper(self, full_df, target_columns, output_plot_dir,
                               selected_render_modes, group_by, reference_group,
                               column_to_properties,
                               **render_kwargs):
            # Get the summary table with the requested data analysis
            summary_table = self.build_summary_atable(
                full_df=full_df,
                target_columns=target_columns,
                group_by=group_by,
                reference_group=reference_group,
                include_all_group=show_global)

            old_nnr = options.no_new_results
            try:
                options.no_new_results = False
                summary_df = summary_table.get_df()
            finally:
                options.no_new_results = old_nnr

            selected_render_modes = selected_render_modes if srm is None else srm

            # Render all applicable modes
            self.render_all_modes(
                summary_df=summary_df,
                target_columns=target_columns,
                output_plot_dir=output_plot_dir,
                reference_group=reference_group,
                group_by=group_by,
                column_to_properties=column_to_properties,
                selected_render_modes=selected_render_modes,
                **render_kwargs)

            # Return the summary result dataframe
            return summary_df

        normalized_wrapper = self.__class__.normalize_parameters(
            f=normalized_wrapper,
            group_by=group_by,
            column_to_properties=column_to_properties,
            target_columns=target_columns,
            reference_group=reference_group,
            output_plot_dir=output_plot_dir,
            selected_render_modes=selected_render_modes)

        return normalized_wrapper(self=self, full_df=full_df, **render_kwargs)

    def render_all_modes(self,
                         # Dynamic arguments with every call
                         summary_df, target_columns, output_plot_dir,
                         reference_group,
                         group_by, column_to_properties,
                         # Arguments normalized by the @enb.aanalysis.AAnalyzer.normalize_parameters,
                         # in turn manageable through .ini configuration files via the
                         # @enb.config.aini.managed_attributes decorator.
                         selected_render_modes, show_global, show_count,
                         # Rendering options, directly passed to plotdata.render_plds_by_group
                         **render_kwargs):
        """Render all target modes and columns into output_plot_dir, with file names based
        on self's class name, the target column and the target render mode.

        Subclasses may overwrite their update_render_kwargs_one_case method to customize the rendering
        parameters that are passed to the parallel rendering function from enb.plotdata.
        These overwriting methods are encouraged to call enb.aanalysis.Analyzer.update_render_kwargs_one_case
        (directly or indirectly) so make sure all necessary parameters reach the rendering function.
        """
        # If plot rendering is requested, do so for all selected modes, in parallel
        render_ids = []
        for render_mode in selected_render_modes:
            for column_selection in target_columns:
                # The update_render_kwargs_one_case call should set all rendering kwargs of interest.
                # A call to Analyzer's/super()'s update_render_kwargs_one_case is recommended
                # to guarantee consistency and minimize code duplicity.
                # Also note that column_selection may have different
                # types (e.g., strings for column names, or tuples of column names, etc).

                column_kwargs = self.update_render_kwargs_one_case(
                    column_selection=column_selection, render_mode=render_mode,
                    reference_group=reference_group,
                    summary_df=summary_df,
                    output_plot_dir=output_plot_dir, group_by=group_by, column_to_properties=column_to_properties,
                    show_global=show_global, show_count=show_count,
                    **(dict(render_kwargs) if render_kwargs is not None else dict()))

                if reference_group is not None:
                    if not self.show_reference_group:
                        # Remove the plottable data for the reference group if one is used
                        filtered_plds = {k: v for k, v in column_kwargs["pds_by_group_name"].items()
                                         if k != reference_group}
                        if len(column_kwargs["pds_by_group_name"]) <= len(filtered_plds):
                            raise ValueError(f"Invalid reference_group {repr(reference_group)} not found.")
                        column_kwargs["pds_by_group_name"] = filtered_plds

                # All arguments to the parallel rendering function are ready; their associated tasks as created
                render_ids.append(enb.plotdata.parallel_render_plds_by_group.start(
                    **column_kwargs))


        # Wait until all rendering tasks are done while updating about progress
        with enb.logger.verbose_context(f"Rendering {len(render_ids)} plots with {self.__class__.__name__}...\n"):
            for progress_report in enb.parallel.ProgressiveGetter(
                    id_list=render_ids,
                    iteration_period=self.progress_report_period):
                enb.logger.verbose(progress_report.report())


    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.AAnalyzer.normalize_parameters,
            # in turn manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to plotdata.render_plds_by_group
            **column_kwargs):
        """Update column_kwargs with the desired rendering arguments for this column
        and render mode. Return the updated dict.
        """
        if isinstance(column_selection, str):
            all_columns = [column_selection]
        elif isinstance(column_selection, collections.abc.Iterable):
            all_columns = []
            for c in column_selection:
                if isinstance(c, str):
                    all_columns.append(c)
                elif isinstance(c, collections.abc.Iterable):
                    all_columns.extend(c)

            if not all(isinstance(c, str) for c in all_columns):
                raise ValueError(f"Invalid column_selection={repr(column_selection)}. "
                                 f"Computed all_columns={repr(all_columns)}, which is not "
                                 f"a list of strings as expected.")

        # Get the output path. Plots are overwritten by default
        column_kwargs["output_plot_path"] = self.get_output_pdf_path(
            column_selection=column_selection,
            group_by=group_by, reference_group=reference_group,
            output_plot_dir=output_plot_dir,
            render_mode=render_mode)
        column_kwargs["pds_by_group_name"] = {
            group_label: group_plds for group_label, group_plds
            in sorted(summary_df[["group_label", f"{column_selection}_render-{render_mode}"]].values,
                      key=lambda t: t[0])}

        # General column properties
        if "column_properties" not in column_kwargs:
            try:
                column_kwargs["column_properties"] = column_to_properties[column_selection]
            except (KeyError, TypeError):
                column_kwargs["column_properties"] = enb.atable.ColumnProperties(name=column_selection)

        # Generate some labels
        if "y_labels_by_group_name" not in column_kwargs:
            column_kwargs["y_labels_by_group_name"] = {
                group: f"{group} ({count})" if show_count else f"{group}"
                for group, count in summary_df[["group_label", "group_size"]].values}
        if "plot_title" not in column_kwargs:
            column_kwargs["plot_title"] = self.plot_title

        # Control group division and labeling
        if "combine_groups" not in column_kwargs:
            column_kwargs["combine_groups"] = self.combine_groups
        if "show_legend" not in column_kwargs:
            column_kwargs["show_legend"] = self.show_legend

        return column_kwargs

    def get_output_pdf_path(self, column_selection, group_by, reference_group, output_plot_dir, render_mode):
        if isinstance(column_selection, str):
            column_selection_str = column_selection
        else:
            column_selection_str = "__vs__".join(column_selection)

        return os.path.join(
            output_plot_dir,
            f"{self.__class__.__name__}-"
            f"{column_selection_str}-{render_mode}" +
            (f"-groupby__{get_groupby_str(group_by=group_by)}" if group_by else "") +
            (f"-referencegroup__{reference_group}" if reference_group else "") +
            ".pdf")

    @classmethod
    def normalize_parameters(cls, f, group_by, column_to_properties, target_columns,
                             reference_group,
                             output_plot_dir, selected_render_modes):
        """Optional decorator methods compatible with the Analyzer.get_df signature, so that managed
        attributes are used when

        This way, users may overwrite most adjustable arguments programmatically,
        or via .ini configuration files.
        """
        column_to_properties = column_to_properties if column_to_properties is not None \
            else collections.OrderedDict()

        @functools.wraps(f)
        def wrapper(self,
                    # Dynamic arguments with every call (full_df and group_by are not normalized)
                    full_df, target_columns=target_columns, reference_group=reference_group,
                    output_plot_dir=output_plot_dir,
                    # Arguments normalized by the @enb.aanalysis.AAnalyzer.normalize_parameters,
                    # in turn manageable through .ini configuration files via the
                    # @enb.config.aini.managed_attributes decorator.
                    selected_render_modes=None, show_global=None, show_count=True, plot_title=None,
                    # Rendering options, directly passed to plotdata.render_plds_by_group
                    **render_kwargs):
            selected_render_modes = selected_render_modes if selected_render_modes is not None \
                else cls.selected_render_modes

            if target_columns is None:
                target_columns = [c for c in full_df.columns if isinstance(full_df.iloc[0][c], numbers.Number)]
                if not target_columns:
                    raise ValueError(f"Cannot find any numeric columns in {repr(full_df.columns)} "
                                     "and no specific column was chosen")
            elif isinstance(target_columns, str):
                target_columns = [target_columns]

            output_plot_dir = output_plot_dir if output_plot_dir is not None \
                else enb.config.options.plot_dir
            show_global = show_global if show_global is not None else cls.show_global
            show_count = show_count if show_count is not None else cls.show_count
            plot_title = plot_title if plot_title is not None else cls.plot_title

            for c in full_df.columns:
                if c not in column_to_properties:
                    column_to_properties[c] = enb.atable.ColumnProperties(clean_column_name(c))

            return f(self=self, full_df=full_df, reference_group=reference_group,
                     selected_render_modes=selected_render_modes,
                     target_columns=target_columns, output_plot_dir=output_plot_dir,
                     show_global=show_global, show_count=show_count,
                     group_by=group_by, column_to_properties=column_to_properties,
                     plot_title=plot_title, **render_kwargs)

        return wrapper

    @classmethod
    def adjust_common_row_axes(cls, column_kwargs, column_selection, render_mode, summary_df):
        """When self.common_group_scale is True, this method is called to make all groups (rows)
        use the same scale.
        """
        global_x_min = float("inf")
        global_x_max = float("-inf")
        global_y_min = float("inf")
        global_y_max = float("-inf")
        for pld_list in summary_df[f"{column_selection}_render-{render_mode}"]:
            # candidate_plds = (pld for pld in pld_list if isinstance()
            #                   any(isinstance(pld, cls) for cls in (enb.plotdata.LineData))
            # candidate_plds = (pld for pld in pld_list if isinstance(pld, plotdata.LineData))
            for pld in pld_list:
                try:
                    global_x_min = min(global_x_min, min(pld.x_values) if len(pld.x_values) > 0 else global_x_min)
                    global_x_max = max(global_x_max, max(pld.x_values) if len(pld.x_values) > 0 else global_x_max)
                except AttributeError:
                    assert not isinstance(pld, plotdata.PlottableData2D)
                try:
                    global_y_min = min(global_y_min, min(pld.y_values) if len(pld.y_values) > 0 else global_y_min)
                    global_y_max = max(global_y_max, max(pld.y_values) if len(pld.y_values) > 0 else global_y_max)
                except AttributeError:
                    assert not isinstance(pld, plotdata.PlottableData2D)
        if "y_min" not in column_kwargs:
            column_kwargs["y_min"] = global_y_min
        if "y_max" not in column_kwargs:
            column_kwargs["y_max"] = global_y_max

    def build_summary_atable(self, full_df, target_columns, reference_group, group_by, include_all_group):
        """
        Build a :class:`enb.aanalysis.AnalyzerSummary` instance with the appropriate
        columns to perform the intended analysis. See :class:`enb.aanalysis.AnalyzerSummary`
        for documentation on the meaning of each argument.

        :param full_df: dataframe instance being analyzed
        :param target_columns: list of columns specified for analysis
        :param reference_group: if not None, the column or group to be used as baseline in the analysis
        :param include_all_group: force inclusion of an "All" group with all samples

        :return: the built summary table, without having called its get_df method.
        """
        raise SyntaxError(
            f"Subclasses must implement this method. {self.__class__} did not. "
            f"Typically, the associated AnalyzerSummary needs to be instantiated and returned. "
            f"See enb.aanalysis.Analyzer's documentation.")

    def get_render_column_name(self, column_selection, selected_render_mode):
        """Return the canonical name for columns containing plottable data instances.
        """
        return f"{column_selection}_render-{selected_render_mode}"


class AnalyzerSummary(enb.atable.SummaryTable):
    """Base class for the surrogate, dynamic summary tables employed by :class:`enb.aanalysis.Analyzer`
    subclasses to gather analysis results and plottable data (when configured to do so).
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group, group_by, include_all_group):
        """Dynamically generate the needed analysis columns and any other needed attributes
        for the analysis.

        Columns that generate plottable data are automatically defined defined using self.render_target,
        based on the analyzer's selected render modes.

        Plot rendering columns are added automatically via this call, with
        associated function self.render_target with partialed parameters
        column_selection and render_mode.

        Subclasses are encouraged to call `self.move_render_columns_back()` to make sure rendering columns
        are processed after any other intermediate column defined by the subclass.

        :param analyzer: :class:`enb.aanalysis.Analyzer` subclass instance corresponding to this summary table.
        :param full_df: full dataframe specified for analysis.
        :param target_columns: columns for which an analysis is being requested.
        :param reference_group: if not None, it must be the name of one group, which is used as baseline.
          Different subclasses may implement this in different ways.
        :param group_by: grouping configuration for this summary. See the specific subclass help for more inforamtion.
        :param include_all_group: if True, an "All" group with all input samples is included in the analysis.
        """
        # Note that csv_support_path is set to None to force computation of the analysis
        # every call, instead of relying on persistence (it would make no sense to load
        # the summary for a different input dataset).
        super().__init__(full_df=full_df, column_to_properties=analyzer.column_to_properties,
                         copy_df=False, csv_support_path=analyzer.csv_support_path,
                         group_by=group_by,
                         include_all_group=(include_all_group if include_all_group is not None
                                            else analyzer.show_global))
        self.analyzer = analyzer
        self.reference_group = reference_group
        self.group_by = group_by
        self.include_all_group = include_all_group
        self.target_columns = target_columns

        # Add columns that compute the list of plotting elements of each group, if needed
        for selected_render_mode in self.analyzer.selected_render_modes:
            for column_selection in target_columns:
                self.add_column_function(
                    self,
                    fun=functools.partial(
                        self.compute_plottable_data_one_case,
                        column_selection=column_selection,
                        render_mode=selected_render_mode,
                        reference_group=reference_group),
                    column_properties=enb.atable.ColumnProperties(
                        name=self.analyzer.get_render_column_name(column_selection, selected_render_mode),
                        has_object_values=True))

        self.apply_reference_bias()

    def split_groups(self, reference_df=None, include_all_group=None):
        try:
            original_group_by = self.group_by
            self.group_by = self.group_by if not is_family_grouping(self.group_by) else "family_label"
            return super().split_groups(reference_df=reference_df, include_all_group=include_all_group)
        finally:
            self.group_by = original_group_by

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function (after "partialing"-out "column_selection" and "render_mode"),
        that computes the list of enb.plotdata.PlottableData instances that represent
        one group, one target column and one render mode.

        Subclasses must implement this method.

        :param args: render configuration arguments is expected to contain values for the signature
          (self, group_label, row)
        :param kwargs: dict with at least the "column_selection" and "render_mode" parameters.
        """
        # The following snippet can be used in overwriting implementations of render_target.
        _self, group_label, row = args
        # group_df = self.label_to_df[group_label]
        column_selection = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        reference_group = kwargs["reference_group"]
        if render_mode not in self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        raise SyntaxError(f"Subclasses must implement this method, which should set row[_column_name] "
                          f"to a list of enb.plotdata.PlottableData instances. "
                          f"{self.__class__.__name__} did not "
                          f"(group_label={group_label}, "
                          f"column_selection={repr(column_selection)}, "
                          f"render_mode={repr(render_mode)}).")

    def move_render_columns_back(self):
        """Reorder the column definitions so that rendering columns are attempted after
        any column the subclass may have defined.
        """
        column_to_properties = collections.OrderedDict()
        for k, v in ((k, v) for k, v in self.column_to_properties.items() if f"_render-" not in k):
            column_to_properties[k] = v
        for k, v in ((k, v) for k, v in self.column_to_properties.items() if f"_render-" in k):
            column_to_properties[k] = v
        self.column_to_properties = column_to_properties

    def apply_reference_bias(self):
        """By default, no action is performed relative to the presence of a reference group,
        and not bias is introduced in the dataframe. Subclasses may overwrite this.
        """
        if self.reference_group:
            enb.logger.warning(f"A reference group {repr(self.reference_group)} is selected "
                               f"but {self.__class__} does not implement its apply_reference_bias method.")
        return


def is_family_grouping(group_by):
    """Return True if and only if group_by is an iterable of one or more enb.experiment.TaskFamily instances.
    """
    try:
        return all(isinstance(e, TaskFamily) for e in group_by)
    except TypeError:
        return False


def get_groupby_str(group_by):
    """Return a string identifying the group_by method.
    If None, 'None' is returned.
    If a string is passed, it is returned.
    If a list of strings is passed, it is formatted adding two underscores as separation.
    If grouping by family was requested, 'family_label' is returned.
    """
    if not group_by:
        return "None"
    elif is_family_grouping(group_by=group_by):
        return "family_label"
    elif isinstance(group_by, str):
        return group_by
    elif isinstance(group_by, collections.abc.Iterable) and all(isinstance(s, str) for s in group_by):
        return "__".join(group_by)
    else:
        raise ValueError(group_by)


@enb.config.aini.managed_attributes
class ScalarNumericAnalyzer(Analyzer):
    """Analyzer subclass for scalar columns with numeric values.
    """
    # The following attributes are directly used for analysis/plotting,
    # and can be modified before any call to get_df. These values may be updated based on .ini files,
    # see the documentation of the enb.config.aini.managed_attributes decorator for more information.
    # Common analyzer attributes:
    valid_render_modes = {"histogram"}
    selected_render_modes = set(valid_render_modes)
    plot_title = None
    show_count = True
    show_global = True
    show_x_std = True
    show_y_std = False
    main_marker_size = None
    secondary_marker_size = None
    main_alpha = 0.5
    secondary_alpha = 0.5
    semilog_y_min_bound = 1e-5
    main_line_width = 2
    secondary_line_width = 2
    group_row_margin = 0.2
    common_group_scale = True
    combine_groups = False
    show_legend = False

    # Specific analyzer attributes:
    # Number of vertical bars in the displayed histograms.
    histogram_bin_count = 50
    # Fraction between 0 and 1 of the bar width for histogram.
    # Adjust for thinner or thicker vertical bars. Set to 0 to disable.
    bar_width_fraction = 1
    # If True, groups are sorted based on the average value of the column of interest.
    sort_by_average = False

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.AAnalyzer.normalize_parameters,
            # in turn manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to plotdata.render_plds_by_group
            **column_kwargs):
        """Update column_kwargs with the desired rendering arguments for this column
        and render mode. Return the updated dict.
        """
        # Update common rendering kwargs
        column_kwargs = super().update_render_kwargs_one_case(
            column_selection=column_selection, reference_group=reference_group,
            render_mode=render_mode,
            summary_df=summary_df, output_plot_dir=output_plot_dir,
            group_by=group_by, column_to_properties=column_to_properties,
            show_global=show_global, show_count=show_count,
            **column_kwargs)

        # Update specific rendering kwargs for this analyzer:
        if "global_x_label" not in column_kwargs:
            if self.main_alpha <= 0 or self.bar_width_fraction <= 0:
                column_kwargs["global_x_label"] = f"Average {column_to_properties[column_selection].label}"
            else:
                column_kwargs["global_x_label"] = column_to_properties[column_selection].label

            if reference_group is not None:
                column_kwargs["global_x_label"] += f" difference vs. {reference_group} average"

        if "global_y_label" not in column_kwargs:
            if self.main_alpha > 0 and self.bar_width_fraction > 0:
                column_kwargs["global_y_label"] = f"Histogram"
                if self.secondary_alpha != 0:
                    column_kwargs["global_y_label"] += ", average" if self.show_x_std else " and average"
            elif self.secondary_alpha != 0:
                column_kwargs["global_y_label"] = f"Average"
            else:
                enb.logger.warn(f"Plotting with {self.__class__.__name__} "
                                "and both bar_alpha and secondary_alpha "
                                "set to zero. Expect an empty-looking plot.")
            if self.show_x_std:
                column_kwargs["global_y_label"] += " and $\pm 1\sigma$"

            if self.main_alpha <= 0 or self.bar_width_fraction <= 0:
                column_kwargs["global_y_label"] = ""

        if self.main_alpha <= 0 or self.bar_width_fraction <= 0:
            column_kwargs["y_tick_list"] = []
            column_kwargs["y_tick_label_list"] = []

        # Calculate axis limits
        if "x_min" not in column_kwargs:
            column_kwargs["x_min"] = float(summary_df[f"{column_selection}_min"].min()) \
                if column_to_properties[column_selection].plot_min is None else \
                column_to_properties[column_selection].plot_min
        if "x_max" not in column_kwargs:
            column_kwargs["x_max"] = float(summary_df[f"{column_selection}_max"].max()) \
                if column_to_properties[column_selection].plot_max is None else \
                column_to_properties[column_selection].plot_max

        # Adjust a common scale for all subplots
        if self.common_group_scale and ("y_min" not in column_kwargs or "y_max" not in column_kwargs):
            with enb.logger.debug_context(f"Adjusting common group scale for {repr(column_selection)}"):
                self.adjust_common_row_axes(column_kwargs=column_kwargs,
                                            column_selection=column_selection,
                                            render_mode=render_mode,
                                            summary_df=summary_df)

        # Obtain the group averages for sorting and displaying purposes
        plds_by_group = summary_df[
            self.get_render_column_name(column_selection=column_selection, selected_render_mode=render_mode)]
        group_avg_tuples = [(group, [p.x_values[0] for p in plds if isinstance(p, enb.plotdata.ScatterData)][0])
                            for group, plds in plds_by_group.items()]

        if self.sort_by_average:
            column_kwargs["group_name_order"] = []
            for t in sorted(group_avg_tuples, key=lambda t: t[1]):
                group_name = t[0]
                try:
                    group_name = ast.literal_eval(group_name)
                except ValueError:
                    pass
                try:
                    if not isinstance(group_name, str) and len(group_name) == 1:
                        group_name = group_name[0]
                except TypeError:
                    pass

                column_kwargs["group_name_order"].append(group_name)

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, reference_group, group_by, include_all_group):
        """Dynamically build a SummaryTable instance for scalar value analysis.
        """
        return ScalarNumericSummary(analyzer=self, full_df=full_df, target_columns=target_columns,
                                    reference_group=reference_group,
                                    group_by=group_by, include_all_group=include_all_group)


class ScalarNumericSummary(AnalyzerSummary):
    """Summary table used in ScalarValueAnalyzer, defined dynamically with each call to maintain
    independent column definitions.

    Note that dynamically in this context implies that modifying the returned instance's class columns does
    not affect the definition of other instances of this class.

    Note that in most cases, the columns returned by default should suffice.

    If a reference_group is provided, its average is computed and subtracted from all values when
    generating the plot.
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group, group_by, include_all_group):
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_selection and render_mode.
        AnalyzerSummary.__init__(
            self=self,
            analyzer=analyzer, full_df=full_df, target_columns=target_columns,
            reference_group=reference_group, group_by=group_by, include_all_group=include_all_group)
        self.column_to_xmin_xmax = {}

        for column_name in target_columns:
            if column_name not in full_df.columns:
                raise ValueError(f"Invalid column name selection {repr(column_name)}. "
                                 f"Full selection: {repr(target_columns)}")

            # Add columns that compute the summary information
            self.add_scalar_description_columns(column_name=column_name)

            # Compute the global dynamic range of all input samples (before grouping)
            finite_series = full_df[column_name].replace([np.inf, -np.inf], np.nan, inplace=False).dropna()
            if len(finite_series) > 1:
                try:
                    self.column_to_xmin_xmax[column_name] = scipy.stats.describe(finite_series.values).minmax
                except FloatingPointError as ex:
                    raise FloatingPointError(f"Invalid finite_series.values={finite_series.values}") from ex
            elif len(finite_series) == 1:
                self.column_to_xmin_xmax[column_name] = [finite_series.values[0], finite_series.values[0]]
            else:
                self.column_to_xmin_xmax[column_name] = [None, None]

        self.move_render_columns_back()

    def apply_reference_bias(self):
        """Compute the average value of the reference group for each target column and
        subtract it from the dataframe being analyzed. If not reference group is present, 
        no action is performed.
        """
        if self.reference_group is not None:
            if self.group_by is None:
                raise ValueError(f"Cannot use a not-None reference_group if group_by is None "
                                 f"(here is {repr(self.reference_group)})")

            for group_label, group_df in self.split_groups():
                if group_label == self.reference_group:
                    self.reference_avg_by_column = {
                        c: group_df[group_df[c].notna()][c].mean()
                        for c in self.target_columns
                    }

                    self.reference_df = self.reference_df.copy()
                    for c, avg in self.reference_avg_by_column.items():
                        self.reference_df[c] -= avg
                    break
            else:
                found_groups_str = ','.join(repr(label) for label, _ in self.split_groups(
                    reference_df=self.reference_df, include_all_group=self.include_all_group))
                raise ValueError(f"Cannot find {self.reference_group} "
                                 f"among defined groups ({found_groups_str})")
        else:
            self.reference_avg_by_column = None

    def add_scalar_description_columns(self, column_name):
        """Add the scalar description columns for a given column_name in the |DataFrame| instance
        being analyzed.
        """
        for descriptor in ["min", "max", "avg", "std", "median"]:
            self.add_column_function(
                self,
                fun=functools.partial(self.set_scalar_description, column_selection=column_name),
                column_properties=enb.atable.ColumnProperties(
                    name=f"{column_name}_{descriptor}", label=f"{column_name}: {descriptor}"))

    def set_scalar_description(self, *args, **kwargs):
        """Set basic descriptive statistics for the target column
        """
        _self, group_label, row = args
        column_name = kwargs["column_selection"]

        full_series = _self.label_to_df[group_label][column_name]
        finite_series = full_series.replace([np.inf, -np.inf], np.nan, inplace=False).dropna()

        if len(full_series) != len(finite_series):
            if len(finite_series) > 0:
                enb.logger.warn(f"{_self.__class__.__name__}: set_scalar_description for group {repr(group_label)}, "
                                f"column {repr(column_name)} "
                                f"is ignoring infinite values ({100 * (1 - len(finite_series) / len(full_series)):.2f}%"
                                f" of the total).")
            else:
                enb.logger.warn(f"{_self.__class__.__name__}: set_scalar_description for group {repr(group_label)}, "
                                f"column {repr(column_name)} "
                                f"found only infinite values. Several statistics will be nan for this case.")

        description_df = finite_series.describe()
        row[f"{column_name}_min"] = description_df["min"]
        row[f"{column_name}_max"] = description_df["max"]
        row[f"{column_name}_avg"] = description_df["mean"]
        row[f"{column_name}_std"] = description_df["std"]
        row[f"{column_name}_median"] = description_df["50%"]

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes
        a list of `enb.plotdata.PlottableData elements` for this case (group, column, render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        if kwargs["render_mode"] == "histogram":
            return self.compute_histogram_plottable_one_case(*args, **kwargs)
        else:
            raise ValueError(f"Invalid reder mode {kwargs['render_mode']}")

    def compute_histogram_plottable_one_case(self, *args, **kwargs):
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        reference_group = kwargs["reference_group"]
        column_series = group_df[column_name].copy()

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        # Only histogram mode is supported in this version of enb
        assert render_mode == "histogram"

        # Set the analysis range based on column properties if provided, or the data's dynamic range.
        try:
            analysis_range = [_self.analyzer.column_to_properties[column_name].plot_min,
                              _self.analyzer.column_to_properties[column_name].plot_max]
        except KeyError:
            analysis_range = [None, None]
        analysis_range[0] = analysis_range[0] if analysis_range[0] is not None \
            else self.column_to_xmin_xmax[column_name][0]
        analysis_range[1] = analysis_range[1] if analysis_range[1] is not None \
            else self.column_to_xmin_xmax[column_name][1]
        if analysis_range[0] == analysis_range[1]:
            # Avoid unnecessary warnings from matplotlib
            analysis_range = [analysis_range[0], analysis_range[0] + 1]

        finite_only_series = column_series.replace([np.inf, -np.inf], np.nan, inplace=False).dropna()
        if len(finite_only_series) == 0:
            enb.logger.warn(f"{_self.__class__.__name__}: No finite data found for column {repr(column_name)}. "
                            f"No plottable data is produced for this case.")
            row[_column_name] = []
            return

        if math.isinf(analysis_range[0]):
            analysis_range[0] = finite_only_series.min()
        if math.isinf(analysis_range[1]):
            analysis_range[1] = finite_only_series.max()

        # Use numpy to obtain the absolute mass distribution of the data.
        # density=False is used so that we can detect the case where
        # some data is not used.
        if self.reference_group is not None:
            analysis_range = (self.reference_df[column_name].min(),
                              self.reference_df[column_name].max())

        hist_y_values, bin_edges = np.histogram(
            finite_only_series,
            bins=_self.analyzer.histogram_bin_count,
            range=analysis_range,
            density=False)

        # Verify that the histogram uses all data
        if sum(hist_y_values) != len(finite_only_series):
            justified_difference = False
            error_msg = f"Not all samples are included in the scalar value histogram for {column_name} " \
                        f"({sum(hist_y_values)} used out of {len(column_series)}). " \
                        f"The used range was [{analysis_range[0]}, {analysis_range[0]}]."
            if math.isinf(row[f"{column_name}_min"]) or math.isinf(row[f"{column_name}_max"]):
                error_msg += f" Note that infinite values have been found in the column, " \
                             f"which are not included in the analysis."
                justified_difference = True
            if analysis_range[0] > row[f"{column_name}_min"] or analysis_range[1] < row[
                f"{column_name}_max"]:
                error_msg += f" This is likely explained by the plot_min/plot_max or y_min/y_max " \
                             f"values set for this analysis."
                justified_difference = True
            if justified_difference:
                enb.log.info(error_msg)
            else:
                raise ValueError(error_msg)

        row[_column_name] = []

        marker_y_position = 0.5
        if _self.analyzer.bar_width_fraction > 0 and _self.analyzer.main_alpha > 0:
            # The relative distribution is computed based
            # on the selected analysis range only, which
            # may differ from the full column dynamic range
            # (hence the warning(s) above)
            histogram_sum = hist_y_values.sum()
            hist_x_values = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            # hist_x_values = bin_edges[:-1]
            hist_y_values = hist_y_values / histogram_sum if histogram_sum != 0 else hist_y_values

            marker_y_position = 0.5 * (hist_y_values.max() + hist_y_values.min())

            # Create the plotdata.PlottableData instances for this group
            row[_column_name].append(plotdata.BarData(
                x_values=hist_x_values,
                y_values=hist_y_values,
                x_label=_self.analyzer.column_to_properties[column_name].label \
                    if column_name in _self.analyzer.column_to_properties else clean_column_name(column_name),
                alpha=_self.analyzer.main_alpha,
                extra_kwargs=dict(
                    width=_self.analyzer.bar_width_fraction * (bin_edges[1] - bin_edges[0]))))

        row[_column_name].append(plotdata.ScatterData(
            x_values=[row[f"{column_name}_avg"]],
            y_values=[marker_y_position],
            marker_size=4 * _self.analyzer.main_marker_size,
            alpha=_self.analyzer.secondary_alpha))
        if _self.analyzer.show_x_std:
            row[_column_name].append(plotdata.ErrorLines(
                x_values=[row[f"{column_name}_avg"]],
                y_values=[marker_y_position],
                marker_size=0,
                alpha=_self.analyzer.secondary_alpha,
                err_neg_values=[row[f"{column_name}_std"]],
                err_pos_values=[row[f"{column_name}_std"]],
                line_width=_self.analyzer.secondary_line_width,
                vertical=False))

        if self.reference_group:
            row[_column_name].append(plotdata.VerticalLine(x_position=0, alpha=0.3, color="black"))


@enb.config.aini.managed_attributes
class TwoNumericAnalyzer(Analyzer):
    """Analyze pairs of columns containing scalar, numeric values.
    Compute basic statistics and produce a scatter plot based on the obtained data.

    As opposed to ScalarNumericAnalyzer, target_columns should be
    an iterable of tuples with 2 column names (other elements are ignored).
    When applicable, the first column in each tuple is considered
    the x column, and the second the y column.
    """
    # The following attributes are directly used for analysis/plotting,
    # and can be modified before any call to get_df. These values may be updated based on .ini files,
    # see the documentation of the enb.config.aini.managed_attributes decorator for more information.
    # Common analyzer attributes:
    valid_render_modes = {"scatter", "line"}
    selected_render_modes = set(valid_render_modes)
    plot_title = None
    show_count = True
    show_global = False
    main_marker_size = 5
    show_x_std = True
    show_y_std = True
    main_alpha = 0.5
    secondary_alpha = 0.5
    semilog_y_min_bound = 1e-5
    main_line_width = 2
    secondary_line_width = 1
    group_row_margin = 0.2
    common_group_scale = True
    combine_groups = True
    show_legend = True

    # Specific analyzer attributes:
    show_individual_samples = True

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.AAnalyzer.normalize_parameters,
            # in turn manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to plotdata.render_plds_by_group
            **column_kwargs):
        # Update common rendering kwargs
        column_kwargs = super().update_render_kwargs_one_case(
            column_selection=column_selection, reference_group=reference_group,
            render_mode=render_mode,
            summary_df=summary_df, output_plot_dir=output_plot_dir,
            group_by=group_by, column_to_properties=column_to_properties,
            show_global=show_global, show_count=show_count,
            **column_kwargs)

        # Update global x and y labels
        try:
            x_column_name, y_column_name = column_selection
        except TypeError as ex:
            raise SyntaxError(f"Passed invalid column selection to {self.__class__.__name__}: "
                              f"{repr(column_selection)}") from ex
        try:
            x_column_properties = column_to_properties[x_column_name]
        except (KeyError, TypeError):
            x_column_properties = enb.atable.ColumnProperties(x_column_name)
        try:
            y_column_properties = column_to_properties[y_column_name]
        except (KeyError, TypeError):
            y_column_properties = enb.atable.ColumnProperties(y_column_name)
        if "global_x_label" not in column_kwargs:
            column_kwargs["global_x_label"] = x_column_properties.label + \
                                              (f" difference vs. {reference_group} average" if reference_group else "")
        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = y_column_properties.label + \
                                              (f" difference vs. {reference_group} average" if reference_group else "")

        # Calculate axis limits
        if "x_min" not in column_kwargs:
            column_kwargs["x_min"] = float(summary_df[f"{x_column_name}_min"].min()) \
                if column_to_properties[x_column_name].plot_min is None \
                else column_to_properties[x_column_name].plot_min
        if "x_max" not in column_kwargs:
            column_kwargs["x_max"] = float(summary_df[f"{x_column_name}_max"].max()) \
                if column_to_properties[x_column_name].plot_max is None \
                else column_to_properties[x_column_name].plot_max
        if "y_min" not in column_kwargs:
            column_kwargs["y_min"] = float(summary_df[f"{y_column_name}_min"].min()) \
                if column_to_properties[y_column_name].plot_min is None \
                else column_to_properties[y_column_name].plot_min
        if "y_max" not in column_kwargs:
            column_kwargs["y_max"] = float(summary_df[f"{y_column_name}_max"].max()) \
                if column_to_properties[y_column_name].plot_max is None \
                else column_to_properties[y_column_name].plot_max

        # Adjust a common scale for all subplots
        if self.common_group_scale and ("y_min" not in column_kwargs or "y_max" not in column_kwargs):
            global_x_min = float("inf")
            global_x_max = float("-inf")
            global_y_min = float("inf")
            global_y_max = float("-inf")
            for pld_list in summary_df[f"{column_selection}_render-{render_mode}"]:
                if render_mode == "scatter":
                    candidate_plds = (pld for pld in pld_list if isinstance(pld, plotdata.ScatterData))
                elif render_mode == "line":
                    candidate_plds = (pld for pld in pld_list if isinstance(pld, plotdata.LineData))
                for pld in candidate_plds:
                    global_x_min = min(global_x_min, min(pld.x_values))
                    global_x_max = max(global_x_max, max(pld.x_values))
                    global_y_min = min(global_y_min, min(pld.y_values))
                    global_y_max = max(global_y_max, max(pld.y_values))
            if "y_min" not in column_kwargs:
                column_kwargs["y_min"] = global_y_min
            if "y_max" not in column_kwargs:
                column_kwargs["y_max"] = global_y_max

        if len(summary_df) >= 5 and "group_row_margin" not in column_kwargs:
            column_kwargs["group_row_margin"] = 0.2 * len(summary_df)

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, reference_group, group_by, include_all_group):
        return TwoNumericSummary(analyzer=self, full_df=full_df, reference_group=reference_group,
                                 target_columns=target_columns, group_by=group_by,
                                 include_all_group=include_all_group)


class TwoNumericSummary(ScalarNumericSummary):
    """Summary table used in TwoNumericAnalyzer.

    For this class, target_columns must be a list of tuples, each tuple containing two column name,
    corresponding to x and y, respectively. Scalar analysis is provided on each column individually,
    as well as basic correlation metrics for each pair of columns.
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group, group_by, include_all_group):
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_name and render_mode.
        AnalyzerSummary.__init__(
            self=self, analyzer=analyzer, full_df=full_df,
            target_columns=target_columns, reference_group=reference_group,
            group_by=group_by, include_all_group=include_all_group)
        self.apply_reference_bias()

        # Add columns that compute the summary information
        self.column_to_xmin_xmax = {}
        for x_y_names in target_columns:
            for column_name in x_y_names:
                if column_name not in full_df.columns:
                    raise ValueError(f"Invalid column name selection {repr(column_name)}. "
                                     f"Full selection: {repr(target_columns)}")
                if column_name in self.column_to_xmin_xmax:
                    continue
                self.add_scalar_description_columns(column_name=column_name)

                try:
                    self.column_to_xmin_xmax[column_name] = scipy.stats.describe(full_df[column_name].values).minmax
                except FloatingPointError as ex:
                    if len(full_df) == 1:
                        self.column_to_xmin_xmax[column_name] = (full_df[column_name][0], full_df[column_name][0])
                    else:
                        enb.logger.error(f"column_name={column_name}")
                        enb.logger.error(f"full_df[column_name].values={full_df[column_name].values}")
                        raise ex

            self.add_twoscalar_description_columns(column_names=x_y_names)

        self.move_render_columns_back()

    def apply_reference_bias(self):
        """Compute the average value of the reference group for each target column and
        subtract it from the dataframe being analyzed. If not reference group is present,
        no action is performed.
        """
        if self.reference_group is not None:
            if self.group_by is None:
                raise ValueError(f"Cannot use a not-None reference_group if group_by is None "
                                 f"(here is {repr(self.reference_group)})")

            for group_label, group_df in self.split_groups():
                if group_label == self.reference_group:
                    target_columns = set()
                    for c1, c2 in self.target_columns:
                        target_columns.add(c1)
                        target_columns.add(c2)

                    self.reference_avg_by_column = {
                        c: group_df[group_df[c].notna()][c].mean()
                        for c in target_columns
                    }

                    self.reference_df = self.reference_df.copy()
                    for c, avg in self.reference_avg_by_column.items():
                        self.reference_df[c] -= avg
                    break
            else:
                found_groups_str = ','.join(repr(label) for label, _ in self.split_groups(
                    reference_df=self.reference_df, include_all_group=self.include_all_group))
                raise ValueError(f"Cannot find {self.reference_group} "
                                 f"among defined groups ({found_groups_str})")
        else:
            self.reference_avg_by_column = None

    def add_twoscalar_description_columns(self, column_names):
        """Add columns that compute several statistics considering two columns jointly, e.g., their correlation.
        """
        for descriptor in ["pearson_correlation", "pearson_correlation_pvalue",
                           "spearman_correlation", "spearman_correlation_pvalue",
                           "linear_lse_slope", "linear_lse_intercept"]:
            cp = enb.atable.ColumnProperties(
                name=f"{column_names[0]}_{column_names[1]}_{descriptor}",
                label=f"{descriptor[:1].upper() + descriptor[1:]} "
                      f"for {column_names[0]}, {column_names[1]}".replace("_", " "))
            self.add_column_function(
                self,
                fun=functools.partial(self.set_twoscalar_description, column_selection=column_names),
                column_properties=cp)

    def set_twoscalar_description(self, *args, **kwargs):
        """Set basic descriptive statistics for the target column
        """
        _, group_label, row = args
        x_column_name, y_column_name = kwargs["column_selection"]

        if len(self.reference_df) > 1:
            row[f"{x_column_name}_{y_column_name}_pearson_correlation"], \
            row[f"{x_column_name}_{y_column_name}_pearson_correlation_pvalue"] = \
                scipy.stats.pearsonr(self.reference_df[x_column_name], self.reference_df[y_column_name])
            row[f"{x_column_name}_{y_column_name}_spearman_correlation"], \
            row[f"{x_column_name}_{y_column_name}_spearman_correlation_pvalue"] = \
                scipy.stats.spearmanr(self.reference_df[x_column_name], self.reference_df[y_column_name])
            lr_results = scipy.stats.linregress(self.reference_df[x_column_name], self.reference_df[y_column_name])
            row[f"{x_column_name}_{y_column_name}_linear_lse_slope"] = lr_results.slope
            row[f"{x_column_name}_{y_column_name}_linear_lse_intercept"] = lr_results.intercept
        else:
            enb.logger.warn("Cannot set correlation metrics for dataframes of length 1")
            row[f"{x_column_name}_{y_column_name}_pearson_correlation"] = float("inf")
            row[f"{x_column_name}_{y_column_name}_pearson_correlation_pvalue"] = float("inf")
            row[f"{x_column_name}_{y_column_name}_spearman_correlation"] = float("inf")
            row[f"{x_column_name}_{y_column_name}_spearman_correlation_pvalue"] = float("inf")
            row[f"{x_column_name}_{y_column_name}_linear_lse_slope"] = float("inf")
            row[f"{x_column_name}_{y_column_name}_linear_lse_intercept"] = float("inf")

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes
        a list of `enb.plotdata.PlottableData elements` for this case (group, column, render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        _self, group_label, row = args
        group_df = self.label_to_df[group_label]
        x_column_name, y_column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        reference_group = kwargs["reference_group"]
        x_column_series = group_df[x_column_name]
        y_column_series = group_df[y_column_name]
        if render_mode not in self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        plds_this_case = []
        if render_mode == "scatter":
            plds_this_case.append(plotdata.ScatterData(
                x_values=[row[f"{x_column_name}_avg"]],
                y_values=[row[f"{y_column_name}_avg"]],
                alpha=self.analyzer.main_alpha,
                marker_size=5 * self.analyzer.main_marker_size))
            if self.analyzer.show_individual_samples:
                plds_this_case.append(plotdata.ScatterData(
                    x_values=x_column_series.values,
                    y_values=y_column_series.values,
                    alpha=self.analyzer.secondary_alpha,
                    marker_size=5 * self.analyzer.secondary_marker_size,
                    extra_kwargs=dict(linewidths=0)))
            if self.analyzer.show_x_std:
                plds_this_case.append(plotdata.ErrorLines(
                    x_values=[row[f"{x_column_name}_avg"]],
                    y_values=[row[f"{y_column_name}_avg"]],
                    marker_size=0,
                    alpha=self.analyzer.secondary_alpha,
                    err_neg_values=[row[f"{x_column_name}_std"]],
                    err_pos_values=[row[f"{x_column_name}_std"]],
                    line_width=self.analyzer.secondary_line_width,
                    vertical=False))
            if self.analyzer.show_y_std:
                plds_this_case.append(plotdata.ErrorLines(
                    x_values=[row[f"{x_column_name}_avg"]],
                    y_values=[row[f"{y_column_name}_avg"]],
                    marker_size=0,
                    alpha=self.analyzer.secondary_alpha,
                    err_neg_values=[row[f"{y_column_name}_std"]],
                    err_pos_values=[row[f"{y_column_name}_std"]],
                    line_width=self.analyzer.secondary_line_width,
                    vertical=True))
        elif render_mode == "line":
            if is_family_grouping(group_by=self.group_by):
                # Family line plots look into the task names and produce
                # one marker per task, linking same-family tasks with a line.
                x_values = []
                y_values = []
                current_family = [f for f in self.group_by if f.label == group_label][0]
                for task_name in current_family.task_names:
                    task_df = group_df[group_df["task_name"] == task_name]
                    x_values.append(task_df[x_column_name].mean())
                    y_values.append(task_df[y_column_name].mean())
            else:
                # Regular line plots are sorted by x values
                x_values, y_values = zip(*sorted(zip(
                    x_column_series.values, y_column_series.values)))
            plds_this_case.append(plotdata.LineData(
                x_values=x_values,
                y_values=y_values,
                alpha=self.analyzer.secondary_alpha,
                marker_size=self.analyzer.main_marker_size - 1))
        else:
            raise SyntaxError(f"Invalid render mode {repr(render_mode)} not within the "
                              f"supported ones for {self.analyzer.__class__.__name__} "
                              f"({repr(self.analyzer.valid_render_modes)}")

        # Plot the reference lines only once per plot to maintain the desired alpha
        if reference_group is not None and \
                ((group_label == sorted(self.label_to_df.keys())[0] and group_label != reference_group)
                        or (sorted(self.label_to_df.keys())[0] == reference_group
                            and sorted(self.label_to_df.keys())[0] == group_label)):
            plds_this_case.append(plotdata.VerticalLine(
                x_position=self.reference_avg_by_column[x_column_name],
                color="black",
                alpha=0.3,
                line_width=1))
            plds_this_case.append(plotdata.HorizontalLine(
                y_position=self.reference_avg_by_column[y_column_name],
                color="black",
                alpha=0.3,
                line_width=1))

        return plds_this_case


@enb.config.aini.managed_attributes
class DictNumericAnalyzer(Analyzer):
    """Analyzer for columns with associated ColumnProperties having has_dict=True.
    Dictionaries are expected to have numeric entries.
    """
    # The following attributes are directly used for analysis/plotting,
    # and can be modified before any call to get_df. These values may be updated based on .ini files,
    # see the documentation of the enb.config.aini.managed_attributes decorator for more information.
    # Common analyzer attributes:
    valid_render_modes = {"line"}
    selected_render_modes = set(valid_render_modes)
    plot_title = None
    show_count = True
    show_global = True
    show_x_std = True
    show_y_std = True
    main_marker_size = None
    secondary_marker_size = None
    main_alpha = 0.5
    secondary_alpha = 0.5
    semilog_y_min_bound = 1e-5
    main_line_width = 2
    secondary_line_width = 2
    group_row_margin = 0.2
    common_group_scale = True
    combine_groups = False
    show_legend = False

    # Specific analyzer attributes:
    show_individual_samples = True

    def __init__(self, csv_support_path=None,
                 column_to_properties=None,
                 progress_report_period=None,
                 combine_keys_callable=None):
        """
        :param csv_support_path: support path where results are to be stored.
          If None, results are not automatically made persistent.
        :param column_to_properties: dictionary mapping column names to
          ther properties
        :param progress_report_period: period with which progress reports
          are emitted by the parallel computation of the analysis table.
        :param combine_keys_callable: if not None, it must be a callable that
          takes dictionary with numeric values and return another one with
          possibly different keys (e.g., merging several dict keys into one).
        """
        super().__init__(csv_support_path=csv_support_path,
                         column_to_properties=column_to_properties,
                         progress_report_period=progress_report_period)
        self.combine_keys_callable = combine_keys_callable
        # Overwritten with every call to self.get_df
        self.column_name_to_keys = {}

    def get_df(self, full_df, target_columns,
               selected_render_modes=None,
               output_plot_dir=None, group_by=None, reference_group=None, column_to_properties=None,
               show_global=None, show_count=True,
               key_to_x=None,
               **render_kwargs):
        """Analyze and plot columns containing dictionaries with numeric data.

        :param full_df: full DataFrame instance with data to be plotted and/or analyzed.
        :param target_columns: columns to be analyzed. Typically, a list of column names, although
          each subclass may redefine the accepted format (e.g., pairs of column names). If None,
          all scalar, non string columns are used.
        :param selected_render_modes: a potentially empty list of mode names, all of which
          must be in self.valid_render_modes. Each mode represents a type of analysis or plotting.
        :param group_by: if not None, the name of the column to be used for grouping.
        :param reference_group: if not None, the reference group name against which data are to be analyzed.
        :param output_plot_dir: path of the directory where the plot/plots is/are to be saved.
          If None, the default output plots path given by `enb.config.options` is used.
        :param column_to_properties: dictionary with ColumnProperties entries. ATable instances provide it
          in the :attr:`column_to_properties` attribute, :class:`Experiment` instances can also use the
          :attr:`joined_column_to_properties` attribute to obtain both the dataset and experiment's
          columns.
        :param show_global: if True, a group containing all elements is also included in the analysis
        :param key_to_x: if provided, it can be a mapping between the keys found in the column data dictionaries,
          and the x value in which they should be plotted.

        :return: a |DataFrame| instance with analysis results"""
        try:
            self.key_to_x = dict(key_to_x) if key_to_x is not None else key_to_x

            combined_df = full_df.copy()
            self.column_name_to_keys = dict()

            # Keys are combined before analyzing. This allows to compute just once the key_to_x dictionary shared
            # across all groups.
            for column_name in target_columns:
                if self.combine_keys_callable:
                    combined_df[f"__{column_name}_combined"] = combined_df[column_name].apply(
                        self.combine_keys_callable)
                else:
                    combined_df[f"__{column_name}_combined"] = combined_df[column_name]
                self.column_name_to_keys[column_name] = set()
                for key_set in combined_df[f"__{column_name}_combined"].apply(lambda d: tuple(d.keys())).unique():
                    for k in key_set:
                        self.column_name_to_keys[column_name].add(k)
                self.column_name_to_keys[column_name] = sorted(self.column_name_to_keys[column_name])

            return super().get_df(full_df=combined_df,
                                  target_columns=target_columns,
                                  output_plot_dir=output_plot_dir,
                                  group_by=group_by,
                                  reference_group=reference_group,
                                  column_to_properties=column_to_properties,
                                  selected_render_modes=selected_render_modes,
                                  show_global=show_global, show_count=show_count,
                                  **render_kwargs)
        finally:
            if self.key_to_x is not None:
                del self.key_to_x

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.AAnalyzer.normalize_parameters,
            # in turn manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to plotdata.render_plds_by_group
            **column_kwargs):

        # Update common rendering kwargs
        column_kwargs = super().update_render_kwargs_one_case(
            column_selection=column_selection, reference_group=reference_group,
            render_mode=render_mode,
            summary_df=summary_df, output_plot_dir=output_plot_dir,
            group_by=group_by, column_to_properties=column_to_properties,
            show_global=show_global, show_count=show_count,
            **column_kwargs)

        # Update global x and y labels
        column_name = column_selection
        column_properties = column_to_properties[column_name]

        if "global_x_label" not in column_kwargs:
            column_kwargs["global_x_label"] = f"{column_properties.label} (keys)"
        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = f"{column_properties.label} (values)"

        # Adjust a common scale for all subplots
        if self.common_group_scale and ("y_min" not in column_kwargs and "y_max" not in column_kwargs):
            self.adjust_common_row_axes(column_kwargs=column_kwargs,
                                        column_selection=column_selection,
                                        render_mode=render_mode,
                                        summary_df=summary_df)

        # Set the x ticks and labels
        if "x_tick_list" not in column_kwargs:
            column_kwargs["x_tick_list"] = list(range(len(self.column_name_to_keys[column_name])))
        if "x_tick_label_list" not in column_kwargs:
            column_kwargs["x_tick_label_list"] = self.column_name_to_keys[column_name]

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, reference_group, group_by, include_all_group):
        return DictNumericSummary(
            analyzer=self, full_df=full_df, target_columns=target_columns,
            reference_group=reference_group,
            group_by=group_by, include_all_group=include_all_group)


class DictNumericSummary(AnalyzerSummary):
    """Summary table for the DictNumericAnalyzer.
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group, group_by, include_all_group):
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_name and render_mode.
        AnalyzerSummary.__init__(
            self=self, analyzer=analyzer, full_df=full_df,
            target_columns=target_columns, reference_group=reference_group,
            group_by=group_by, include_all_group=include_all_group)

        for column_name in target_columns:
            # The original dicts are combined based on the analyzer's combine_keys_callable
            try:
                if not self.analyzer.column_to_properties[column_name].has_dict_values:
                    raise ValueError(f"Attempting to use {self.__class__.__name__} on "
                                     f"column {repr(column_name)}, which is does not have "
                                     f"has_dict_values=True in its column properties.")
            except KeyError:
                pass

        self.move_render_columns_back()

    def combine_keys(self, *args, **kwargs):
        """Combine the keys of a column containing
        """
        _, group_label, row = args
        column_name = kwargs["column_selection"]
        try:
            row[_column_name] = self.analyzer.combine_keys_callable(row[column_name])
        except TypeError:
            row[_column_name] = row[column_name]

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes
        a list of `enb.plotdata.PlottableData elements` for this case (group, column, render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        reference_group = kwargs["reference_group"]
        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        # Only one mode is supported in this version of enb
        assert render_mode == "line"

        row[_column_name] = []

        x_values = []
        avg_values = []
        std_values = []
        for x, k in enumerate(_self.analyzer.column_name_to_keys[column_name]):
            values = group_df[f"__{column_name}_combined"].apply(lambda d: d[k] if k in d else None).dropna()
            if len(values) > 0:
                if _self.analyzer.key_to_x:
                    x_values.append(_self.analyzer.key_to_x[k])
                else:
                    x_values.append(x)
                avg_values.append(values.mean())
                std_values.append(values.std())
                if _self.analyzer.show_individual_samples:
                    row[_column_name].append(enb.plotdata.ScatterData(x_values=x_values[-1:] * len(values),
                                                                      y_values=values.values,
                                                                      alpha=self.analyzer.secondary_alpha))
        if render_mode == "line":
            row[_column_name].append(enb.plotdata.LineData(
                x_values=x_values, y_values=avg_values, alpha=self.analyzer.main_alpha))
            if _self.analyzer.show_y_std:
                row[_column_name].append(enb.plotdata.ErrorLines(
                    x_values=x_values, y_values=avg_values,
                    err_neg_values=std_values, err_pos_values=std_values,
                    alpha=self.analyzer.secondary_alpha,
                    vertical=True))
        else:
            raise ValueError(f"Unexpected render mode {render_mode} for {self.__class__.__name__}")


class HistogramKeyBinner:
    """Helper class to transform numeric-to-numeric dicts into other dicts
    binning keys like an histogram.
    """

    def __init__(self, min_value, max_value, bin_count, normalize=False):
        """
        :param min_value: minimum expected key value
        :param max_value:
        :param bin_count:
        :param normalize:
        """
        self.min_value = min_value
        self.max_value = max_value
        self.bin_count = bin_count
        assert self.bin_count > 0
        self.bin_width = max(1e-10, (max_value - min_value) / self.bin_count)
        self.intervals = [(min_value, min(min_value + self.bin_width, max_value))
                          for min_value in np.linspace(min_value, max(min_value, max_value - self.bin_width),
                                                       self.bin_count, endpoint=True)]

        self.binned_keys = []
        for i, interval in enumerate(self.intervals):
            s = "["
            s += ",".join(f"{v:.2f}" if int(v) != v else str(v) for v in interval)
            s += ")" if i < len(self.intervals) - 1 else "]"
            self.binned_keys.append(s)
        self.normalize = normalize

    def __call__(self, input_dict):
        """When an instance of this class is called, it takes an input dictionary
        with numeric keys and values (e.g., something like {x:f(x) for x in x_values}).
        The specified range of key values is split into a given number of bins (intervals),
        and a dictionary is returned, with keys being those intervals and the values
        being the sum of all elements in the input dict with keys inside that bin.
        """
        index_to_sum = [0] * len(self.binned_keys)
        total_sum = 0
        ignored_sum = 0
        for k, v in input_dict.items():
            try:
                index_to_sum[math.floor((k - self.min_value) / self.bin_width)] += v
            except IndexError as ex:
                if k == self.max_value:
                    index_to_sum[-1] += v
                else:
                    ignored_sum += v
            total_sum += v

        if ignored_sum > 0 and options.verbose > 2:
            enb.log.warn(f"{self.__class__.__name__} is ignorning {100 * ignored_sum / total_sum:.6f}% "
                         f"of the values, which lie outside {self.min_value, self.max_value}. "
                         f"This is likely OK if you specified x_min or x_max manually.")

        output_dict = collections.OrderedDict()
        for i, k in enumerate(self.binned_keys):
            output_dict[k] = index_to_sum[i] / (total_sum if self.normalize else 1)

        return output_dict

    def __repr__(self):
        return f"{self.__class__.__name__}({','.join(f'{k}={v}' for k, v in self.__dict__.items())})"


def columnname_to_labels(column_name):
    """Guess x_label and y_label from a name column.
    If _to_ is found once in the string, x_label will be obtained from the text to the left,
    and y_label from the text to the right.
    Otherwise, x_label is set using the complete column_name string, and y_label is None
    """
    parts = column_name.split("_to_")
    if len(parts) == 2:
        x_label, y_label = clean_column_name(parts[0]), clean_column_name(parts[1])
    else:
        x_label, y_label = clean_column_name(column_name), None
    return x_label, y_label


class PDFToPNG(enb.sets.FileVersionTable):
    """Take all .pdf files in input dir and save them as .png files into output_dir,
    maintining the relative folder structure.
    """
    dataset_files_extension = "pdf"

    def __init__(self, input_pdf_dir, output_png_dir, csv_support_path=None):
        super().__init__(version_name="pdf_to_png",
                         original_base_dir=input_pdf_dir,
                         version_base_dir=output_png_dir,
                         csv_support_path=csv_support_path,
                         check_generated_files=True)

    def version(self, input_path, output_path, row):
        with enb.logger.info_context(f"{self.__class__.__name__}: {input_path} -> {output_path}...\n"):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            imgs = pdf2image.convert_from_path(pdf_path=input_path)
            assert len(imgs) == 1
            imgs[0].save(output_path)


def pdf_to_png(input_dir, output_dir, **kwargs):
    """Take all .pdf files in input dir and save them as .png files into output_dir,
    maintining the relative folder structure.

    It is perfectly valid for input_dir and output_dir
    to point to the same location, but input_dir must exist beforehand.

    :param kwargs: other parameters directly passed to pdf2image.convert_from_path. Refer to their
      documentation for more information: https://github.com/Belval/pdf2image,
      https://pdf2image.readthedocs.io/en/latest/reference.html#functions
    """
    with tempfile.NamedTemporaryFile() as tmp_file:
        PDFToPNG(input_pdf_dir=input_dir, output_png_dir=output_dir, csv_support_path=tmp_file.name).get_df()
