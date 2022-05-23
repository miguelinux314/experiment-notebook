#!/usr/bin/env python3
"""Automatic analysis and report of pandas :class:`pandas.DataFrames`
(e.g., produced by :class:`enb.experiment.Experiment` instances)
using pyplot.

See https://miguelinux314.github.io/experiment-notebook/analyzing_data.html for detailed help.
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
import alive_progress
import pdf2image
import numpy as np
import scipy.stats
import warnings
import re

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
    # Default figure width
    fig_width = 5.0
    # Default figure height
    fig_height = 4.0
    # Relative horizontal margin added to plottable data in figures, e.g. 0.1 for a 10% margin
    horizontal_margin = 0
    # Relative vertical margin added to plottable data in figures, e.g. 0.1 for a 10% margin
    vertical_margin = 0
    # Show grid lines at the major ticks?
    show_grid = False
    # Show grid lines at the minor ticks?
    show_subgrid = False
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
    group_row_margin = None
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
    # Default number of columns inside the legend
    legend_column_count = 2
    # Legend position (if configured to be shown). It can be "title" to show it above the plot,
    # or any matplotlib-recognized argument for the loc parameter of legend()
    legend_position = "title"
    # If not None, it must be a list of matplotlibrc styles (names or file paths)
    style_list = []
    # Number of decimals used when saving to latex
    latex_decimal_count = 3

    def __init__(self, csv_support_path=None, column_to_properties=None, progress_report_period=None):
        super().__init__(csv_support_path=csv_support_path,
                         column_to_properties=column_to_properties,
                         progress_report_period=progress_report_period)
        self.valid_render_modes = set(self.valid_render_modes)
        self.selected_render_modes = set(self.selected_render_modes)
        for mode in self.selected_render_modes:
            if mode not in self.valid_render_modes:
                raise SyntaxError(f"Selected mode {repr(mode)} not in the "
                                  f"list of available modes ({repr(self.valid_render_modes)}. "
                                  f"(self.selected_render_modes = {self.selected_render_modes})")

    def get_df(self, full_df, target_columns,
               selected_render_modes=None,
               output_plot_dir=None, group_by=None, reference_group=None, column_to_properties=None,
               show_global=None, show_count=None, **render_kwargs):
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
        :param show_global: if True, a group containing all elements is also included in the analysis.
          If None, self.show_count is used.
        :param show_count: if True or False, it determines whether the number of elements in each group
          is shown next to its name. If None, self.show_count is used.

        :return: a |DataFrame| instance with analysis results
        """
        show_count = show_count if show_count is not None else self.show_count
        show_global = show_global if show_global is not None else self.show_global

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

            self.save_analysis_tables(
                group_by=group_by,
                reference_group=reference_group,
                selected_render_modes=selected_render_modes,
                summary_df=summary_df,
                summary_table=summary_table,
                target_columns=target_columns)

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

        return normalized_wrapper(self=self, full_df=full_df, show_count=show_count, **render_kwargs)

    def render_all_modes(self,
                         # Dynamic arguments with every call
                         summary_df, target_columns, output_plot_dir,
                         reference_group,
                         group_by, column_to_properties,
                         # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
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
                    filtered_plds = column_kwargs["pds_by_group_name"]
                    if not self.show_reference_group:
                        filtered_plds = {k: v
                                         for k, v in column_kwargs["pds_by_group_name"].items()
                                         if k != reference_group}

                        if reference_group not in column_kwargs["pds_by_group_name"]:
                            enb.logger.debug(f"Requested reference_group {repr(reference_group)} not found.")
                        column_kwargs["pds_by_group_name"] = filtered_plds
                        if "group_name_order" in column_kwargs and column_kwargs["group_name_order"]:
                            column_kwargs["group_name_order"] = [n for n in column_kwargs["group_name_order"] if
                                                                 n != reference_group]

                    if "combine_groups" in column_kwargs and column_kwargs["combine_groups"] is True \
                            and "reference_group" in column_kwargs and column_kwargs["reference_group"] is not None:
                        for i, name in enumerate(filtered_plds.keys()):
                            if i > 0:
                                column_kwargs["pds_by_group_name"][name] = [
                                    pld for pld in column_kwargs["pds_by_group_name"][name]
                                    if not isinstance(pld, enb.plotdata.VerticalLine) or pld.x_position != 0]
                    try:
                        column_kwargs["group_name_order"] = [n for n in column_kwargs["group_name_order"]
                                                             if n != reference_group]
                    except KeyError:
                        pass

                # All arguments to the parallel rendering function are ready; their associated tasks as created
                render_ids.append(enb.plotdata.parallel_render_plds_by_group.start(
                    **dict(column_kwargs)))

        # Wait until all rendering tasks are done while updating about progress
        with enb.logger.info_context(f"Rendering {len(render_ids)} plots with {self.__class__.__name__}...\n"):
            with alive_progress.alive_bar(
                    len(render_ids), manual=True, ctrl_c=False,
                    title=f"{self.__class__.__name__}.get_df()",
                    spinner="dots_waves2",
                    disable=options.verbose <= 0,
                    enrich_print=False) as bar:
                bar(0)
                for progress_report in enb.parallel.ProgressiveGetter(
                        id_list=render_ids,
                        iteration_period=self.progress_report_period,
                        alive_bar=bar):
                    enb.logger.debug(progress_report.report())
                enb.parallel.get(render_ids)
                bar(1)

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
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

        # Set the list of plottable data instances per group
        column_kwargs["pds_by_group_name"] = {
            group_label: group_plds for group_label, group_plds
            in sorted(summary_df[["group_label", f"{column_selection}_render-{render_mode}"]].values,
                      key=lambda t: t[0])
            if self.show_reference_group or group_label != reference_group}

        # General column properties
        if "column_properties" not in column_kwargs:
            try:
                column_kwargs["column_properties"] = column_to_properties[column_selection]
            except (KeyError, TypeError):
                column_kwargs["column_properties"] = enb.atable.ColumnProperties(name=column_selection)

        # Generate some labels
        if "y_labels_by_group_name" not in column_kwargs or column_kwargs["y_labels_by_group_name"] is None:
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

        if "legend_position" not in column_kwargs:
            column_kwargs["legend_position"] = self.legend_position

        if self.style_list is not None:
            column_kwargs["style_list"] = self.style_list

        return column_kwargs

    def get_output_pdf_path(self, column_selection, group_by, reference_group, output_plot_dir, render_mode):
        if isinstance(column_selection, str):
            column_selection_str = f"{column_selection}"
        elif isinstance(column_selection, collections.abc.Iterable):
            if all(isinstance(s, str) for s in column_selection):
                column_selection_str = f"columns_{'__'.join(column_selection)}"
                if len(column_selection_str) > 150:
                    # Excessively long. Show an abbreviated form
                    column_selection_str = f"{len(column_selection)}column{'s' if len(column_selection) > 1 else ''}"
            else:
                column_selection_str = f"columns_{'__'.join('__vs__'.join(cs) for cs in column_selection)}"
                if len(column_selection_str) > 150:
                    # Excessively long. Show an abbreviated form
                    column_selection_str = f"{len(column_selection)}columns"
        else:
            raise ValueError(f"Column selection {column_selection} not supported")

        return os.path.join(
            output_plot_dir,
            f"{self.__class__.__name__}-"
            f"{column_selection_str}-{render_mode}" +
            (f"-groupby__{get_groupby_str(group_by=group_by)}" if group_by else "") +
            (f"-referencegroup__{reference_group}" if reference_group else "") +
            ".pdf")

    def save_analysis_tables(self, group_by, reference_group, selected_render_modes, summary_df, summary_table,
                             target_columns):
        """Save csv and tex files into enb.config.options.analysis_dir
        that summarize the results of one target_columns element.
        If enb.config.options.analysis_dir is None or empty, no analysis
        is performed.

        By default, the CSV contains the min, max, avg, std, and median
        of each group. Subclasses may overwrite this behavior.
        """
        if options.analysis_dir:
            # Generate full csv summary
            try:
                render_mode_str = "__".join(selected_render_modes)
            except TypeError:
                render_mode_str = str(render_mode_str).replace(os.sep, "__")
            analysis_output_path = self.get_output_pdf_path(column_selection=target_columns,
                                                            group_by=group_by,
                                                            reference_group=reference_group,
                                                            output_plot_dir=options.analysis_dir,
                                                            render_mode=render_mode_str)[:-4] + ".csv"
            enb.logger.info(f"Saving analysis results to {analysis_output_path}")
            os.makedirs(os.path.dirname(analysis_output_path), exist_ok=True)
            summary_df[list(c for c in summary_df.columns
                            if c not in summary_table.render_column_names
                            and c not in ["row_created", "row_updated",
                                          enb.atable.ATable.private_index_column])].to_csv(
                analysis_output_path, index=False)

            # Generate tex summary
            summary_df[list(c for c in summary_df.columns
                            if c not in summary_table.render_column_names
                            and c not in ["row_created", "row_updated",
                                          enb.atable.ATable.private_index_column]
                            and (c in ("group_label", "group_size")
                                 or c.endswith("_avg")))].style.format(escape="latex",
                                                                       precision=self.latex_decimal_count).format_index(
                r"\textbf{{ {} }}", escape="latex", axis=1).hide(axis="index").to_latex(
                analysis_output_path[:-4] + ".tex")

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
                    # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
                    # in turn manageable through .ini configuration files via the
                    # @enb.config.aini.managed_attributes decorator.
                    selected_render_modes=selected_render_modes,
                    show_global=None, show_count=True, plot_title=None,
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
            for pld in pld_list:
                try:
                    global_x_min = min(global_x_min, min(pld.x_values) if len(pld.x_values) > 0 else global_x_min)
                    global_x_max = max(global_x_max, max(pld.x_values) if len(pld.x_values) > 0 else global_x_max)
                except TypeError:
                    global_x_min = 0
                    global_x_max = max(global_x_max, len(pld.x_values))
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
        self.column_to_properties = dict(self.column_to_properties)
        self.render_column_names = self.add_render_columns()

        self.apply_reference_bias()

    def add_render_columns(self):
        """Add to column_to_properties the list of columns used to compute instances from the plotdata module.
        :return the list of column names added in this call:
        """
        render_column_names = []
        for selected_render_mode in self.analyzer.selected_render_modes:
            for column_selection in self.target_columns:
                render_column_name = self.analyzer.get_render_column_name(column_selection, selected_render_mode)
                self.add_column_function(
                    self,
                    fun=functools.partial(
                        self.compute_plottable_data_one_case,
                        column_selection=column_selection,
                        render_mode=selected_render_mode,
                        reference_group=self.reference_group),
                    column_properties=enb.atable.ColumnProperties(
                        name=render_column_name,
                        has_object_values=True))
                render_column_names.append(render_column_name)
        return render_column_names

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
        for k, v in ((k, v) for k, v in self.column_to_properties.items() if k not in self.render_column_names):
            column_to_properties[k] = v
        for k in self.render_column_names:
            column_to_properties[k] = self.column_to_properties[k]
        self.column_to_properties = column_to_properties

    def apply_reference_bias(self):
        """By default, no action is performed relative to the presence of a reference group,
        and not bias is introduced in the dataframe. Subclasses may overwrite this.
        """
        if self.reference_group:
            enb.logger.warning(f"A reference group {repr(self.reference_group)} is selected "
                               f"but {self.__class__} does not implement its apply_reference_bias method.")
        return

    def remove_nans(self, column_series):
        return column_series.replace([np.inf, -np.inf], np.nan, inplace=False).dropna()


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
    valid_render_modes = {"histogram", "hbar", "boxplot"}
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
    # If True, modes that allow it show the individual samples
    show_individual_samples = False

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
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

        # Obtain the group averages for sorting and displaying purposes
        plds_by_group = summary_df[
            self.get_render_column_name(column_selection=column_selection, selected_render_mode=render_mode)]

        if render_mode == "histogram":
            group_avg_tuples = []
            for group, plds in plds_by_group.items():
                try:
                    group_avg_tuples.append((group,
                                             [p.x_values[0] for p in plds if isinstance(p, enb.plotdata.ScatterData)][
                                                 0]))
                except IndexError:
                    # Empty group
                    group_avg_tuples.append((group, 0))

        elif render_mode == "hbar":
            group_avg_tuples = []
            for group, plds in plds_by_group.items():
                try:
                    group_avg_tuples.append((group, plds[0].y_values[0]))
                except IndexError:
                    # Empty group
                    group_avg_tuples.append((group, 0))
        elif render_mode == "boxplot":
            group_avg_tuples = []
            for group, plds in plds_by_group.items():
                try:
                    group_avg_tuples.append((group,
                                             [p.x_values[0] for p in plds if isinstance(p, enb.plotdata.ErrorLines)][
                                                 0]))
                except IndexError:
                    # Empty group
                    group_avg_tuples.append((group, 0))
        else:
            raise ValueError(f"Unsupported render mode {render_mode}")

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

        if render_mode == "histogram":
            fun = self.update_render_kwargs_one_case_histogram
        elif render_mode == "hbar":
            fun = self.update_render_kwargs_one_case_hbar
        elif render_mode == "boxplot":
            fun = self.update_render_kwargs_one_case_boxplot
        else:
            raise ValueError(f"Invalid render mode {render_mode}")
        return fun(
            column_selection=column_selection,
            reference_group=reference_group,
            render_mode=render_mode,
            summary_df=summary_df,
            output_plot_dir=output_plot_dir,
            group_by=group_by, column_to_properties=column_to_properties,
            show_global=show_global, show_count=show_count, **column_kwargs)

    def update_render_kwargs_one_case_histogram(self, column_selection, reference_group, render_mode,
                                                # Dynamic arguments with every call
                                                summary_df, output_plot_dir,
                                                group_by, column_to_properties,
                                                # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
                                                # in turn manageable through .ini configuration files via the
                                                # @enb.config.aini.managed_attributes decorator.
                                                show_global, show_count,
                                                # Rendering options, directly passed to plotdata.render_plds_by_group
                                                **column_kwargs):
        """Update rendering kwargs (e.g., labels) specifically for the histogram mode.
        """
        # Update specific rendering kwargs for this analyzer:
        if "global_x_label" not in column_kwargs:
            if self.main_alpha <= 0 or self.bar_width_fraction <= 0:
                column_kwargs["global_x_label"] = f"Average {column_to_properties[column_selection].label}"
            else:
                column_kwargs["global_x_label"] = column_to_properties[column_selection].label

            if reference_group is not None:
                column_kwargs["global_x_label"] += f" difference vs. {reference_group}"

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

        # Fix the patterns used in the bars in the combined case
        if ("combine_groups" in column_kwargs and column_kwargs["combine_groups"]) \
                or ("combine_groups" not in column_kwargs and self.combine_groups):

            # Combined histograms do not allow showing means.
            column_kwargs["pds_by_group_name"] = {
                k: [pld for pld in v
                    if not isinstance(pld, plotdata.ScatterData)
                    and not isinstance(pld, plotdata.ErrorLines)]
                for k, v in column_kwargs["pds_by_group_name"].items()
            }

            # Fix pattern
            for i, ((group_name, group_pds), pattern) in enumerate(zip(
                    sorted(column_kwargs["pds_by_group_name"].items()),
                    plotdata.pattern_cycle)):
                for pld in group_pds:
                    if isinstance(pld, plotdata.BarData):
                        pld.pattern = pattern

            column_kwargs["global_y_label"] = "Relative frequency"

        # Add the reference vertical line at x=0 if needed
        if reference_group:
            for name, pds in column_kwargs["pds_by_group_name"].items():
                if self.show_reference_group or name != reference_group:
                    pds.append(plotdata.VerticalLine(x_position=0, alpha=0.3, color="black"))

        return column_kwargs

    def update_render_kwargs_one_case_hbar(self, column_selection, reference_group, render_mode,
                                           # Dynamic arguments with every call
                                           summary_df, output_plot_dir,
                                           group_by, column_to_properties,
                                           # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
                                           # in turn manageable through .ini configuration files via the
                                           # @enb.config.aini.managed_attributes decorator.
                                           show_global, show_count,
                                           # Rendering options, directly passed to plotdata.render_plds_by_group
                                           **column_kwargs):
        """Update rendering kwargs (e.g., labels) specifically for the hbarmode.
        """
        if "global_x_label" not in column_kwargs:

            column_kwargs["global_x_label"] = column_to_properties[column_selection].label
            if reference_group is not None:
                column_kwargs["global_x_label"] += f" difference vs. {reference_group}"

        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = ""

        # Calculate axis limits
        if "x_min" not in column_kwargs:
            column_kwargs["x_min"] = float(summary_df[f"{column_selection}_min"].min()) \
                if column_to_properties[column_selection].plot_min is None else \
                column_to_properties[column_selection].plot_min
        if "x_max" not in column_kwargs:
            column_kwargs["x_max"] = float(summary_df[f"{column_selection}_max"].max()) \
                if column_to_properties[column_selection].plot_max is None else \
                column_to_properties[column_selection].plot_max

        column_kwargs["combine_groups"] = True

        group_names = sorted(column_kwargs["pds_by_group_name"].keys())
        try:
            if column_kwargs["group_name_order"]:
                group_names = column_kwargs["group_name_order"]
        except KeyError:
            pass
        group_names = [n for n in reversed(group_names)
                       if not reference_group or n != reference_group]

        pds_by_group_name = column_kwargs["pds_by_group_name"]
        column_kwargs["pds_by_group_name"] = {}
        for i, name in enumerate(group_names):
            column_kwargs["pds_by_group_name"][name] = pds_by_group_name[name]
            for pld in pds_by_group_name[name]:
                pld.x_values = (i,)
            if reference_group and \
                    (self.show_reference_group or name != reference_group):
                column_kwargs["pds_by_group_name"][name].append(
                    enb.plotdata.VerticalLine(x_position=0, alpha=0.3, color="black"))

        column_kwargs["y_tick_list"] = list(range(len(column_kwargs["pds_by_group_name"])))
        column_kwargs["y_tick_label_list"] = list(
            column_kwargs["y_labels_by_group_name"][name]
            if "y_labels_by_group_name" in column_kwargs and name in column_kwargs["y_labels_by_group_name"]
            else name for name in column_kwargs["pds_by_group_name"].keys())

        column_kwargs["y_min"] = -0.5
        column_kwargs["y_max"] = len(column_kwargs["pds_by_group_name"]) - 1 + 0.5
        column_kwargs["show_legend"] = False

        column_kwargs["fig_height"] = 0.5 + 0.5 * len(column_kwargs["pds_by_group_name"])

        return column_kwargs

    def update_render_kwargs_one_case_boxplot(self, column_selection, reference_group, render_mode,
                                              # Dynamic arguments with every call
                                              summary_df, output_plot_dir,
                                              group_by, column_to_properties,
                                              # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
                                              # in turn manageable through .ini configuration files via the
                                              # @enb.config.aini.managed_attributes decorator.
                                              show_global, show_count,
                                              # Rendering options, directly passed to plotdata.render_plds_by_group
                                              **column_kwargs):
        """Update rendering kwargs (e.g., labels) specifically for the boxplot mode.
        """
        if "global_x_label" not in column_kwargs:

            column_kwargs["global_x_label"] = column_to_properties[column_selection].label
            if reference_group is not None:
                column_kwargs["global_x_label"] += f" difference vs. {reference_group}"

        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = ""

        # Calculate axis limits
        forced_xmin = "x_min" in column_kwargs and column_kwargs["x_min"] is not None
        forced_xmax = "x_max" in column_kwargs and column_kwargs["x_max"] is not None
        if "x_min" not in column_kwargs:
            column_kwargs["x_min"] = float(summary_df[f"{column_selection}_min"].min()) \
                if column_to_properties[column_selection].plot_min is None else \
                column_to_properties[column_selection].plot_min
        if "x_max" not in column_kwargs:
            column_kwargs["x_max"] = float(summary_df[f"{column_selection}_max"].max()) \
                if column_to_properties[column_selection].plot_max is None else \
                column_to_properties[column_selection].plot_max

        margin = 0.05 * (column_kwargs["x_max"] - column_kwargs["x_min"])
        if not forced_xmin:
            column_kwargs["x_min"] -= margin
        if not forced_xmax:
            column_kwargs["x_max"] += margin

        column_kwargs["combine_groups"] = True
        try:
            group_names = column_kwargs["group_name_order"]
        except KeyError:
            group_names = sorted(column_kwargs["pds_by_group_name"].keys())
            try:
                if column_kwargs["group_name_order"]:
                    group_names = column_kwargs["group_name_order"]
            except KeyError:
                pass
        group_names = [n for n in reversed(group_names)
                       if self.show_reference_group or n != reference_group]

        pds_by_group_name = column_kwargs["pds_by_group_name"]
        column_kwargs["pds_by_group_name"] = {}
        for i, name in enumerate(group_names):
            column_kwargs["pds_by_group_name"][name] = pds_by_group_name[name]
            for pld in column_kwargs["pds_by_group_name"][name]:
                # All elements of a group are aligned along the same horizontal position
                pld.y_values = [i] * len(pld.y_values)
            if reference_group and \
                    (self.show_reference_group or name != reference_group):
                column_kwargs["pds_by_group_name"][name].append(
                    enb.plotdata.VerticalLine(x_position=0, alpha=0.3, color="black"))

        column_kwargs["y_tick_list"] = list(range(len(column_kwargs["pds_by_group_name"])))
        column_kwargs["y_tick_label_list"] = list(
            column_kwargs["y_labels_by_group_name"][name]
            if "y_labels_by_group_name" in column_kwargs and name in column_kwargs["y_labels_by_group_name"]
            else name for name in column_kwargs["pds_by_group_name"].keys())

        column_kwargs["y_min"] = -0.5
        column_kwargs["y_max"] = len(column_kwargs["pds_by_group_name"]) - 1 + 0.5
        column_kwargs["show_legend"] = False

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
            self.column_to_xmin_xmax[column_name] = min(finite_series.values), max(finite_series.values)

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
        finite_series = self.remove_nans(full_series)

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

        if len(np.unique(finite_series.values)) > 1:
            description_df = finite_series.describe()
            row[f"{column_name}_min"] = description_df["min"]
            row[f"{column_name}_max"] = description_df["max"]
            row[f"{column_name}_avg"] = description_df["mean"]
            row[f"{column_name}_std"] = description_df["std"]
            row[f"{column_name}_median"] = description_df["50%"]
        else:
            row[f"{column_name}_min"] = finite_series.values[0]
            row[f"{column_name}_max"] = finite_series.values[0]
            row[f"{column_name}_avg"] = finite_series.values[0]
            row[f"{column_name}_std"] = 0
            row[f"{column_name}_median"] = finite_series.values[0]

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes
        a list of `enb.plotdata.PlottableData elements` for this case (group, column, render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        if kwargs["render_mode"] == "histogram":
            return self.compute_histogram_plottable_one_case(*args, **kwargs)
        elif kwargs["render_mode"] == "hbar":
            return self.compute_hbar_plottable_one_case(*args, **kwargs)
        elif kwargs["render_mode"] == "boxplot":
            return self.compute_boxplot_plottable_one_case(*args, **kwargs)
        else:
            raise ValueError(f"Invalid render mode {kwargs['render_mode']}")

    def compute_histogram_plottable_one_case(self, *args, **kwargs):
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        column_series = group_df[column_name].copy()

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")
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

        finite_only_series = self.remove_nans(column_series)
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
            alpha=_self.analyzer.main_alpha))
        if _self.analyzer.show_x_std:
            row[_column_name].append(plotdata.ErrorLines(
                x_values=[row[f"{column_name}_avg"]],
                y_values=[marker_y_position],
                marker_size=0,
                alpha=_self.analyzer.main_alpha,
                err_neg_values=[row[f"{column_name}_std"]],
                err_pos_values=[row[f"{column_name}_std"]],
                line_width=_self.analyzer.main_line_width,
                vertical=False))

    def compute_hbar_plottable_one_case(self, *args, **kwargs):
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        column_series = group_df[column_name]

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")
        assert render_mode == "hbar"

        finite_only_series = self.remove_nans(column_series)
        if len(finite_only_series) == 0:
            enb.logger.warn(f"{_self.__class__.__name__}: No finite data found for column {repr(column_name)}. "
                            f"No plottable data is produced for this case.")
            row[_column_name] = []
            return
        if len(column_series) != len(column_series):
            enb.logger.debug("Finite and/or NaNs found in the input. "
                             f"Using {100 * (len(finite_only_series) / len(column_series))}% of the total.")

        row[_column_name] = [enb.plotdata.BarData(
            x_values=(0,),
            y_values=(finite_only_series.mean(),),
            vertical=False,
            alpha=_self.analyzer.main_alpha), ]

    def compute_boxplot_plottable_one_case(self, *args, **kwargs):
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        column_series = group_df[column_name]

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")
        assert render_mode == "boxplot"

        finite_only_series = self.remove_nans(column_series)
        if len(finite_only_series) == 0:
            enb.logger.warn(f"{_self.__class__.__name__}: No finite data found for column {repr(column_name)}. "
                            f"No plottable data is produced for this case.")
            row[_column_name] = []
            return
        if len(column_series) != len(column_series):
            enb.logger.debug("Finite and/or NaNs found in the input. "
                             f"Using {100 * (len(finite_only_series) / len(column_series))}% of the total.")

        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            np.seterr(all="raise")
            try:
                description = scipy.stats.describe(finite_only_series)
                quartiles = scipy.stats.mstats.mquantiles(finite_only_series)
            except (RuntimeWarning, FloatingPointError):
                class Description:
                    try:
                        minmax = [finite_only_series.values[0]] * 2
                        mean = finite_only_series.values[0]
                    except IndexError:
                        minmax = 0, 0
                        mean = 0

                description = Description()
                try:
                    quartiles = [finite_only_series.values[0]] * 3
                except IndexError:
                    quartiles = 0, 0, 0
            np.seterr(all="warn")

        row[_column_name] = [
            enb.plotdata.ErrorLines(
                x_values=(description.mean,),
                y_values=(0,),
                err_neg_values=(description.mean - description.minmax[0],),
                err_pos_values=(description.minmax[1] - description.mean,),
                vertical=False,
                line_width=_self.analyzer.main_line_width,
                marker_size=_self.analyzer.main_marker_size,
                alpha=_self.analyzer.main_alpha),
            enb.plotdata.Rectangle(
                x_values=(0.5 * (quartiles[0] + quartiles[2]),), y_values=(0,),
                width=quartiles[2] - quartiles[0],
                line_width=_self.analyzer.main_line_width,
                alpha=_self.analyzer.main_alpha,
                height=0.8),
            enb.plotdata.LineSegment(
                x_values=(quartiles[1],), y_values=(0,),
                line_width=_self.analyzer.main_line_width,
                alpha=_self.analyzer.main_alpha,
                length=0.8,
                vertical=True),
        ]

        if _self.analyzer.show_individual_samples:
            row[_column_name].append(enb.plotdata.ScatterData(
                y_values=[0] * len(finite_only_series.values),
                x_values=list(finite_only_series),
                alpha=_self.analyzer.secondary_alpha,
                marker_size=_self.analyzer.secondary_marker_size,
                marker="o",
            ))


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
    common_group_scale = True
    combine_groups = True
    show_legend = True

    # Specific analyzer attributes:
    # If True, individual data points are shown
    show_individual_samples = True
    # If True, markers of the same group in the exact same x position are 
    # grouped into a single one with the average y value. Applies only in the 'line' render mode.
    average_identical_x = False
    # If True, a line displaying linear regression is shown in the 'scatter' render mode
    show_linear_regression = False

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
            # in turn manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to plotdata.render_plds_by_group
            **column_kwargs):
        # Update common rendering kwargs, including the 'pds_by_group_name' entry with the data to be plotted
        column_kwargs = super().update_render_kwargs_one_case(
            column_selection=column_selection, reference_group=reference_group,
            render_mode=render_mode,
            summary_df=summary_df, output_plot_dir=output_plot_dir,
            group_by=group_by, column_to_properties=column_to_properties,
            show_global=show_global, show_count=show_count,
            **column_kwargs)

        # Combine samples in the same x position
        if self.average_identical_x and render_mode == "line":
            for group_name, group_pds in column_kwargs["pds_by_group_name"].items():
                for pd in group_pds:
                    x_to_ylist = collections.defaultdict(list)
                    for x_value, y_value in zip(pd.x_values, pd.y_values):
                        x_to_ylist[x_value].append(y_value)

                    pd.x_values = sorted(x_to_ylist.keys())
                    pd.y_values = [sum(x_to_ylist[x]) / len(x_to_ylist[x])
                                   for x in pd.x_values]

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
                                              (f" difference vs. {reference_group}" if reference_group else "")
        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = y_column_properties.label + \
                                              (f" difference vs. {reference_group}" if reference_group else "")

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

    def save_analysis_tables(
            self, group_by, reference_group, selected_render_modes, summary_df,
            summary_table, target_columns):
        """Save csv and tex files into enb.config.options.analysis_dir
        that summarize the results of one target_columns element.
        If enb.config.options.analysis_dir is None or empty, no analysis
        is performed.

        By default, the CSV contains the min, max, avg, std, and median
        of each group. Subclasses may overwrite this behavior.
        """
        for render_mode in selected_render_modes:
            if render_mode == "scatter":
                super().save_analysis_tables(
                    group_by=group_by,
                    reference_group=reference_group,
                    selected_render_modes={render_mode},
                    summary_df=summary_df,
                    summary_table=summary_table,
                    target_columns=target_columns)
            elif options.analysis_dir:
                for column_pair in target_columns:
                    analysis_output_path = self.get_output_pdf_path(
                        column_selection=[column_pair],
                        group_by=group_by,
                        reference_group=reference_group,
                        output_plot_dir=options.analysis_dir,
                        render_mode=render_mode)[:-4] + ".csv"
                    os.makedirs(os.path.dirname(analysis_output_path), exist_ok=True)
                    with open(analysis_output_path, "w") as analysis_file:
                        pds_column = summary_df[f"{repr(column_pair)}_render-{render_mode}"]
                        for index, row in summary_df.iterrows():
                            group_name = re.match(r"\('(.+)',\)", index).group(1)
                            x_values = row[f"{repr(column_pair)}_render-{render_mode}"][0].x_values
                            y_values = row[f"{repr(column_pair)}_render-{render_mode}"][0].y_values
                            analysis_file.write(
                                ",".join([group_name, column_pair[0]] + [str(x) for x in x_values]) + "\n")
                            analysis_file.write(",".join(["", column_pair[1]] + [str(y) for y in y_values]) + "\n")


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
        self.column_to_stat_description = {}
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
                    if len(full_df) == 1 or len(full_df[column_name].unique()) == 1:
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
                raise ValueError(f"Cannot use a not None reference_group if group_by is None "
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
        _self, group_label, row = args
        x_column_name, y_column_name = kwargs["column_selection"]

        full_series_x = _self.label_to_df[group_label][x_column_name]
        finite_series_x = self.remove_nans(full_series_x)
        full_series_y = _self.label_to_df[group_label][y_column_name]
        finite_series_y = self.remove_nans(full_series_y)

        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            try:
                row[f"{x_column_name}_{y_column_name}_pearson_correlation"], \
                row[f"{x_column_name}_{y_column_name}_pearson_correlation_pvalue"] = \
                    scipy.stats.pearsonr(finite_series_x, finite_series_y)
                row[f"{x_column_name}_{y_column_name}_spearman_correlation"], \
                row[f"{x_column_name}_{y_column_name}_spearman_correlation_pvalue"] = \
                    scipy.stats.spearmanr(finite_series_x, finite_series_y)
                lr_results = scipy.stats.linregress(finite_series_x, finite_series_y)
                row[f"{x_column_name}_{y_column_name}_linear_lse_slope"] = lr_results.slope
                row[f"{x_column_name}_{y_column_name}_linear_lse_intercept"] = lr_results.intercept
            except (RuntimeWarning, FloatingPointError, ValueError):
                enb.logger.info(f"{self.__class__.__name__}: Cannot set correlation metrics for dataframes of length 1")
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
        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        plds_this_case = []
        if render_mode == "scatter":
            plds_this_case.append(plotdata.ScatterData(
                x_values=[row[f"{x_column_name}_avg"]],
                y_values=[row[f"{y_column_name}_avg"]],
                alpha=_self.analyzer.main_alpha,
                marker_size=5 * _self.analyzer.main_marker_size))
            if self.analyzer.show_individual_samples:
                plds_this_case.append(plotdata.ScatterData(
                    x_values=x_column_series.values,
                    y_values=y_column_series.values,
                    alpha=_self.analyzer.main_alpha,
                    marker_size=5 * _self.analyzer.secondary_marker_size,
                    extra_kwargs=dict(linewidths=0)))
            if self.analyzer.show_x_std:
                plds_this_case.append(plotdata.ErrorLines(
                    x_values=[row[f"{x_column_name}_avg"]],
                    y_values=[row[f"{y_column_name}_avg"]],
                    marker_size=0,
                    alpha=_self.analyzer.secondary_alpha,
                    err_neg_values=[row[f"{x_column_name}_std"]],
                    err_pos_values=[row[f"{x_column_name}_std"]],
                    line_width=_self.analyzer.secondary_line_width,
                    vertical=False))
            if self.analyzer.show_y_std:
                plds_this_case.append(plotdata.ErrorLines(
                    x_values=[row[f"{x_column_name}_avg"]],
                    y_values=[row[f"{y_column_name}_avg"]],
                    marker_size=0,
                    alpha=_self.analyzer.secondary_alpha,
                    err_neg_values=[row[f"{y_column_name}_std"]],
                    err_pos_values=[row[f"{y_column_name}_std"]],
                    line_width=_self.analyzer.secondary_line_width,
                    vertical=True))
            if self.analyzer.show_linear_regression:
                x_min, x_max = row[f"{x_column_name}_min"], row[f"{x_column_name}_max"]
                slope = row[f"{x_column_name}_{y_column_name}_linear_lse_slope"]
                intercept = row[f"{x_column_name}_{y_column_name}_linear_lse_intercept"]
                plds_this_case.append(plotdata.LineData(
                    x_values=[x_min, x_max],
                    y_values=[intercept + slope * x for x in (x_min, x_max)],
                    marker_size=0, alpha=_self.analyzer.secondary_alpha,
                    line_width=_self.analyzer.secondary_line_width))
        elif render_mode == "line":
            if self.group_by == "family_label":
                try:
                    group_by = kwargs["task_families"]
                except KeyError:
                    raise ValueError(f"Passed {repr(group_by)} for grouping but no task_families parameter found.")
            else:
                group_by = self.group_by

            if is_family_grouping(group_by=group_by):
                # Family line plots look into the task names and produce
                # one marker per task, linking same-family tasks with a line.
                x_values = []
                y_values = []

                current_family = [f for f in group_by if f.label == group_label][0]
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
                alpha=_self.analyzer.main_alpha,
                marker_size=_self.analyzer.main_marker_size - 1))
        else:
            raise SyntaxError(f"Invalid render mode {repr(render_mode)} not within the "
                              f"supported ones for {_self.analyzer.__class__.__name__} "
                              f"({repr(_self.analyzer.valid_render_modes)}")

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
                self.key_to_x = None

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
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
            column_kwargs["global_x_label"] = f"{column_properties.label}"
        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = f""

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
            column_kwargs["x_tick_label_list"] = [str(x) for x in column_kwargs["x_tick_list"]]

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

        self.add_group_description_columns()
        self.move_render_columns_back()

    def add_group_description_columns(self):
        for column_name in self.target_columns:
            for descriptor in ["min", "max", "avg", "std", "median"]:
                self.add_column_function(
                    self,
                    fun=functools.partial(self.set_group_description, column_selection=column_name),
                    column_properties=enb.atable.ColumnProperties(
                        name=f"{column_name}_{descriptor}", label=f"{column_name}: {descriptor}",
                        has_dict_values=True))

    def set_group_description(self, *args, **kwargs):
        _self, group_label, row = args
        column_name = kwargs["column_selection"]
        group_df = _self.label_to_df[group_label]
        full_series = group_df[column_name]
        finite_series = self.remove_nans(full_series)

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

        x_values = []
        min_values = []
        max_values = []
        avg_values = []
        std_values = []
        median_values = []
        key_values = []
        for x, k in enumerate(_self.analyzer.column_name_to_keys[column_name]):
            values = group_df[f"__{column_name}_combined"].apply(lambda d: d[k] if k in d else None).dropna()
            if len(values) > 0:
                if _self.analyzer.key_to_x:
                    try:
                        x_values.append(_self.analyzer.key_to_x[k])
                    except KeyError:
                        enb.logger.debug(f"{self.__class__.__name__}: "
                                         f"Key {k} not present in {self.analyzer.__class__.__name__}'s key_to_x. "
                                         f"Ignoring.")
                        continue
                else:
                    x_values.append(x)
                key_values.append(k)

                with warnings.catch_warnings():
                    try:
                        warnings.filterwarnings("error")
                        description = scipy.stats.describe(values)
                        min_values.append(description.minmax[0])
                        max_values.append(description.minmax[1])
                        avg_values.append(description.mean)
                        std_values.append(math.sqrt(description.variance))
                        median_values.append(values.median())
                    except (FloatingPointError, RuntimeWarning):
                        min_values.append(values.min())
                        max_values.append(values.min())
                        avg_values.append(values.mean())
                        std_values.append(values.std() if len(np.unique(values)) > 1 else 0)
                        median_values.append(values.median())

        for label, data_list in [("min", min_values),
                                 ("max", max_values),
                                 ("avg", avg_values),
                                 ("std", std_values),
                                 ("median", median_values)]:
            row[f"{column_name}_{label}"] = {k: v for k, v in zip(key_values, data_list)}

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
        reference_group = kwargs["reference_group"]  # Bias has already been applied by now, if needed
        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        # Only one mode is supported in this version of enb
        assert render_mode == "line"

        row[_column_name] = []

        key_values, avg_values = zip(*sorted(row[f"{column_name}_avg"].items()))

        if _self.analyzer.key_to_x:
            x_values = [_self.analyzer.key_to_x[k] for k in key_values]
        elif any(isinstance(k, str) for k in key_values):
            x_values = range(len(key_values))
        else:
            x_values = key_values

        if _self.analyzer.show_individual_samples and (
                self.analyzer.secondary_alpha is None or self.analyzer.secondary_alpha > 0):
            row[_column_name].append(enb.plotdata.ScatterData(
                x_values=x_values,
                y_values=avg_values,
                alpha=self.analyzer.secondary_alpha))
        if render_mode == "line":
            row[_column_name].append(enb.plotdata.LineData(
                x_values=x_values, y_values=avg_values, alpha=self.analyzer.main_alpha,
                line_width=_self.analyzer.main_line_width,
                marker_size=_self.analyzer.main_marker_size, ))
            if _self.analyzer.show_y_std:
                _, std_values = zip(*sorted(row[f"{column_name}_std"].items()))
                assert len(_) == len(x_values)
                row[_column_name].append(enb.plotdata.ErrorLines(
                    x_values=x_values, y_values=avg_values,
                    err_neg_values=std_values, err_pos_values=std_values,
                    alpha=_self.analyzer.secondary_alpha,
                    vertical=True))
        else:
            raise ValueError(f"Unexpected render mode {render_mode} for {self.__class__.__name__}")


@enb.config.aini.managed_attributes
class ScalarNumeric2DAnalyzer(ScalarNumericAnalyzer):
    bin_count = 50
    valid_render_modes = {"colormap"}
    selected_render_modes = {"colormap"}
    x_tick_format_str = "{:.2f}"
    y_tick_format_str = "{:.2f}"
    color_map = "inferno"
    no_data_color = (1, 1, 1, 0)
    bad_data_color = "magenta"

    """Analyzer able to process scalar numeric values located on an (x,y) plane.
    
    The target_columns parameter must be an iterable of tuples with 3 elements, containing the columns with 
    the x, y and data coordinates, e.g., ("column_x", "column_y", "column_data").
    """

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
            # in turn manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to plotdata.render_plds_by_group
            **column_kwargs):
        column_kwargs = Analyzer.update_render_kwargs_one_case(
            self, column_selection=column_selection,
            reference_group=reference_group,
            render_mode=render_mode,
            summary_df=summary_df,
            output_plot_dir=output_plot_dir,
            group_by=group_by,
            column_to_properties=column_to_properties,
            show_global=show_global,
            show_count=show_count,
            **column_kwargs)

        if "global_x_label" not in column_kwargs:
            x_column_name = column_selection[0]
            try:
                x_column_label = column_to_properties[x_column_name].label
            except (TypeError, KeyError):
                x_column_label = enb.atable.clean_column_name(x_column_name)
            column_kwargs["global_x_label"] = x_column_label

        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = None

        if render_mode == "colormap":
            for group_name, plds in column_kwargs["pds_by_group_name"].items():
                for pd in (p for p in plds if isinstance(p, enb.plotdata.Histogram2D)):
                    data_column_name = column_selection[2]
                    try:
                        data_column_label = column_to_properties[data_column_name].label
                    except (TypeError, KeyError):
                        data_column_label = enb.atable.clean_column_name(data_column_name)
                    pd.colormap_label = data_column_label

            histogram_pds = list(
                p for group_name, plds in column_kwargs["pds_by_group_name"].items()
                for p in plds if isinstance(p, enb.plotdata.Histogram2D))
            assert histogram_pds

            h2d = histogram_pds[0]

            if "x_tick_list" not in column_kwargs:
                column_kwargs["x_tick_list"] = h2d.x_values
                column_kwargs["x_tick_label_list"] = [
                    self.x_tick_format_str.format(e) for e in h2d.x_edges]
                if len(column_kwargs["x_tick_label_list"]) > 16:
                    column_kwargs["x_tick_list"] = [
                        column_kwargs["x_tick_list"][0],
                        column_kwargs["x_tick_list"][len(column_kwargs["x_tick_list"]) // 2],
                        column_kwargs["x_tick_list"][-1]]
                    column_kwargs["x_tick_label_list"] = [
                        column_kwargs["x_tick_label_list"][0],
                        column_kwargs["x_tick_label_list"][len(column_kwargs["x_tick_label_list"]) // 2],
                        column_kwargs["x_tick_label_list"][-1]]

            if "y_tick_list" not in column_kwargs:
                column_kwargs["y_tick_list"] = h2d.y_values
                column_kwargs["y_tick_label_list"] = [
                    self.y_tick_format_str.format(e) for e in h2d.y_edges]
                if len(column_kwargs["y_tick_label_list"]) > 16:
                    column_kwargs["y_tick_list"] = [
                        column_kwargs["y_tick_list"][0],
                        column_kwargs["y_tick_list"][
                            len(column_kwargs["y_tick_list"]) // 2],
                        column_kwargs["y_tick_list"][-1]]
                    column_kwargs["y_tick_label_list"] = [
                        column_kwargs["y_tick_label_list"][0],
                        column_kwargs["y_tick_label_list"][
                            len(column_kwargs["y_tick_label_list"]) // 2],
                        column_kwargs["y_tick_label_list"][-1]]

            if "x_min" not in column_kwargs:
                column_kwargs["x_min"] = 0
            if "x_max" not in column_kwargs:
                column_kwargs["x_max"] = h2d.x_values[-1]
            if "y_min" not in column_kwargs:
                column_kwargs["y_min"] = 0
            if "y_max" not in column_kwargs:
                column_kwargs["y_max"] = h2d.y_values[-1]
            column_kwargs["x_tick_label_angle"] = 90

            column_kwargs["left_y_label"] = True

            y_column_name = column_selection[1]
            try:
                y_column_label = column_to_properties[y_column_name].label
            except (TypeError, KeyError):
                y_column_label = enb.atable.clean_column_name(y_column_name)

            if not column_kwargs["combine_groups"] and len(column_kwargs["pds_by_group_name"]) > 1:
                for group_name, pds in column_kwargs["pds_by_group_name"].items():
                    for pd in (p for p in pds if isinstance(p, enb.plotdata.Histogram2D)):
                        pd.colormap_label = f"{pd.colormap_label}" \
                                            + (f" vs {column_kwargs['y_labels_by_group_name'][reference_group]}"
                                               if reference_group and pd.colormap_label else "") \
                                            + (f"\n" if pd.colormap_label else "") + \
                                            f"{column_kwargs['y_labels_by_group_name'][group_name]}"

            # The y_labels_by_group_name key is set to the y label name; the group name is shown
            # to the right of the colorbar.
            column_kwargs["y_labels_by_group_name"] = {
                group_name: y_column_label
                for group_name in column_kwargs["pds_by_group_name"].keys()}

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, reference_group, group_by, include_all_group):
        """Dynamically build a SummaryTable instance for scalar value analysis.
        """
        return ScalarNumeric2DSummary(analyzer=self, full_df=full_df, target_columns=target_columns,
                                      reference_group=reference_group,
                                      group_by=group_by, include_all_group=include_all_group)


class ScalarNumeric2DSummary(ScalarNumericSummary):

    def __init__(self, analyzer, full_df, target_columns, reference_group, group_by, include_all_group):
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_selection and render_mode.
        AnalyzerSummary.__init__(
            self=self,
            analyzer=analyzer, full_df=full_df, target_columns=target_columns,
            reference_group=reference_group, group_by=group_by, include_all_group=include_all_group)
        self.column_to_min_max = {}

        for column_tuple in target_columns:
            for column_name in column_tuple:
                if column_name not in full_df.columns:
                    raise ValueError(f"Invalid column name selection {repr(column_name)}. "
                                     f"Full selection: {repr(target_columns)}")

                if column_name in self.column_to_min_max:
                    continue

                # Add columns that compute the summary information
                self.add_scalar_description_columns(column_name=column_name)

                # Compute the global dynamic range of all input samples (before grouping)
                finite_series = full_df[column_name].replace([np.inf, -np.inf], np.nan, inplace=False).dropna()
                if len(finite_series) > 1:
                    try:
                        self.column_to_min_max[column_name] = scipy.stats.describe(finite_series.values).minmax
                    except FloatingPointError as ex:
                        raise FloatingPointError(f"Invalid finite_series.values={finite_series.values}") from ex
                elif len(finite_series) == 1:
                    self.column_to_min_max[column_name] = [finite_series.values[0], finite_series.values[0]]
                else:
                    self.column_to_min_max[column_name] = [None, None]

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
                        for c in (t[2] for t in self.target_columns)
                    }

                    self.reference_df = self.reference_df.copy()
                    for c, avg in self.reference_avg_by_column.items():
                        self.reference_df[c] -= avg
                    break
        else:
            self.reference_avg_by_column = None

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes
        a list of `enb.plotdata.PlottableData elements` for this case (group, column, render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        if kwargs["render_mode"] == "colormap":
            return self.compute_colormap_plottable_one_case(*args, **kwargs)
        else:
            raise ValueError(f"Invalid render mode {kwargs['render_mode']}")

    def compute_colormap_plottable_one_case(self, *args, **kwargs):
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        x_column_name, y_column_name, data_column_name = kwargs["column_selection"]
        try:
            data_column_label = kwargs["column_to_properties"][data_column_name].label
        except (TypeError, KeyError):
            data_column_label = enb.atable.clean_column_name(data_column_name)

        render_mode = kwargs["render_mode"]
        x_column_series = group_df[x_column_name].apply(float)
        y_column_series = group_df[y_column_name].apply(float)
        data_column_series = group_df[data_column_name].apply(float)

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(f"Invalid requested render mode {repr(render_mode)}")

        common_range = np.array(
            [list(self.column_to_min_max[x_column_name]), list(self.column_to_min_max[y_column_name])])

        histogram, x_edges, y_edges = np.histogram2d(
            x=x_column_series, y=y_column_series, density=False,
            range=common_range,
            weights=data_column_series, bins=self.analyzer.bin_count)

        counts, _, _ = np.histogram2d(
            x=x_column_series, y=y_column_series, density=False,
            range=common_range,
            bins=self.analyzer.bin_count)
        histogram /= np.clip(counts, 1, None)

        vmin = self.column_to_min_max[data_column_name][0]
        vmax = self.column_to_min_max[data_column_name][1]
        try:
            if kwargs["reference_group"]:
                reference_mean = self.reference_avg_by_column[data_column_name]
                vmin -= reference_mean
                vmax -= reference_mean
        except KeyError:
            pass

        histogram[counts == 0] = vmin - 1

        row[_column_name] = [enb.plotdata.Histogram2D(
            x_edges=x_edges, y_edges=y_edges, matrix_values=histogram,
            colormap_label=data_column_label,
            vmin=vmin,
            vmax=vmax,
            no_data_color=self.analyzer.no_data_color,
            color_map=self.analyzer.color_map)]


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
