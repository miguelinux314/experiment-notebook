#!/usr/bin/env python3
"""Automatic analysis and report of of pandas :class:`pandas.DataFrames`
(e.g., produced by :class:`enb.experiment.Experiment` instances)
using pyplot.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/01/01"

import functools
import os
import itertools
import math
import collections
import collections.abc

import deprecation
import sortedcontainers
import re
import glob
import numbers

import pdf2image
import numpy as np
import scipy.stats
import pandas as pd
import ray

import enb.atable
from enb.atable import get_nonscalar_value
from enb import plotdata
from enb.config import options
from enb.plotdata import parallel_render_plds_by_group
from enb.plotdata import render_plds_by_group
from enb.plotdata import color_cycle
from enb.plotdata import marker_cycle


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
               # Dynamic arguments with every call
               output_plot_dir=None,
               group_by=None, column_to_properties=None,
               # Arguments normalized by the @enb.aanalysis.AAnalyzer.normalize_parameters,
               # in turn manageable through .ini configuration files via the
               # @enb.config.aini.managed_attributes decorator.
               selected_render_modes=None, show_global=None, show_count=True, plot_title=None,
               # Rendering options, directly passed to plotdata.render_plds_by_group
               **render_kwargs):
        """
        Analyze a :class:`pandas.DataFrame` instance, optionally producing plots, and returning the computed
        dataframe with the analysis results.

        Rendering is performed for all modes contained self.selected_render_modes, which
        must be in self.valid_render_modes.

        You can use the @enb.aanalysis.Analyzer.normalize_parameters decorator when overwriting this method,
        to automatically transform None values into their defaults.

        :param full_df: full DataFrame instance with data to be plotted and/or analyzed.
        :param target_columns: columns to be analyzed. Typically a list of column names, although
          each subclass may redefine the accepted format (e.g., pairs of column names). If None,
          all scalar, non string columns are used.
        :param output_plot_dir: path of the directory where the plot/plots is/are to be saved.
          If None, the default output plots path given by `enb.config.options` is used.
        :param group_by: if not None, the name of the column to be used for grouping.
        :param column_to_properties: dictionary with ColumnProperties entries. ATable instances provide it
          in the :attr:`column_to_properties` attribute, :class:`Experiment` instances can also use the
          :attr:`joined_column_to_properties` attribute to obtain both the dataset and experiment's
          columns.

        :param selected_render_modes: a potentially empty list of mode names, all of which
          must be in self.valid_render_modes
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

        def normalized_wrapper(self, full_df, target_columns,
                               output_plot_dir, group_by, column_to_properties,
                               selected_render_modes,
                               **render_kwargs):
            # Get the summary table with the requested data analysis
            summary_table = self.build_summary_atable(
                full_df=full_df, target_columns=target_columns, group_by=group_by,
                include_all_group=show_global)
            old_nnr = options.no_new_results
            try:
                options.no_new_results = False
                summary_df = summary_table.get_df(reference_df=full_df)
            finally:
                options.no_new_results = old_nnr

            selected_render_modes = selected_render_modes if srm is None else srm

            # Render all applicable modes
            self.render_all_modes(
                summary_df=summary_df,
                target_columns=target_columns,
                output_plot_dir=output_plot_dir,
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
            output_plot_dir=output_plot_dir,
            selected_render_modes=selected_render_modes)

        return normalized_wrapper(self=self, full_df=full_df, **render_kwargs)

    def render_all_modes(self,
                         # Dynamic arguments with every call
                         summary_df, target_columns, output_plot_dir,
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
                    column_selection=column_selection, render_mode=render_mode, summary_df=summary_df,
                    output_plot_dir=output_plot_dir, group_by=group_by, column_to_properties=column_to_properties,
                    show_global=show_global, show_count=show_count,
                    **(dict(render_kwargs) if render_kwargs is not None else dict()))

                # All arguments to the parallel rendering function are ready; their associated tasks as created
                render_ids.append(enb.plotdata.parallel_render_plds_by_group.remote(
                    **{k: ray.put(v) for k, v in column_kwargs.items()}))

        # Wait until all rendering tasks are done while updating about progress
        with enb.logger.verbose_context(f"Rendering {len(render_ids)} plots with {self.__class__.__name__}..."):
            for progress_report in enb.ray_cluster.ProgressiveGetter(
                    ray_id_list=render_ids,
                    iteration_period=self.progress_report_period):
                enb.logger.verbose(progress_report.report())

    def update_render_kwargs_one_case(
            self, column_selection, render_mode,
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
            column_selection, group_by, output_plot_dir, render_mode)
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

    def get_output_pdf_path(self, column_selection, group_by, output_plot_dir, render_mode):
        if group_by:
            if isinstance(group_by, str):
                group_by_str = group_by
            elif isinstance(group_by, collections.abc.Iterable):
                group_by_str = ",".join(group_by)
            # else:
            #     group_by_str = str(group_by)
        else:
            group_by_str = ""
        group_by_str = group_by_str if not group_by_str else f"_groupby-{group_by_str}"

        return os.path.join(
            output_plot_dir,
            f"{self.__class__.__name__}_"
            f"{column_selection}{group_by_str}_{render_mode}.pdf")

    @classmethod
    def normalize_parameters(cls, f, group_by, column_to_properties, target_columns,
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
                    full_df, target_columns=target_columns, output_plot_dir=output_plot_dir,
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

            return f(self=self, full_df=full_df, selected_render_modes=selected_render_modes,
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
                global_x_min = min(global_x_min, min(pld.x_values) if len(pld.x_values) > 0 else global_x_min)
                global_x_max = max(global_x_max, max(pld.x_values) if len(pld.x_values) > 0 else global_x_max)
                global_y_min = min(global_y_min, min(pld.y_values) if len(pld.y_values) > 0 else global_y_min)
                global_y_max = max(global_y_max, max(pld.y_values) if len(pld.y_values) > 0 else global_y_max)
        if "y_min" not in column_kwargs:
            column_kwargs["y_min"] = global_y_min
        if "y_max" not in column_kwargs:
            column_kwargs["y_max"] = global_y_max

    def build_summary_atable(self, full_df, target_columns, group_by, include_all_group):
        """
        Build a :class:`enb.aanalysis.AnalyzerSummary` instance with the appropriate
        columns to perform the intended analysis. See :class:`enb.aanalysis.AnalyzerSummary`
        for documentation on the meaning of each argument.

        :param full_df: dataframe instance being analyzed
        :param target_columns: list of columns specified for analysis
        :param include_all_group: force inclusion of an "All" group with all samples

        :return: the built summary table, without having called its get_df method.
        """
        raise SyntaxError(
            f"Subclasses must implement this method. {self.__class__} did not. "
            f"Typically, the associated AnalyzerSummary needs to be instantiated and returned. "
            f"See enb.aanalysis.Analyzer's documentation.")


class AnalyzerSummary(enb.atable.SummaryTable):
    """Base class for the surrogate, dynamic summary tables employed by :class:`enb.aanalysis.Analyzer`
    subclasses to gather analysis results and plottable data (when configured to do so).
    """

    def __init__(self, analyzer, full_df, target_columns, group_by, include_all_group):
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

        # Add columns that compute the list of plotting elements of each group, if needed
        for selected_render_mode in self.analyzer.selected_render_modes:
            for column_selection in target_columns:
                self.add_column_function(
                    self,
                    fun=functools.partial(
                        self.compute_plottable_data_one_case,
                        column_selection=column_selection,
                        render_mode=selected_render_mode),
                    column_properties=enb.atable.ColumnProperties(
                        name=f"{column_selection}_render-{selected_render_mode}",
                        has_object_values=True))

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
    # Adjust for thinner or thicker vertical bars.
    bar_width_fraction = 1

    def update_render_kwargs_one_case(
            self, column_selection, render_mode,
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
            column_selection=column_selection, render_mode=render_mode,
            summary_df=summary_df, output_plot_dir=output_plot_dir,
            group_by=group_by, column_to_properties=column_to_properties,
            show_global=show_global, show_count=show_count,
            **column_kwargs)

        # Update specific rendering kwargs for this analyzer:
        if "global_x_label" not in column_kwargs:
            column_kwargs["global_x_label"] = column_to_properties[column_selection].label

        if "global_y_label" not in column_kwargs:
            if self.main_alpha != 0:
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

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, group_by, include_all_group):
        """Dynamically build a SummaryTable instance for scalar value analysis.
        """
        return ScalarNumericSummary(analyzer=self, full_df=full_df, target_columns=target_columns,
                                    group_by=group_by, include_all_group=include_all_group)


class ScalarNumericSummary(AnalyzerSummary):
    """Summary table used in ScalarValueAnalyzer, defined dynamically with each call to maintain
    independent column definitions.

    Note that dynamically in this context implies that modifying the returned instance's class columns does
    not affect the definition of other instances of this class.

    Note that in most cases, the columns returned by default
    should suffice.
    """

    def __init__(self, analyzer, full_df, target_columns, group_by, include_all_group):
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_selection and render_mode.
        AnalyzerSummary.__init__(
            self=self,
            analyzer=analyzer, full_df=full_df, target_columns=target_columns,
            group_by=group_by, include_all_group=include_all_group)

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
        _, group_label, row = args
        column_name = kwargs["column_selection"]

        full_series = self.label_to_df[group_label][column_name]
        finite_series = full_series.replace([np.inf, -np.inf], np.nan, inplace=False).dropna()

        if len(full_series) != len(finite_series):
            if len(finite_series) > 0:
                enb.logger.warn(f"{self.__class__.__name__}: set_scalar_description for group {repr(group_label)}, "
                                f"column {repr(column_name)} "
                                f"is ignoring infinite values ({100 * (1 - len(finite_series) / len(full_series)):.2f}%"
                                f" of the total).")
            else:
                enb.logger.warn(f"{self.__class__.__name__}: set_scalar_description for group {repr(group_label)}, "
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
        _self, group_label, row = args
        group_df = self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        column_series = group_df[column_name]
        if render_mode not in self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        # Only histogram mode is supported in this version of enb
        assert render_mode == "histogram"

        # Set the analysis range based on column properties if provided, or the data's dynamic range.
        try:
            analysis_range = [self.analyzer.column_to_properties[column_name].plot_min,
                              self.analyzer.column_to_properties[column_name].plot_max]
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
            enb.logger.warn(f"{self.__class__.__name__}: No finite data found for column {repr(column_name)}. "
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
        hist_y_values, bin_edges = np.histogram(
            finite_only_series,
            bins=self.analyzer.histogram_bin_count,
            range=analysis_range, density=False)

        # Verify that the histogram uses all data
        if sum(hist_y_values) != len(finite_only_series):
            justified_difference = False
            error_msg = f"Not all samples are included in the scalar value histogram for {column_name} " \
                        f"({sum(hist_y_values)} used out of {len(column_series)})."
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

        # The relative distribution is computed based
        # on the selected analysis range only, which
        # may differ from the full column dynamic range
        # (hence the warning(s) above)
        histogram_sum = hist_y_values.sum()
        hist_x_values = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        hist_y_values = hist_y_values / histogram_sum if histogram_sum != 0 else hist_y_values

        # Create the plotdata.PlottableData instances for this group
        row[_column_name] = []
        row[_column_name].append(plotdata.BarData(
            x_values=hist_x_values,
            y_values=hist_y_values,
            x_label=self.analyzer.column_to_properties[column_name].label \
                if column_name in self.analyzer.column_to_properties else clean_column_name(column_name),
            alpha=self.analyzer.main_alpha,
            extra_kwargs=dict(
                width=self.analyzer.bar_width_fraction * (bin_edges[1] - bin_edges[0]))))
        if self.analyzer.secondary_alpha > 0:
            y_min, y_max = hist_y_values.min(), hist_y_values.max()
            row[_column_name].append(plotdata.ScatterData(
                x_values=[row[f"{column_name}_avg"]],
                y_values=[0.5 * (y_min + y_max)],
                marker_size=4 * self.analyzer.main_marker_size,
                alpha=self.analyzer.secondary_alpha))
            if self.analyzer.show_x_std:
                row[_column_name].append(plotdata.ErrorLines(
                    x_values=[row[f"{column_name}_avg"]],
                    y_values=[0.5 * (y_min + y_max)],
                    marker_size=0,
                    alpha=self.analyzer.secondary_alpha,
                    err_neg_values=[row[f"{column_name}_std"]],
                    err_pos_values=[row[f"{column_name}_std"]],
                    line_width=self.analyzer.secondary_line_width,
                    vertical=False))


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
            self, column_selection, render_mode,
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
            column_selection=column_selection, render_mode=render_mode,
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
            column_kwargs["global_x_label"] = x_column_properties.label
        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = y_column_properties.label

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

    def get_output_pdf_path(self, column_selection, group_by, output_plot_dir, render_mode):
        return os.path.join(
            output_plot_dir,
            f"{self.__class__.__name__}_"
            f"{','.join(column_selection)}{'_groupby-' + group_by if group_by else ''}_{render_mode}.pdf")

    def build_summary_atable(self, full_df, target_columns, group_by, include_all_group):
        return TwoNumericSummary(analyzer=self, full_df=full_df,
                                 target_columns=target_columns, group_by=group_by,
                                 include_all_group=include_all_group)


class TwoNumericSummary(ScalarNumericSummary):
    """Summary table used in TwoNumericAnalyzer.

    For this class, target_columns must be a list of tuples, each tuple containing two column name,
    corresponding to x and y, respectively. Scalar analysis is provided on each column individually,
    as well as basic correlation metrics for each pair of columns.
    """

    def __init__(self, analyzer, full_df, target_columns, group_by, include_all_group):
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_name and render_mode.
        AnalyzerSummary.__init__(
            self=self, analyzer=analyzer, full_df=full_df,
            target_columns=target_columns, group_by=group_by,
            include_all_group=include_all_group)

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

                # Compute the global dynamic range of all input samples (before grouping)
                self.column_to_xmin_xmax[column_name] = scipy.stats.describe(full_df[column_name].values).minmax

            self.add_twoscalar_description_columns(column_names=x_y_names)

        self.move_render_columns_back()

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
        row[f"{x_column_name}_{y_column_name}_pearson_correlation"], \
        row[f"{x_column_name}_{y_column_name}_pearson_correlation_pvalue"] = \
            scipy.stats.pearsonr(self.reference_df[x_column_name], self.reference_df[y_column_name])
        row[f"{x_column_name}_{y_column_name}_spearman_correlation"], \
        row[f"{x_column_name}_{y_column_name}_spearman_correlation_pvalue"] = \
            scipy.stats.spearmanr(self.reference_df[x_column_name], self.reference_df[y_column_name])

        lr_results = scipy.stats.linregress(self.reference_df[x_column_name], self.reference_df[y_column_name])
        row[f"{x_column_name}_{y_column_name}_linear_lse_slope"] = lr_results.slope
        row[f"{x_column_name}_{y_column_name}_linear_lse_intercept"] = lr_results.intercept

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
            # Line plots are sorted by x values
            x_column_series, y_column_series = zip(*sorted(zip(
                x_column_series.values, y_column_series.values)))
            plds_this_case.append(plotdata.LineData(
                x_values=x_column_series,
                y_values=y_column_series,
                alpha=self.analyzer.secondary_alpha,
                marker_size=self.analyzer.main_marker_size - 1))
        else:
            raise SyntaxError(f"Invalid render mode {repr(render_mode)} not within the "
                              f"supported ones for {self.analyzer.__class__.__name__} "
                              f"({repr(self.analyzer.valid_render_modes)}")

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
               # Dynamic arguments with every call
               output_plot_dir=None,
               group_by=None, column_to_properties=None,
               # Arguments normalized by the @enb.aanalysis.AAnalyzer.normalize_parameters,
               # in turn manageable through .ini configuration files via the
               # @enb.config.aini.managed_attributes decorator.
               selected_render_modes=None, show_global=None, show_count=True, plot_title=None,
               # Rendering options, directly passed to plotdata.render_plds_by_group
               **render_kwargs):
        combined_df = full_df.copy()
        self.column_name_to_keys = dict()

        # Keys are combined before analyzing. This allows to compute just once the key_to_x dictionary shared
        # across all groups.
        for column_name in target_columns:
            if self.combine_keys_callable:
                combined_df[f"__{column_name}_combined"] = combined_df[column_name].apply(self.combine_keys_callable)
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
                              column_to_properties=column_to_properties,
                              selected_render_modes=selected_render_modes,
                              show_global=show_global, show_count=show_count, plot_title=plot_title,
                              **render_kwargs)

    def update_render_kwargs_one_case(
            self, column_selection, render_mode,
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
            column_selection=column_selection, render_mode=render_mode,
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

    def build_summary_atable(self, full_df, target_columns, group_by, include_all_group):
        return DictNumericSummary(
            analyzer=self, full_df=full_df, target_columns=target_columns,
            group_by=group_by, include_all_group=include_all_group)


class DictNumericSummary(AnalyzerSummary):
    """Summary table for the DictNumericAnalyzer.
    """

    def __init__(self, analyzer, full_df, target_columns, group_by, include_all_group):
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_name and render_mode.
        AnalyzerSummary.__init__(
            self=self, analyzer=analyzer, full_df=full_df,
            target_columns=target_columns, group_by=group_by,
            include_all_group=include_all_group)

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
        group_df = self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        if render_mode not in self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        # Only one mode is supported in this version of enb
        assert render_mode == "line"

        row[_column_name] = []

        x_values = []
        avg_values = []
        std_values = []
        for x, k in enumerate(self.analyzer.column_name_to_keys[column_name]):
            values = group_df[f"__{column_name}_combined"].apply(lambda d: d[k] if k in d else None).dropna()
            if len(values) > 0:
                x_values.append(x)
                avg_values.append(values.mean())
                std_values.append(values.std())
            if self.analyzer.show_individual_samples:
                row[_column_name].append(enb.plotdata.ScatterData(x_values=[x] * len(values),
                                                                  y_values=values.values,
                                                                  alpha=self.analyzer.secondary_alpha))
        if render_mode == "line":
            row[_column_name].append(enb.plotdata.LineData(
                x_values=x_values, y_values=avg_values, alpha=self.analyzer.main_alpha))
            if self.analyzer.show_y_std:
                row[_column_name].append(enb.plotdata.ErrorLines(
                    x_values=x_values, y_values=avg_values,
                    err_neg_values=std_values, err_pos_values=std_values,
                    alpha=self.analyzer.secondary_alpha,
                    vertical=True))
        else:
            raise ValueError(f"Unexpected render mode {render_mode} for {self.__class__.__name__}")


class OldAnalyzer:
    @deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                            current_version=enb.config.ini.get_key("enb", "version"),
                            details="A new set of analyzer classes has been defined. "
                                    "See enb.aanalysis.Analyzer for further information.")
    def analyze_df(self, full_df, target_columns, output_plot_dir, output_csv_file=None,
                   column_to_properties=None, group_by=None, group_name_order=None,
                   show_global=True, show_count=True, version_name=None,
                   adjust_height=False):
        """
        Analyze a :class:`pandas.DataFrame` instance, producing plots and/or analysis files.
        
        :param adjust_height:
        :param full_df: full DataFrame instance with data to be plotted and/or analyzed
        :param target_columns: list of columns to be analyzed. Typically a list of column names, although each subclass may 
         redefine the accepted format (e.g., pairs of column names)
        :param output_plot_dir: path of the directory where the plot/plots is/are to be saved.
        :param output_csv_file: If not None, path of the csv file where basic analysis results are stored.
          The contents of the file are subclass-defined.
        :param column_to_properties: dictionary with ColumnProperties entries. ATable instances provide it
          in the :attr:`column_to_properties` attribute, :class:`Experiment` instances can also use the
          :attr:`joined_column_to_properties` attribute to obtain both the dataset and experiment's
          columns.
        :param group_by: if not None, the name of the column to be used for grouping.
        :param group_name_order: if not None, and if group_by is not None,
          it must be the list of group names (values of the group_by) in the order that they are to be displayed.
          If None, group names are sorted alphabetically (case insensitive).
        :param show_count: determines whether the number of element per group should be shown in the group label
        :param version_name: if not None, a string identifying the file version that produced full_df.
        """
        raise NotImplementedError(self)


class ScalarDistributionAnalyzer(OldAnalyzer):
    """Automatic analysis and report of scalar data in pandas' DataFrames
    """
    # Number of bars to display in the histogram diagrams
    hist_bin_count = 50
    # Fraction in 0,1 of the bar width for histogram
    bar_width_fraction = 1
    # Margin height in heights of each individual histogram
    histogram_margin = 0.2
    # If True, the number of items in each group is displayed next to their names
    show_count = True

    # Default element opacity
    bar_alpha = 0.5
    secondary_alpha = 0.6

    semilog_y_min_bound = 1e-5

    @deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                            current_version=enb.config.ini.get_key("enb", "version"),
                            details="A new set of analyzer classes has been defined. "
                                    "See enb.aanalysis.Analyzer for further information.")
    def analyze_df(self, full_df, target_columns, global_y_label=None,
                   output_plot_dir=None, output_csv_file=None, column_to_properties=None,
                   group_by=None, group_name_order=None, show_global=True, show_count=True, version_name=None,
                   y_max=None, y_labels_by_group_name=None, **kwargs):
        """Perform an analysis of target_columns, grouping as specified.

        :param output_csv_file: path where the CSV report is stored
        :param output_plot_dir: path where the distribution plots are stored. Defaults to options.plotdir
        :param target_columns: list of column names for which an analysis is to be performed.
          A single string is also accepted (as a single column name).
        :param column_to_properties: if not None, a dict indexed by column name (as given
          in the column parameter of the @atable.column_function decorator), entries being
          an atable.ColumnProperties instance
        :param group_by: if not None, analysis is performed after grouping by that column name
        :param show_global: if True, distribution for all entries (without grouping) is also shown
        :param version_name: if not None, the version name is prepended to the x axis' label
        :param global_y_label: shared y-axis label
        """
        output_plot_dir = options.plot_dir if output_plot_dir is None else output_plot_dir
        target_columns = [target_columns] if isinstance(target_columns, str) else target_columns
        column_to_properties = collections.defaultdict(
            lambda: enb.atable.ColumnProperties(name="unknown")) \
            if column_to_properties is None else column_to_properties
        min_max_by_column = get_scalar_min_max_by_column(
            df=full_df, target_columns=target_columns, column_to_properties=column_to_properties)
        min_max_by_column = dict(min_max_by_column)

        pooler_suffix_tuples = [(pd.DataFrame.min, "min"), (pd.DataFrame.max, "max"),
                                (pd.DataFrame.mean, "avg"), (pd.DataFrame.std, "std")]
        analysis_df = pd.DataFrame(columns=["count"] + list(
            itertools.chain([f"{column}_{suffix}"
                             for column in target_columns
                             for _, suffix in pooler_suffix_tuples])))

        # Fill analysis_df and gather plotdata.PlottableData instances
        label_column_to_pds = {}
        lengths_by_group_name = {}
        if group_by is not None:
            assert isinstance(group_by, str), repr(group_by)
            for group_name, group_df in full_df.groupby(group_by):
                group_name = str(group_name) if isinstance(group_name, bool) else group_name

                pool_scalar_into_analysis_df(analysis_df=analysis_df, analysis_label=group_name, data_df=group_df,
                                             pooler_suffix_tuples=pooler_suffix_tuples, columns=target_columns)
                analysis_df.at[group_name, "count"] = len(group_df)
                label_column_to_pds.update({
                    (group_name, column): scalar_column_to_pds(
                        column=column, properties=column_to_properties[column],
                        df=group_df, min_max_by_column=min_max_by_column,
                        hist_bin_count=self.hist_bin_count, bar_width_fraction=self.bar_width_fraction,
                        semilogy_min_y=self.semilog_y_min_bound,
                        bar_alpha=self.bar_alpha, secondary_alpha=self.secondary_alpha)
                    for column in target_columns})
                lengths_by_group_name[group_name] = len(group_df)

        if show_global or group_by is None:
            analysis_df.at["all", "count"] = len(full_df)
            pool_scalar_into_analysis_df(analysis_df=analysis_df, analysis_label="all", data_df=full_df,
                                         pooler_suffix_tuples=pooler_suffix_tuples, columns=target_columns)
            label_column_to_pds.update({
                ("all", column): scalar_column_to_pds(
                    column=column, properties=column_to_properties[column],
                    df=full_df, min_max_by_column=min_max_by_column,
                    hist_bin_count=self.hist_bin_count, bar_width_fraction=self.bar_width_fraction,
                    semilogy_min_y=self.semilog_y_min_bound,
                    bar_alpha=self.bar_alpha, secondary_alpha=self.secondary_alpha)
                for column in target_columns})
            lengths_by_group_name["all"] = len(full_df)
        if output_csv_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_csv_file)), exist_ok=True)
            analysis_df.to_csv(output_csv_file)

        expected_return_ids = []
        for column_name in target_columns:
            pds_by_group_name = {k[0]: v for k, v in label_column_to_pds.items() if k[1] == column_name}

            if column_name in column_to_properties and column_to_properties[column_name].label:
                x_label = column_to_properties[column_name].label
            else:
                x_label = clean_column_name(column_name)
            if version_name and version_name.strip():
                x_label = f"{version_name.strip()} {x_label}"

            hist_bin_width = None
            if column_name in column_to_properties and column_to_properties[column_name].hist_bin_width is not None:
                hist_bin_width = column_to_properties[column_name].hist_bin_width
            if hist_bin_width is None:
                try:
                    hist_bin_width = ((min_max_by_column[column_name][1] - min_max_by_column[column_name][0])
                                      / self.hist_bin_count)
                except TypeError:
                    hist_bin_width = 1 / self.hist_bin_count
            y_min = 0 if not column_name in column_to_properties \
                         or not column_to_properties[column_name].semilog_y else self.semilog_y_min_bound

            # Compute the maximum height of any plottable element
            if y_max is None:
                y_max = float("-inf")
                for pds in pds_by_group_name.values():
                    for pld in pds:
                        if not isinstance(pld, plotdata.BarData):
                            continue
                        y_max = max(y_max, max(pld.y_values))
                y_max = y_max if y_max != float("-inf") else None

            # If that height is not 1 (e.g., it is not a relative frequency),
            # some elements may need adjustment
            if y_max != 1:
                for pds in pds_by_group_name.values():
                    for pld in pds:
                        if isinstance(pld, plotdata.ErrorLines):
                            pld.y_values = [0.5 * (y_max - y_min)]

            try:
                column_properties = column_to_properties[column_name]
                x_min, x_max = column_properties.plot_min, column_properties.plot_max
            except KeyError:
                x_min, x_max = None, None

            if y_labels_by_group_name is None:
                y_labels_by_group_name = {
                    group: f"{group} ({length})" if show_count else f"{group}"
                    for group, length in lengths_by_group_name.items()}
            elif show_count:
                for group, length in lengths_by_group_name.items():
                    try:
                        affix = f" ({length})"
                        if not y_labels_by_group_name[group].endswith(affix):
                            y_labels_by_group_name[group] += f" ({length})"
                    except KeyError:
                        y_labels_by_group_name[group] = f"{group} ({length})" if show_count else f"{group}"

            group_str = f"_groupby-{group_by}" if group_by is not None else ""

            expected_return_ids.append(
                parallel_render_plds_by_group.remote(
                    pds_by_group_name=ray.put(pds_by_group_name),
                    output_plot_path=ray.put(os.path.join(output_plot_dir,
                                                          f"distribution{group_str}_{column_name}.pdf")),
                    column_properties=ray.put(column_to_properties[column_name]
                                              if column_name in column_to_properties else None),
                    horizontal_margin=ray.put(hist_bin_width),
                    global_x_label=ray.put(x_label),
                    global_y_label=ray.put(r"Distribution, average and $\pm 1\sigma$"
                                           if global_y_label is None else global_y_label),
                    y_labels_by_group_name=ray.put(y_labels_by_group_name),
                    x_min=ray.put(x_min), x_max=ray.put(x_max),
                    y_min=ray.put(y_min), y_max=ray.put(y_max),
                    semilog_y_min_bound=ray.put(self.semilog_y_min_bound),
                    group_name_order=ray.put(group_name_order)))

        ray.get(expected_return_ids)

        return analysis_df


@deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                        current_version=enb.config.ini.get_key("enb", "version"),
                        details="A new set of analyzer classes has been defined. "
                                "See enb.aanalysis.Analyzer for further information.")
def scalar_column_to_pds(column, properties, df, min_max_by_column, hist_bin_count, bar_width_fraction,
                         semilogy_min_y, bar_alpha=0.5, secondary_alpha=0.75, ):
    """Add the pooled values and get a list of PlottableData instances with the
    relative distribution, mean and error bars.
    """
    column_df = df[column]
    range = tuple(min_max_by_column[column])
    if range == (None, None):
        range = None
    if range is not None:
        if range[0] == range[1]:
            range = (range[0], range[0] + 1)

    hist_y_values, bin_edges = np.histogram(
        column_df.values, bins=hist_bin_count, range=range, density=False)
    hist_y_values = hist_y_values / len(column_df) if len(column_df) > 0 else hist_y_values

    if abs(sum(hist_y_values) - 1) > 1e-10:
        if math.isinf(df[column].max()) or math.isinf(df[column].min()):
            enb.log.warn(f"Not all samples included in the scalar distribution for {column} "
                         f"(used {100 * (sum(hist_y_values)):.1f}% of the samples)."
                         f"Note that infinite values are not accounted for, and the plot_min "
                         f"and plot_max column properties affect this range.")
        else:
            enb.log.warn(f"Not all samples included in the scalar distribution for {column} "
                         f"(used {100 * (sum(hist_y_values)):.1f}% of the samples)."
                         f"Note that plot_min and plot_max column properties might be affecting this range.")

    hist_y_values = hist_y_values / hist_y_values.sum() \
        if hist_y_values.sum() > 0 and len(hist_y_values) > 0 and np.isfinite(
        hist_y_values / hist_y_values.sum()).all() \
        else hist_y_values

    x_label = column if (properties is None or not properties.label) else properties.label

    hist_x_values = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    plot_data = plotdata.BarData(x_values=hist_x_values,
                                 y_values=hist_y_values,
                                 x_label=x_label,
                                 y_label="",
                                 alpha=bar_alpha,
                                 extra_kwargs=dict(
                                     width=bar_width_fraction
                                           * (bin_edges[1] - bin_edges[0])))

    average_point_position = 0.5
    if properties is not None and properties.semilog_y:
        average_point_position = 10 ** (0.5 * (math.log10(semilogy_min_y) + math.log10(1)))
    error_lines = plotdata.ErrorLines(
        x_values=[column_df.mean()],
        y_values=[average_point_position],
        marker_size=5,
        alpha=secondary_alpha,
        err_neg_values=[column_df.std()], err_pos_values=[column_df.std()],
        line_width=2,
        vertical=False)

    return [plot_data, error_lines]


@deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                        current_version=enb.config.ini.get_key("enb", "version"),
                        details="A new set of analyzer classes has been defined. "
                                "See enb.aanalysis.Analyzer for further information.")
def pool_scalar_into_analysis_df(analysis_df, analysis_label, data_df, pooler_suffix_tuples, columns):
    """Pull columns into analysis using the poolers in pooler_suffix_tuples, with the specified
    suffixes.
    """
    analysis_label = analysis_label if not isinstance(analysis_label, bool) else str(analysis_label)

    for column in columns:
        for pool_fun, suffix in pooler_suffix_tuples:
            analysis_df.at[analysis_label, f"{column}_{suffix}"] = pool_fun(data_df[column])


@deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                        current_version=enb.config.ini.get_key("enb", "version"),
                        details="A new set of analyzer classes has been defined. "
                                "See enb.aanalysis.Analyzer for further information.")
def get_scalar_min_max_by_column(df, target_columns, column_to_properties):
    """Get a dictionary indexed by column name with minimum and maximum values.
    (useful e.g., for normalized processing of subgroups).

    If column to properties is set, for a column, the minimum and maximum are taken from them.
    None limits are taken from the minimum and maximum values that are not infinite.

    """
    min_max_by_column = {}
    for column in target_columns:
        if column_to_properties and column in column_to_properties:
            min_max_by_column[column] = [column_to_properties[column].plot_min,
                                         column_to_properties[column].plot_max]
        else:
            min_max_by_column[column] = [None, None]

        for i in range(2):
            if min_max_by_column[column][i] is None:
                try:
                    min_max_by_column[column][i] = df[column].min() if i == 0 else df[column].max()
                    if math.isinf(min_max_by_column[column][i]) or math.isnan(min_max_by_column[column][i]):
                        try:
                            min_max_by_column[column][i] = \
                                min(df[column].dropna()) if i == 0 else max(df[column].dropna())
                        except ValueError:
                            min_max_by_column[column][i] = 0
                except TypeError as ex:
                    if not column_to_properties or column not in column_to_properties:
                        enb.logger.debug(f"Cannot calculate min,max for column {repr(column)}. Setting to None.")
                    min_max_by_column[column][0] = None

        if min_max_by_column[column][1] is not None and min_max_by_column[column][1] > 1:
            if column not in column_to_properties or column_to_properties[column].plot_min is None:
                min_max_by_column[column][0] = math.floor(min_max_by_column[column][0])
            if column not in column_to_properties or column_to_properties[column].plot_max is None:
                min_max_by_column[column][1] = math.ceil(min_max_by_column[column][1])

    return min_max_by_column


@deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                        current_version=enb.config.ini.get_key("enb", "version"),
                        details="A new set of analyzer classes has been defined. "
                                "See enb.aanalysis.Analyzer for further information.")
def histogram_overlap_column_to_pds(df, column, column_properties=None, line_alpha=0.2, line_width=0.5):
    pld_list = []
    for d in df[column]:
        x_values = sorted(d.keys())
        y_values = [d[x] for x in x_values]
        pld_list.append(plotdata.LineData(
            x_values=x_values, y_values=y_values, alpha=line_alpha,
            extra_kwargs=dict(lw=line_width)))
    return pld_list


class HistogramDistributionAnalyzer(OldAnalyzer):
    """Analyze DFs with vector mappings, i.e., dictionary-like instances from
    value to weights (e.g., counts).
    """
    alpha_global = 0.5
    alpha_individual = 0.25

    # Default histogram bin width
    histogram_bin_width = 1

    # Fraction in 0,1 of the bar width for histogram
    bar_width_fraction = 1
    # Margin height in heights of each individual histogram
    histogram_margin = 0.3

    subdivision_count = 10

    hist_min = 0
    hist_max = 1
    semilog_y_min_bound = 1e-5

    color_sequence = ["blue", "orange", "r", "g", "magenta", "yellow"]

    @deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                            current_version=enb.config.ini.get_key("enb", "version"),
                            details="A new set of analyzer classes has been defined. "
                                    "See enb.aanalysis.Analyzer for further information.")
    def analyze_df(self, full_df, target_columns, output_plot_dir=None, output_csv_file=None,
                   column_to_properties=None,
                   group_by=None, group_name_order=None, show_global=True, show_count=True, version_name=None,
                   adjust_height=False):
        """Analyze a column, where each cell contains a real to real mapping.

        :param adjust_height:
        :param full_df: full df from which the column is to be extracted
        :param target_columns: list of column names containing tensor (dictionary) data
        :param output_plot_dir: path of the directory where the plot is to be saved
        :param output_csv_file: path of the csv file where basic analysis results are stored
        :param column_to_properties: dictionary with ColumnProperties entries
        :param group_by: if not None, the name of the column to be used for grouping
        :param group_name_order: if not None, and if group_by is not None,
          it must be the list of group names (values of the group_by) in the order that they are to be displayed.
          If None, group names are sorted alphabetically (case insensitive).
        :param show_count: determines whether the number of element per group should be shown in the group label
        :param version_name: if not None, a string identifying the file version that produced full_df.
        """
        output_plot_dir = options.plot_dir if output_plot_dir is None else output_plot_dir
        full_df = pd.DataFrame(full_df)
        column_to_properties = collections.defaultdict(
            lambda: enb.atable.ColumnProperties("unknown")) \
            if column_to_properties is None else column_to_properties

        return_ids = []
        for column_name in target_columns:
            # Gather plottable data
            column_properties = column_to_properties[column_name] if column_name in column_to_properties else None
            assert column_properties is not None, (self, column_name)
            assert column_properties.has_dict_values, (column_name, column_properties)
            column_dicts = get_histogram_dicts(df=full_df, column=column_name)
            global_x_min = min(min(d.keys()) for d in column_dicts)
            global_x_max = max(max(d.keys()) for d in column_dicts)

            pds_by_group_name = collections.defaultdict(list)
            lengths_by_group = dict()

            histogram_bin_width = column_properties.hist_bin_width \
                if column_properties.hist_bin_width is not None else self.histogram_bin_width

            if group_by is not None:
                for group_label, group_df in sorted(full_df.groupby(by=group_by)):
                    pds_by_group_name[group_label] = histogram_dist_column_to_pds(
                        df=group_df, column=column_name, bar_width_fraction=self.bar_width_fraction,
                        global_xmin_xmax=(global_x_min, global_x_max),
                        column_properties=column_properties,
                        individual_pd_alpha=self.alpha_individual, global_pd_alpha=self.alpha_global,
                        bin_width=histogram_bin_width)
                    lengths_by_group[group_label] = len(group_df)
            if show_global or not group_by:
                pds_by_group_name["all"] = histogram_dist_column_to_pds(
                    df=full_df, column=column_name, bar_width_fraction=self.bar_width_fraction,
                    global_xmin_xmax=(global_x_min, global_x_max),
                    column_properties=column_properties,
                    individual_pd_alpha=self.alpha_individual, global_pd_alpha=self.alpha_global,
                    bin_width=histogram_bin_width)
                lengths_by_group["all"] = len(full_df)

            # Make plots in parallel
            output_plot_path = os.path.join(output_plot_dir, f"histogram_{column_name}.pdf")
            labels_by_group = {
                group: f"{group} (n={length})" if show_global else f"{group}"
                for group, length in lengths_by_group.items()
            }
            x_label = column_to_properties[column_name].label if column_name in column_to_properties else None
            x_label = clean_column_name(column_name) if x_label is None else x_label
            if version_name:
                x_label = f"{version_name} {x_label}"
            y_label = column_to_properties[column_name].hist_label if column_name in column_to_properties else None
            y_label = "Relative frequency" if y_label is None else y_label

            y_min = column_to_properties[column_name].hist_min if column_name in column_to_properties else None
            y_min = self.hist_min if y_min is None else y_min
            if y_min is not None and column_to_properties[column_name].semilog_y:
                y_min = max(y_min, self.semilog_y_min_bound)
            y_max = column_to_properties[column_name].hist_max if column_name in column_to_properties else None
            y_max = self.hist_max if y_max is None else y_max

            try:
                column_properties = column_to_properties[column_name]
                x_min, x_max = column_properties.plot_min, column_properties.plot_max
            except KeyError:
                x_min, x_max = None, None

            return_ids.append(parallel_render_plds_by_group.remote(
                pds_by_group_name=ray.put(pds_by_group_name),
                output_plot_path=ray.put(output_plot_path),
                horizontal_margin=ray.put(histogram_bin_width),
                column_properties=ray.put(column_properties),
                global_x_label=ray.put(x_label),
                global_y_label=ray.put(y_label),
                x_min=ray.put(x_min), x_max=ray.put(x_max),
                y_min=ray.put(y_min), y_max=ray.put(y_max),
                y_labels_by_group_name=ray.put(labels_by_group),
                group_name_order=ray.put(group_name_order)))

        return ray.get(return_ids)


@deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                        current_version=enb.config.ini.get_key("enb", "version"),
                        details="A new set of analyzer classes has been defined. "
                                "See enb.aanalysis.Analyzer for further information.")
def histogram_dist_column_to_pds(df, column, global_xmin_xmax,
                                 bar_width_fraction,
                                 column_properties=None, plot_individual=False,
                                 bin_width=1,
                                 individual_pd_alpha=0.2, global_pd_alpha=0.5):
    """Return a list of PlotData instances graphically an histogram of the contents
    column.

    Each entry dict is normalized so that the maximum y value is 1. One StepData
    instance is produced per row in df.

    :param df: df with the data to analyze
    :param column: column to be analyzed
    :param bin_width: width of the histogram bins
    """
    produced_pds = []
    parsed_dicts = get_histogram_dicts(df=df, column=column)

    hist_bin_count = 1 + math.ceil((global_xmin_xmax[1] - global_xmin_xmax[0]) / bin_width)

    hist_range = (global_xmin_xmax[0] - bin_width / 2, global_xmin_xmax[1] + bin_width / 2)

    last_bin_edges = None
    hist_x_values = None
    hist_y_lists = None
    global_histogram = collections.defaultdict(float)

    for column_index, column_dict in enumerate(parsed_dicts):
        column_value_sum = sum(column_dict.values())

        hist_y_values, bin_edges = np.histogram(
            list(column_dict.keys()), weights=list(column_dict.values()),
            range=hist_range, density=False, bins=hist_bin_count)
        assert last_bin_edges is None or np.all(bin_edges == last_bin_edges)
        last_bin_edges = bin_edges

        y_normalization = sum(hist_y_values)
        assert abs(y_normalization - column_value_sum) < 1e-10, (y_normalization, column_value_sum)

        hist_y_values = [y / y_normalization for y in hist_y_values]
        hist_x_values = bin_edges[:-1] if hist_x_values is None else hist_x_values
        if plot_individual:
            produced_pds.append(plotdata.StepData(
                x_values=hist_x_values, y_values=hist_y_values,
                alpha=individual_pd_alpha,
                extra_kwargs=dict(lw=0.75)))

        if hist_y_lists is None:
            hist_y_lists = [[] for _ in range(len(hist_x_values))]
        for i, y in enumerate(hist_y_values):
            hist_y_lists[i].append(y)

        for k, v in column_dict.items():
            global_histogram[k] += v / column_value_sum

    assert all(len(y_list) == len(parsed_dicts) for y_list in hist_y_lists)

    # Generate global histogram (each image weighted equally)
    hist_y_values, bin_edges = np.histogram(
        list(global_histogram.keys()),
        weights=list(global_histogram.values()),
        range=hist_range, density=False, bins=hist_bin_count)
    hist_x_values = [x + bin_width / 2 for x in bin_edges[:-1]]
    assert last_bin_edges is None or np.all(bin_edges == last_bin_edges)
    y_normalization = sum(hist_y_values)
    hist_y_values = [y / y_normalization for y in hist_y_values]
    produced_pds.append(plotdata.BarData(
        x_values=hist_x_values, y_values=hist_y_values,
        alpha=global_pd_alpha,
        extra_kwargs=dict(width=bar_width_fraction * (bin_edges[1] - bin_edges[0]))))

    # Add vertical error bars
    global_hist_avg = [np.array(l).mean() for l in hist_y_lists]
    global_hist_std = [np.array(l).std() for l in hist_y_lists]
    produced_pds.append(plotdata.ErrorLines(x_values=hist_x_values, y_values=global_hist_avg,
                                            err_neg_values=global_hist_std,
                                            err_pos_values=global_hist_std,
                                            marker_size=0.5,
                                            alpha=individual_pd_alpha,
                                            vertical=True,
                                            line_width=0.5))

    return produced_pds


class OverlappedHistogramAnalyzer(HistogramDistributionAnalyzer):
    """Plot multiple overlapped histograms (e.g. dicts from float to float)
    per group, one per row.
    """
    line_alpha = 0.3
    line_width = 0.5

    @deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                            current_version=enb.config.ini.get_key("enb", "version"),
                            details="A new set of analyzer classes has been defined. "
                                    "See enb.aanalysis.Analyzer for further information.")
    def analyze_df(self, full_df, target_columns, output_plot_dir=None, output_csv_file=None,
                   column_to_properties=None,
                   group_by=None, group_name_order=None, show_global=True, show_count=True, version_name=None,
                   adjust_height=False):
        output_plot_dir = options.plot_dir if output_plot_dir is None else output_plot_dir
        result_ids = []
        for column_name in target_columns:
            if column_name in column_to_properties:
                x_label = column_to_properties[column_name].label
                y_label = column_to_properties[column_name].hist_label
            else:
                parts = column_name.split("_to_")
                x_label, y_label = None, None
                if len(parts) == 2:
                    x_label = clean_column_name(parts[0])
                    y_label = clean_column_name(parts[1])
            if version_name:
                x_label = f"{version_name} {x_label}"
                y_label = f"{version_name} {y_label}"

            properties = column_to_properties[column_name] if column_name in column_to_properties else None

            output_plot_path = os.path.join(output_plot_dir, f"overlapped_histogram_{column_name}.pdf")

            pds_by_group = {}
            lens_by_group = {}

            def process_group(name, df):
                pds_by_group[name] = histogram_overlap_column_to_pds(
                    df=df, column=column_name, column_properties=properties,
                    line_alpha=self.line_alpha, line_width=self.line_width)
                lens_by_group[name] = len(df)

            if group_by:
                for group_name, group_df in sorted(full_df.groupby(group_by)):
                    process_group(name=group_name, df=group_df)
            if not pds_by_group or len(pds_by_group) > 1:
                process_group(name="all", df=full_df)

            y_labels_by_group_name = {group_name: f"{group_name} ({lens_by_group[group_name]})"
                                      for group_name in pds_by_group.keys()}

            y_min = column_to_properties[column_name].hist_min if column_name in column_to_properties else None
            y_min = self.hist_min if y_min is None else y_min
            if y_min is not None and column_to_properties[column_name].semilog_y:
                y_min = max(y_min, self.semilog_y_min_bound)
            y_max = column_to_properties[column_name].hist_max if column_name in column_to_properties else None
            y_max = self.hist_max if y_max is None else y_max

            try:
                column_properties = column_to_properties[column_name]
                x_min, x_max = column_properties.plot_min, column_properties.plot_max
            except KeyError:
                x_min, x_max = None, None

            result_ids.append(parallel_render_plds_by_group.remote(
                pds_by_group_name=ray.put(pds_by_group),
                output_plot_path=ray.put(output_plot_path),
                column_properties=ray.put(properties), horizontal_margin=ray.put(0),
                global_x_label=ray.put(x_label), y_labels_by_group_name=ray.put(y_labels_by_group_name),
                global_y_label=ray.put(y_label), color_by_group_name=ray.put(None),
                x_min=ray.put(x_min), x_max=ray.put(x_max),
                y_min=ray.put(y_min), y_max=ray.put(y_max),
                group_name_order=ray.put(group_name_order)))

        ray.get(result_ids, timeout=0)
        if options.verbose > 1:
            "TODO: fill csv and write to output_csv_file"


class TwoColumnScatterAnalyzer(OldAnalyzer):
    marker_size = 5
    alpha = 0.5

    @deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                            current_version=enb.config.ini.get_key("enb", "version"),
                            details="A new set of analyzer classes has been defined. "
                                    "See enb.aanalysis.Analyzer for further information.")
    def analyze_df(self, full_df, target_columns, output_plot_dir=None, output_csv_file=None,
                   column_to_properties=None,
                   group_by=None, group_name_order=None, show_global=True, show_count=True, version_name=None,
                   adjust_height=False, show_individual=True, legend_column_count=None):
        """
        :param adjust_height:
        :param group_name_order:
        :param show_count:
        :param target_columns: must be a list of tuple-like instances, each with two elements.
          The first element is the name of the column to use for the x axis,
          the second element is the name of the column for the y axis.
        :param group_by: if not None, it must be either a string representing a column
          or a list of TaskFamily instances.
        """
        legend_column_count = legend_column_count if legend_column_count is not None else options.legend_column_count
        output_plot_dir = options.plot_dir if output_plot_dir is None else output_plot_dir
        selected_column_pairs = []
        for column_x, column_y in target_columns:
            if options.columns:
                if column_x not in options.columns or column_y not in options.columns:
                    if options.verbose > 2:
                        print(f"[S]kipping ({column_x}, {column_y} because options.columns={options.columns}")
                    continue
            selected_column_pairs.append((column_x, column_y))

        expected_returns = []
        for column_x, column_y in selected_column_pairs:
            pds_by_group = collections.defaultdict(list)
            x_label = column_to_properties[
                column_x].label if column_to_properties is not None and column_x in column_to_properties else None
            x_label = clean_column_name(column_x) if x_label is None else x_label
            y_label = column_to_properties[
                column_y].label if column_to_properties is not None and column_y in column_to_properties else None
            y_label = clean_column_name(column_y) if y_label is None else y_label
            if group_by is not None:
                try:
                    assert all(issubclass(t, TaskFamily) for t in group_by), group_by
                    group_column = "task_name"
                    group_by_families = True
                except TypeError:
                    group_column = group_by
                    group_by_families = False

                for i, (group_label, group_df) in enumerate(full_df.groupby(by=group_column)):
                    x_values, y_values = zip(*sorted(zip(
                        group_df[column_x].values, group_df[column_y].values)))
                    if not group_by_families:
                        label = group_label
                    else:
                        for family in group_by:
                            try:
                                label = family.name_to_label[group_label]
                                break
                            except KeyError:
                                pass
                        else:
                            raise ValueError(f"task name {group_label} not found in group_by={group_by}")

                    pds_by_group[group_label].append(
                        plotdata.ScatterData(
                            x_values=[sum(x_values) / len(x_values)],
                            y_values=[sum(y_values) / len(y_values)],
                            label=label,
                            extra_kwargs=dict(
                                marker=marker_cycle[i % len(marker_cycle)],
                                s=self.marker_size,
                                color=color_cycle[i % len(color_cycle)]),
                            alpha=min(self.alpha * 2, 0.65)))
                    pds_by_group[group_label][-1].marker_size = self.marker_size * 5
                    if show_individual:
                        pds_by_group[group_label].append(
                            plotdata.ScatterData(
                                x_values=x_values, y_values=y_values,
                                extra_kwargs=dict(
                                    marker=marker_cycle[i % len(marker_cycle)],
                                    color=color_cycle[i % len(color_cycle)],
                                    s=self.marker_size),
                                alpha=0.7 * self.alpha))

            if not pds_by_group or show_global:
                x_values, y_values = zip(*sorted(zip(
                    full_df[column_x].values, full_df[column_y].values)))
                pds_by_group["all"] = [plotdata.ScatterData(
                    x_values=x_values, y_values=y_values, alpha=self.alpha),
                    plotdata.ScatterData(x_values=[np.array(x_values).mean()],
                                         y_values=[np.array(y_values).mean()],
                                         alpha=self.alpha)]

            output_plot_path = os.path.join(output_plot_dir, f"twocolumns_scatter_{column_x}_VS_{column_y}.pdf")

            all_plds = [pld for pds in pds_by_group.values() for pld in pds]
            # for pld in all_plds:
            #     pld.alpha = self.alpha
            #     pld.marker_size = self.marker_size
            global_x_min = min(min(pld.x_values) for pld in all_plds)
            global_x_max = max(max(pld.x_values) for pld in all_plds)
            global_y_min = min(min(pld.y_values) for pld in all_plds)
            global_y_max = max(max(pld.y_values) for pld in all_plds)

            try:
                column_properties = column_to_properties[column_x]
                global_x_min, global_x_max = column_properties.plot_min, column_properties.plot_max
            except (KeyError, TypeError):
                pass

            global_y_min = global_y_min - 0.05 * (global_y_max - global_y_min) \
                if column_to_properties is None or not column_y in column_to_properties \
                   or column_to_properties[column_y].plot_min is None \
                else column_to_properties[column_y].plot_min

            global_y_max = global_y_max + 0.05 * (global_y_max - global_y_min) \
                if column_to_properties is None or not column_y in column_to_properties \
                   or column_to_properties[column_y].plot_max is None \
                else column_to_properties[column_y].plot_max

            pds_by_group_id = ray.put(pds_by_group)

            if global_x_max is None or global_x_min is None:
                horizontal_margin = 0
            else:
                horizontal_margin = 0.05 * (global_x_max - global_x_min)

            expected_returns.append(parallel_render_plds_by_group.remote(
                pds_by_group_name=pds_by_group_id,
                output_plot_path=ray.put(output_plot_path),
                column_properties=ray.put(
                    column_to_properties[column_x]
                    if column_to_properties is not None and column_x in column_to_properties else None),
                horizontal_margin=ray.put(horizontal_margin),
                y_min=ray.put(global_y_min),
                y_max=ray.put(global_y_max),
                global_x_label=ray.put(x_label), global_y_label=ray.put(y_label),
                combine_groups=ray.put(True),
                legend_column_count=ray.put(legend_column_count)))

        ray.wait(expected_returns)


class TwoColumnLineAnalyzer(OldAnalyzer):
    alpha = 0.5

    @deprecation.deprecated(deprecated_in="0.3.0", removed_in="1.0.0",
                            current_version=enb.config.ini.get_key("enb", "version"),
                            details="A new set of analyzer classes has been defined. "
                                    "See enb.aanalysis.Analyzer for further information.")
    def analyze_df(self, full_df, target_columns, group_by,
                   show_v_range_bar=False, show_h_range_bar=False,
                   show_v_std_bar=False, show_h_std_bar=False,
                   output_plot_dir=None, output_csv_file=None, column_to_properties=None,
                   group_name_order=None, show_global=True, show_count=True, version_name=None,
                   adjust_height=False, show_markers=False, marker_size=3,
                   task_column_name="task_name",
                   legend_column_count=None):
        """
        :param adjust_height:
        :param full_df: full pandas.DataFrame to be analyzed and plotted
        :param group_by: a list of TaskFamily instances. Note that this behavior
          differs from that of other Analyzers, which take a column name.
        :param task_column_name: if provided, the df is grouped by the elements
          of this column instead of "task_name", using the families provided
          to group_by
        :param target_columns: an iterable of either two column names or
          one or more tuple-like objects with two elements also being column names.
          The first column name gives the one to be used for the x axis,
          the second column for the y axis.
        :param output_plot_dir: directory where the produced plots are to
          be saved
        :param output_csv_file: if not None, a file path were analysis statistics
          are saved
        :param column_to_properties: a dictionary of atable.ColumnProperties
          indexed by their corresponding column name
        :param show_global: if group_by is not None, show_global determines
          whether the whole dataframe (regardless of the group_by column)
          is analyzed as well.
        :param group_name_order: ignored in this class, since group_by already
          provides an order.
        :param version_name: if not None, the version name is prepended to
          the X and Y labels of the plot (does not affect computation).
        :param show_markers: if True, markers are displayed in the Line plot
        :param marker_size: if show_markers is True, this parameters sets
          the displayed marker size
        """
        output_plot_dir = options.plot_dir if output_plot_dir is None else output_plot_dir
        legend_column_count = options.legend_column_count if legend_column_count is None else legend_column_count

        assert target_columns, "Target columns cannot be empty nor None"
        try:
            len(target_columns[0]) == 2
        except TypeError:
            target_columns = [target_columns]

        assert all(len(t) == 2 for t in target_columns), \
            "Entries in target columns must be 2-element tuple-like instances. " \
            f"(found {target_columns})"
        assert all(t[0] in full_df.columns and t[1] in full_df.columns for t in target_columns), \
            f"At least one column name in {target_columns} is not defined in " \
            f"full_df's columns ({full_df.columns}"

        data_point_count = None

        for column_name_x, column_name_y in target_columns:
            # Entries are lists of PlottableData instances
            plds_by_family_label = sortedcontainers.SortedDict()
            for i, family in enumerate(group_by):
                family_avg_x_y_values = []
                family_x_pos_values = []
                family_x_neg_values = []
                family_y_pos_values = []
                family_y_neg_values = []
                family_x_std_values = []
                family_y_std_values = []
                for task_name in family.task_names:
                    rows = full_df[full_df[task_column_name] == task_name]

                    # Sanity check on the number of rows
                    if data_point_count is None:
                        data_point_count = len(rows)
                    else:
                        assert data_point_count == len(rows), \
                            f"Previously found {data_point_count} data points per task, " \
                            f"but {task_name} in {family} has {len(rows)} data points."

                    # Check and discard infinities before calculation
                    x_data = np.array(rows[column_name_x].values)
                    y_data = np.array(rows[column_name_y].values)
                    mean_x = x_data.mean()
                    mean_y = y_data.mean()

                    if math.isinf(mean_x + mean_y):
                        finite_positions = [math.isfinite(x) and math.isfinite(y)
                                            for x, y in zip(x_data, y_data)]
                        x_data = np.array([x_data[i] for i, finite in enumerate(finite_positions) if finite])
                        y_data = np.array([y_data[i] for i, finite in enumerate(finite_positions) if finite])
                        mean_x = x_data.mean() if x_data.size else 0
                        mean_y = y_data.mean() if x_data.size else 0
                        if options.verbose:
                            print(f"[W]arning: some of the provided results are infinite "
                                  f"and won't be taken into account for this plot: "
                                  f"{100 * sum(1 for f in finite_positions if f) / len(finite_positions)}% elements used.")

                    if x_data.size and y_data.size:
                        family_avg_x_y_values.append((mean_x, mean_y))
                        family_x_pos_values.append(x_data.max() - mean_x)
                        family_x_neg_values.append(mean_x - x_data.min())
                        family_y_pos_values.append(y_data.max() - mean_y)
                        family_y_neg_values.append(mean_y - y_data.min())
                        family_x_std_values.append(x_data.std())
                        family_y_std_values.append(y_data.std())

                # Sort all values together
                family_data = ((*x_y, x_pos, x_neg, y_pos, y_neg, x_std, y_std)
                               for x_y, x_pos, x_neg, y_pos, y_neg, x_std, y_std
                               in zip(family_avg_x_y_values,
                                      family_x_pos_values,
                                      family_x_neg_values,
                                      family_y_pos_values,
                                      family_y_neg_values,
                                      family_x_std_values,
                                      family_y_std_values))
                family_data = sorted(family_data)
                if family_data:
                    x_values, y_values, \
                    family_x_pos_values, family_x_neg_values, \
                    family_y_pos_values, family_y_neg_values, \
                    family_x_std_values, family_y_std_values = \
                        [[d[i] for d in family_data] for i in range(len(family_data[0]))]

                    plds_by_family_label[family.label] = []
                    plds_by_family_label[family.label].append(plotdata.LineData(
                        x_values=x_values, y_values=y_values,
                        x_label=column_name_x,
                        y_label=column_name_y,
                        label=family.label, alpha=self.alpha,
                        extra_kwargs=dict(
                            marker=marker_cycle[i % len(marker_cycle)], ms=marker_size) if show_markers else None))
                    if show_v_range_bar:
                        plds_by_family_label[family.label].append(plotdata.ErrorLines(
                            x_values=x_values, y_values=y_values,
                            err_pos_values=family_y_pos_values,
                            err_neg_values=family_y_neg_values,
                            vertical=True, line_width=0.75, cap_size=3))
                    if show_h_range_bar:
                        plds_by_family_label[family.label].append(plotdata.ErrorLines(
                            x_values=x_values, y_values=y_values,
                            err_pos_values=family_x_pos_values,
                            err_neg_values=family_x_neg_values,
                            vertical=False, line_width=0.75, cap_size=3))
                    if show_v_std_bar:
                        plds_by_family_label[family.label].append(plotdata.ErrorLines(
                            x_values=x_values, y_values=y_values,
                            err_pos_values=family_y_std_values,
                            err_neg_values=family_y_std_values,
                            vertical=True, line_width=1, cap_size=2))
                    if show_h_std_bar:
                        plds_by_family_label[family.label].append(plotdata.ErrorLines(
                            x_values=x_values, y_values=y_values,
                            err_pos_values=family_x_std_values,
                            err_neg_values=family_x_std_values,
                            vertical=False, line_width=1, cap_size=2))
                else:
                    plds_by_family_label[family.label] = []

            try:
                column_properties = column_to_properties[column_name_x]
                global_min_x, global_max_x = column_properties.plot_min, column_properties.plot_max
            except (KeyError, TypeError):
                global_min_x, global_max_x = None, None

            global_min_x = float("inf")
            global_max_x = float("-inf")
            for plds in plds_by_family_label.values():
                for pld in plds:
                    global_min_x = min(global_min_x, min(pld.x_values))
                    global_max_x = min(global_max_x, max(pld.x_values))

            if math.isinf(global_min_x) or math.isinf(global_max_x):
                global_min_x, global_max_x = None, None

            if column_to_properties is None:
                def new():
                    return enb.atable.ColumnProperties("unknown")

                column_to_properties = collections.defaultdict(new)

            render_plds_by_group(
                pds_by_group_name=plds_by_family_label,
                output_plot_path=os.path.join(output_plot_dir, f"plot_line_{column_name_x}_{column_name_y}.pdf"),
                column_properties=column_to_properties[column_name_x],
                global_x_label=column_to_properties[column_name_x].label
                if column_to_properties[column_name_x].label else column_name_x,
                global_y_label=column_to_properties[column_name_y].label
                if column_to_properties[column_name_x].label else column_name_y,
                x_min=global_min_x,
                x_max=global_max_x,
                y_min=column_to_properties[column_name_y].plot_min,
                y_max=column_to_properties[column_name_y].plot_max,
                horizontal_margin=0.05 * (
                        global_max_x - global_min_x) if global_max_x is not None and global_min_x is not None else 0,
                legend_column_count=legend_column_count,
                combine_groups=True,
                group_name_order=[f.label for f in group_by])


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


class ScalarDictAnalyzer(OldAnalyzer):
    """Analyzer to plot columns that contain dictionary data with scalar entries.
    """
    #
    default_bin_count = 16

    def analyze_df(self, full_df, target_columns, output_plot_path=None, combine_keys=None,
                   x_min=None, x_max=None, mass_fraction=None, epsilon=0.0001, width_fraction=1,
                   key_to_x=None, key_list=None, output_plot_dir=None, output_csv_file=None,
                   column_to_properties=None,
                   group_by=None, group_name_order=None, show_global=True, show_count=True, version_name=None,
                   show_std_bar=True, show_std_band=False, show_individual_results=False,
                   y_tick_list=None, y_tick_label_list=None, y_tick_label_angle=0,
                   x_tick_label_angle=90, show_grid=True, combine_groups=False,
                   fig_height=None, fig_width=None,
                   semilog_y=False, semilog_y_base=10, show_h_bars=False,
                   global_y_label=""):
        """For each target column, analyze dictionary values stored in each cell.
        Scalar analysis is applied on each key found in the dictionaries.

        See @a combine_keys on how to automatically plot columns containing float to float data (integers allowed, too).

        :param full_df: df to be analyzer
        :param target_columns: either a string with the name of a column, or a list of column names. In either case,
          all referenced columns must contain dictionary data with scalar (integer, float, etc) values.
        :param output_plot_path: if provided, this will be used for plots generated by this call, after adding the
          column of interest to the name.
        :param combine_keys: if not None, it can be either:

            - a callable that takes an input dictionary and returns another one. This can be used to combine groups of
              keys into a single one before analysis in an arbitrary way.
            - a string with format 'histogram' or 'histogram(\d+)col'. This case expects dictionaries with
              numeric (float or integer) keys and entries. When used, keys are binned in regular intervals
              that conform a partition of the range between the minimum and maximum found keys
              (in all columns of the table). The number of bins is default_bin_count if 'histogram' is passed
              as value of this argument, or the positive integer specified in the second format.
              Note that this key combination is only applied when the number of different keys is larger than
              the selected number of bins.
            - None. In this keys table cell keys are not modified before the analysis.

        :param x_min, x_max: if not None, they define the minimum and maximum values that are considered. This
          applies only to the case where combine_keys indicates an histogram binning.
        :param mass_fraction: if an histogram combiner is used, and if both x_min and x_max are None, then this
          parameter sets the mass fraction that is actually used in the plot. To do this, the mass center is computed
          for each image, and values are removed around it while the sum of the removed values is below the
          total sum times mass_fraction. If width_fraction is used, this parameter must be 1 or None.
        :param epsilon: when mass_fraction < 1, epsilon determines how finely x keys are searched for. The original
          interval width is multiplied by this value, and the result is used as each search step. The default should
          sufffice in most cases, but values closer to 1 will result in faster rendering.
        :param width_fraction: if both x_min and x_max are None and histogram rendering is selected,
          this parameter allows to control the fraction of the original x-axis interval that is considered
          for analysis. For instance, a value of 0.25 will consider 25% of the original range, centered around
          the mass centroid. If mass_fraction is to be used, this value must be set to None or 1
        :param key_to_x: if None, found keys are sorted alphabetically and placed at 0, 1, ..., etc.
          If not None, if must be a dictionary so that dictionary keys (after applying @a combine_keys, if present),
          are all present in key_to_x, and values are real values
          (typically a permutation of the default 0, 1, ..., N sequence).
        :param key_list: if not None, it must be a list of the dictionary keys to be displayed, with the desired order.
        :param show_std_bar: if True, vertical error bars are shown centered on each average point, plus/minus one
          standard deviation.
        :param show_std_band: if True, a band of width 2*sigma is added to each line.
        :param fig_height, fig_width: absolute image size. Affects rendered font size.
        :param semilog_y: use a logarithmic scale for the y axis?
        :param semilog_y_base: use this base if semilog_y is True.
        :param show_h_bars: if True, +/- 0.5 horizontal bars are shown at each data point.
          Useful for coarsely classified data.
        :param y_tick_list, y_tick_label_list: passed directly to render_render_plds_by_group()

        All remaining parameters are as defined in :class:`Analyzer` or :func:`enb.aanalysis.render_plds_by_group`.
        """
        target_columns = target_columns if not isinstance(target_columns, str) else [target_columns]
        output_plot_dir = output_plot_dir if output_plot_dir is not None else options.plot_dir

        output_csv_file = output_csv_file if output_csv_file is not None else os.path.join(
            options.analysis_dir, f"{self.__class__.__name__}.csv")
        os.makedirs(os.path.dirname(os.path.abspath(output_csv_file)), exist_ok=True)

        histogram_combination = False
        bin_count = None
        if combine_keys is not None:
            if not callable(combine_keys):
                if combine_keys.startswith("histogram"):
                    if combine_keys == "histogram":
                        bin_count = self.default_bin_count
                    else:
                        try:
                            bin_count = int(re.match(r"histogram(\d+)col", combine_keys).group(1))
                        except AttributeError:
                            bin_count = self.default_bin_count
                            if options.verbose > 1:
                                print(
                                    f"[W]arning: combine_keys {repr(combine_keys)} not recognized. Using default: {bin_count}")
                    if bin_count <= 0:
                        raise ValueError(f"Invalid value for combine_keys: {combine_keys}")
                    # We cannot instantiate a HistogramKeyBinner here yet, because the minimum
                    # and maximum key values are not (yet) known.
                    histogram_combination = True
                else:
                    raise ValueError(f"Invalid value for combine_keys: {combine_keys}")

            full_df = full_df.copy()

        enb.ray_cluster.init_ray()

        keys_by_column = {}
        key_to_x_by_column = {}
        column_to_xmin_xmax = {}
        column_to_properties = dict() if column_to_properties is None else dict(column_to_properties)
        for column in target_columns:
            column_to_xmin_xmax[column] = (x_min, x_max)

            if column not in column_to_properties:
                column_to_properties[column] = enb.atable.ColumnProperties(name=column, has_dict_values=True)
            if not column_to_properties[column].has_dict_values:
                raise Exception(f"Not possible to plot column {column}, has_dict_values was not set to True")

            if histogram_combination:
                keys_by_column[column] = \
                    sorted(set(full_df[column].apply(lambda d: list(d.keys())).sum()))

                column_x_min = x_min if x_min is not None else keys_by_column[column][0]
                column_x_max = x_max if x_max is not None else keys_by_column[column][-1]
                interval_width = max(1e-10, column_x_max - column_x_min)

                # The user may select a mass fraction around the mass centroid where the plot is to be analyzed
                # (note that some data may be discarded this way).
                mass_fraction = mass_fraction if mass_fraction is not None else 1
                width_fraction = width_fraction if width_fraction is not None else 1
                if mass_fraction != 1 or width_fraction != 1:
                    assert 0 < mass_fraction <= 1, f"Invalid mass fraction {mass_fraction}"
                    absolute_mass = 0
                    x_centroid = 0
                    for d in full_df[column]:
                        for x_value, mass in d.items():
                            absolute_mass += mass
                            x_centroid += mass * x_value
                    x_centroid /= absolute_mass

                    if mass_fraction != 1:
                        assert width_fraction == 1, f"Cannot set mass_fraction and width_fraction at the same time."
                        assert 0 < mass_fraction < 1

                        def get_x_interval_width(a, b):
                            """Compute the mass of all x values in [a,b].
                            """
                            for d in full_df[column]:
                                interval_mass = 0
                                for x_value, mass in d.items():
                                    if a <= x_value <= b:
                                        interval_mass += mass
                            return interval_mass

                        column_x_min = x_centroid
                        column_x_max = x_centroid
                        interval_width = keys_by_column[column][-1] - keys_by_column[column][0]
                        while get_x_interval_width(column_x_min, column_x_max) < absolute_mass * mass_fraction:
                            column_x_min -= interval_width * epsilon
                            column_x_max += interval_width * epsilon
                    else:
                        assert 0 < width_fraction <= 1
                        column_x_min = x_centroid - interval_width * 0.5 * width_fraction
                        column_x_max = x_centroid + interval_width * 0.5 * width_fraction

                combine_keys = HistogramKeyBinner(
                    min_value=column_x_min, max_value=column_x_max, bin_count=bin_count)

            if combine_keys is not None or histogram_combination:
                full_df[column] = full_df[column].apply(combine_keys)
                if histogram_combination:
                    column_to_xmin_xmax[column] = (0, len(combine_keys.binned_keys))
            keys_by_column[column] = \
                sorted(set(full_df[column].apply(
                    lambda d: list(d.keys())).sum())) \
                    if combine_keys is None or not histogram_combination \
                    else combine_keys.binned_keys
            if key_to_x is not None:
                key_to_x_by_column[column] = key_to_x
            else:
                key_to_x_by_column[column] = {k: i for i, k in enumerate(sorted(keys_by_column[column]))} \
                    if combine_keys is None or not histogram_combination \
                    else {k: i for i, k in enumerate(combine_keys.binned_keys)}

        # Generate the plottable data
        column_to_id_by_group = collections.defaultdict(dict)
        column_to_pds_by_group = collections.defaultdict(dict)

        if group_by is not None:
            for group_name, group_df in full_df.groupby(group_by):
                df_id = ray.put(group_df)
                for column in target_columns:
                    column_to_id_by_group[column][group_name] = scalar_dict_to_pds.remote(
                        df=df_id, column=ray.put(column),
                        column_properties=ray.put(column_to_properties[column]),
                        group_label=ray.put(group_name),
                        key_to_x=ray.put(key_to_x_by_column[column]),
                        show_std_bar=ray.put(show_std_bar),
                        show_std_band=ray.put(show_std_band),
                        show_individual_results=ray.put(show_individual_results),
                        std_band_add_xmargin=ray.put(combine_keys is not None or histogram_combination))
        if group_by is None or show_global is True:
            df_id = ray.put(full_df)
            for column in target_columns:
                column_to_id_by_group[column]["all"] = scalar_dict_to_pds.remote(
                    df=df_id, column=ray.put(column),
                    column_properties=ray.put(column_to_properties[column]),
                    group_label=ray.put("all"),
                    key_to_x=ray.put(key_to_x_by_column[column]),
                    show_std_bar=ray.put(show_std_bar),
                    show_std_band=ray.put(show_std_band),
                    show_individual_results=ray.put(show_individual_results),
                    std_band_add_xmargin=(combine_keys is not None or histogram_combination))

        # Retrieve data produced in a parallel way and fix labels, colors, etc
        group_names = set()
        for column, group_to_id in column_to_id_by_group.items():
            for group_name, id in group_to_id.items():
                column_to_pds_by_group[column][group_name] = ray.get(id)
                group_names.add(group_name)
        group_names = sorted(str(n) for n in group_names)
        for column, pds_by_group in column_to_pds_by_group.items():
            for group_name, pds in pds_by_group.items():
                for pld in pds:
                    pld.color = color_cycle[group_names.index(str(pld.label)) % len(color_cycle)]
                    if not combine_groups or not isinstance(pld, plotdata.LineData):
                        pld.label = None
        # Produce the analysis csv based on the gathered information
        os.makedirs(os.path.dirname(os.path.abspath(output_csv_file)), exist_ok=True)
        with open(output_csv_file, "w") as csv_file:
            for column, pds_by_group in sorted(column_to_pds_by_group.items()):
                csv_file.write(f"Column,{','.join(str(k) for k in keys_by_column[column])}\n")
                line_data = tuple(column_to_pds_by_group[column].values())[0][0]
                assert isinstance(line_data, plotdata.LineData)
                csv_file.write(f"{column},")

                csv_file.write(','.join(str(line_data.y_values[math.floor(key_to_x_by_column[column][k])])
                                        if k in key_to_x_by_column[column]
                                           and len(line_data.y_values) > math.floor(
                    key_to_x_by_column[column][k]) else ''
                                        for k in keys_by_column[column]))
                csv_file.write("\n\n")

        render_ids = []
        original_output_plot_path = output_plot_path
        for column, pds_by_group in column_to_pds_by_group.items():
            if original_output_plot_path is not None:
                output_plot_path = original_output_plot_path.replace(".pdf", "") + f"_{column}.pdf"
            else:
                name = f"{self.__class__.__name__}"
                if group_by:
                    name += f"_group-{group_by}"
                if column in column_to_properties and column_to_properties[column].semilog_y:
                    name += "_semilogY"
                if combine_groups:
                    name += "_combine"
                    if histogram_combination:
                        name += f"_hist{bin_count}"
                    if mass_fraction != 1:
                        name += f"_massfrac{mass_fraction:.6f}"
                    if width_fraction != 1:
                        name += f"_widthfrac{width_fraction:.6f}"

                name += f"_{column}.pdf"

                output_plot_path = os.path.join(output_plot_dir, name)

            global_x_label = f"{column_to_properties[column].label}"

            margin = max(key_to_x_by_column[column].values()) / (10 * len(key_to_x_by_column[column])) \
                if key_to_x_by_column[column] else 0
            if combine_keys or histogram_combination:
                margin = 0
            if x_min is None:
                x_min = min(key_to_x_by_column[column].values()) - margin if key_to_x_by_column[column] else None
            if x_max is None:
                x_max = max(key_to_x_by_column[column].values()) + margin if key_to_x_by_column[column] else None
            y_min = column_to_properties[column].plot_min
            y_max = column_to_properties[column].plot_max

            # Add a 0.5 offset and x margin when combining keys
            if histogram_combination:
                columns = list(key_to_x_by_column.keys())
                for c in columns:
                    key_to_x_by_column[c] = {k: x + 0.5 for k, x in key_to_x_by_column[c].items()}
                    for group, pds in pds_by_group.items():
                        for plottable_data in pds:
                            plottable_data.x_values = [x + 0.5 for x in plottable_data.x_values]
                        if show_h_bars:
                            pds.append(plotdata.ErrorLines(
                                x_values=plottable_data.x_values, y_values=plottable_data.y_values,
                                err_neg_values=[0.5] * len(plottable_data.x_values),
                                err_pos_values=[0.5] * len(plottable_data.x_values),
                                vertical=False, cap_size=0, marker_size=0))
                            pds[-1].color = pds[-2].color

            x_tick_list = [key_to_x_by_column[column][k] for k in keys_by_column[column]]

            try:
                original_fig_width = options.fig_width
                options.fig_width = max(options.fig_width, len(keys_by_column[column]) / 5)

                render_ids.append(parallel_render_plds_by_group.remote(
                    pds_by_group_name=ray.put(pds_by_group),
                    output_plot_path=ray.put(output_plot_path),
                    column_properties=ray.put(column_to_properties[column]),
                    global_x_label=ray.put(global_x_label),
                    global_y_label=ray.put(global_y_label),
                    x_tick_list=ray.put(x_tick_list),
                    x_tick_label_list=ray.put(keys_by_column[column]),
                    x_tick_label_angle=ray.put(x_tick_label_angle),
                    y_tick_list=ray.put(y_tick_list),
                    y_tick_label_list=ray.put(y_tick_label_list),
                    horizontal_margin=ray.put(0.1),
                    x_min=ray.put(x_min), x_max=ray.put(x_max),
                    y_min=ray.put(y_min), y_max=ray.put(y_max),
                    show_grid=ray.put(show_grid),
                    combine_groups=ray.put(combine_groups),
                    force_monochrome_group=ray.put(False),
                    fig_height=ray.put(fig_height),
                    fig_width=ray.put(fig_width),
                    semilog_y=ray.put(semilog_y),
                    group_name_order=ray.put(group_name_order)))

                _ = [ray.get(id) for id in render_ids]

            finally:
                options.fig_width = original_fig_width


@ray.remote
def scalar_dict_to_pds(df, column, column_properties, key_to_x,
                       group_label=None,
                       show_std_bar=True, show_std_band=False,
                       show_individual_results=False, std_band_add_xmargin=False):
    """
    See :class:`enb.aanalysis.ScalarDictAnalyzer`

    :param df: df to be transformed into plotdata.* instances
    :param column: column to be analized
    :param column_properties: :class:`enb.atable.ColumnProperties instance`, if known
    :param key_to_x: see :class:`enb.aanalysis.ScalarDictAnalyzer`
    :param group_label: see :class:`enb.aanalysis.ScalarDictAnalyzer`
    :param show_std_bar: see :class:`enb.aanalysis.ScalarDictAnalyzer`
    :param show_std_band: see :class:`enb.aanalysis.ScalarDictAnalyzer`
    :param show_individual_results: see :class:`ScalarDictAnalyzer`
    :param std_band_add_xmargin: if True, if is assumed that keys were combined and a +/- 0.5 margin should be assumed
      for std band
    :return: the list of pds generated
    """
    key_to_stats = dict()
    finite_data_by_column = dict()
    for k in key_to_x.keys():
        column_data = df[column].apply(lambda d: d[k] if k in d else float("inf"))
        finite_data_by_column[column] = column_data[column_data.apply(lambda v: math.isfinite(v))].copy()
        description = finite_data_by_column[column].describe()
        if len(finite_data_by_column[column]) > 0:
            key_to_stats[k] = dict(min=description["min"],
                                   max=description["max"],
                                   std=description["std"],
                                   mean=description["mean"])

    plot_data_list = []
    avg_x_values = []
    avg_y_values = []
    std_values = []
    for k, stats in key_to_stats.items():
        avg_x_values.append(key_to_x[k])
        avg_y_values.append(stats["mean"])
        std_values.append(stats["std"] if math.isfinite(stats["std"]) else 0)
    plot_data_list.append(plotdata.LineData(x_values=avg_x_values, y_values=avg_y_values))

    if show_std_band:
        plot_data_list.append(plotdata.HorizontalBand(
            x_values=avg_x_values,
            y_values=avg_y_values,
            pos_height_values=std_values,
            neg_height_values=std_values,
            std_band_add_xmargin=std_band_add_xmargin,
            line_style="", line_width=0))

    if show_std_bar:
        plot_data_list.append(plotdata.ErrorLines(
            x_values=avg_x_values, y_values=avg_y_values,
            err_neg_values=std_values,
            err_pos_values=std_values,
            line_width=1,
            vertical=True, cap_size=2, alpha=0.3))

    if show_individual_results:
        for k, stats in key_to_stats.items():
            plot_data_list.append(plotdata.ScatterData(
                x_values=[key_to_x[k]] * len(finite_data_by_column[column]),
                y_values=finite_data_by_column[column],
                alpha=0.3))
            plot_data_list[-1].marker_size = 10
            plot_data_list[-1].extra_kwargs["marker"] = "x"

    # This is used in ScalarDictAnalyzer.analyze_df to set the right colors
    for pld in plot_data_list:
        pld.label = group_label

    return plot_data_list


class TaskFamily:
    """Describe a sorted list of task names that identify a family of related
    results within a DataFrame. Typically, this family will be constructed using
    task workers (e.g., :class:`icompression.AbstractCodec` instances) that share
    all configuration values except for a parameter.
    """

    def __init__(self, label, task_names=None, name_to_label=None):
        """
        :param label: Printable name that identifies the family
        :param task_names: if not None, it must be a list of task names (strings)
          that are expected to be found in an ATable's DataFrame when analyzing
          it.
        :param name_to_label: if not None, it must be a dictionary indexed by
        task name that contains a displayable version of it
        """
        self.label = label
        self.task_names = task_names if task_names is not None else []
        self.name_to_label = name_to_label if name_to_label is not None else {}

    def add_task(self, task_name, task_label=None):
        """
        Add a new task name to the family (it becomes the last element
        in self.task_names)

        :param task_name: A new new not previously included in the Family
        """
        assert task_name not in self.task_names
        self.task_names.append(task_name)
        if task_label:
            self.name_to_label[task_name] = task_label


def get_histogram_dicts(df, column):
    """Get a list of dicts, each one representing one histogram stored at row, column
    for al rows in df in the order given by the index.
    """
    #
    parsed_dicts = [get_nonscalar_value(column_value) for column_value in df[column]]
    assert len(parsed_dicts) == len(df)
    return parsed_dicts


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


def clean_column_name(column_name):
    """Return a cleaned version of the column name, more indicated for display.
    """
    s = column_name.replace("_", " ").strip()
    s = s[:1].upper() + s[1:]
    return s


def pdf_to_png(input_dir, output_dir, **kwargs):
    """Take all .pdf files in input dir and save them as .png files into output_dir,
    maintining the relative folder structure.

    It is perfectly valid for input_dir and output_dir
    to point to the same location, but input_dir must exist beforehand.

    :param kwargs: other parameters directly passed to pdf2image.convert_from_path. Refer to their
      documentation for more information: https://github.com/Belval/pdf2image,
      https://pdf2image.readthedocs.io/en/latest/reference.html#functions
    """
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    assert os.path.isdir(input_dir)
    for input_path in glob.glob(os.path.join(input_dir, "**", "*.pdf"), recursive=True):
        output_path = f"{input_path.replace(input_dir, output_dir)[:-4]}.png"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        kwargs["fmt"] = "png"
        _ = [img.save(output_path) for img in pdf2image.convert_from_path(pdf_path=input_path, **kwargs)]
