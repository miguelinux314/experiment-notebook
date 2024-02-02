#!/usr/bin/env python3
"""Automatic analysis and report of pandas :class:`pandas.DataFrames` (e.g.,
produced by :class:`enb.experiment.Experiment` instances) using pyplot.

See https://miguelinux314.github.io/experiment-notebook/analyzing_data.html
for detailed help.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/01/01"

import ast
import functools
import os
import math
import collections
import collections.abc
import numbers
import re
import warnings
import numpy as np
import scipy.stats
import pandas as pd
import enb.atable
from enb.atable import clean_column_name
from enb import plotdata
from enb.config import options
from enb.experiment import TaskFamily


@enb.config.aini.managed_attributes
class Analyzer(enb.atable.ATable):
    """Base class for all enb analyzers.

    A |DataFrame| instance with analysis results can be obtained by calling
    get_df. In addition, if render_plots is used in that function, one or
    more figures will be produced. What plots are generated (if any) is based
    on the values of the self.selected_render_modes list, which must contain
    only elements in self.valid_render_modes.

    Data analysis is done through a surrogate
    :class:`enb.aanalysis.AnalyzerSummary` subclass, which is used to obtain
    the returned analysis results. Subclasses of
    :class:`enb.aanalysis.Analyzer` then perform any requested plotting.

    Rendering is performed for all modes contained
    self.selected_render_modes, which must be in self.valid_render_modes.

    The `@enb.config.aini.managed_attributes` decorator overwrites the class
    ("static") properties upon definition, with values taken from .ini
    configuration files. The decorator can be added to any Analyzer subclass,
    and parameters can be managed within the full-qualified name of the
    class, e.g., using a "[enb.aanalysis.Analyzer]" section header in any of
    the .ini files detected by enb.
    """
    # List of allowed rendering modes for the analyzer
    valid_render_modes = set()
    # Selected render modes (by default, all of them)
    selected_render_modes = set(valid_render_modes)
    # If more than one group is present, they are shown in the same subplot
    # instead of in different rows
    combine_groups = False

    # If not None, it must be a list of matplotlibrc styles (names or file paths)
    style_list = None
    # Default figure width
    fig_width = 5.0
    # Default figure height
    fig_height = 4.0
    # Relative horizontal margin added to plottable data in figures, e.g. 0.1 for a 10% margin
    horizontal_margin = 0
    # Relative vertical margin added to plottable data in figures, e.g. 0.1 for a 10% margin
    vertical_margin = 0
    # Margin between group rows (None to use matplotlib's default)
    group_row_margin = None
    # Padding between the global y label and the y axis (when present)
    global_y_label_margin = 15

    # Show grid lines at the major ticks?
    show_grid = False
    # Show grid lines at the minor ticks?
    show_subgrid = False
    # Transparency (between 0 and 1) of the main grid, if shown
    grid_alpha = 0.6
    # Transparency (between 0 and 1) of the subgrid, if shown
    subgrid_alpha = 0.4
    # Tick mark direction ("in", "out" or "inout")
    tick_direction = "in"

    # If applicable, show a horizontal +/- 1 standard deviation bar centered on the average
    show_x_std = False
    # If applicable, show a vertical +/- 1 standard deviation bar centered on the average
    show_y_std = False
    # If True, display group legends when applicable
    show_legend = True
    # Default number of columns inside the legend
    legend_column_count = 2
    # Legend position (if configured to be shown). It can be "title" to show it above the plot,
    # or any matplotlib-recognized argument for the loc parameter of legend()
    legend_position = "title"
    # If more than one group is displayed, when applicable, adjust plots to use the same scale in every subplot?
    common_group_scale = True

    # Main title to be displayed
    plot_title = None
    # Y position of the main title, if not None. If None, an attempt is automatically made
    # to avoid overlapping with the axes and legend
    title_y = None
    # Show the number of elements in each group?
    show_count = True
    # Show a group containing all elements?
    show_global = False
    # Name of the global group
    global_group_name = "All"
    # If a reference group is used as baseline, should it be shown in the analysis itself?
    show_reference_group = True

    # Main marker size
    main_marker_size = 4
    # Secondary (e.g., individual data) marker size
    secondary_marker_size = 2
    # Thickness of secondary plot lines
    secondary_line_width = 1
    # Main plot element alpha
    main_alpha = 0.5
    # Thickness of the main plot lines
    main_line_width = 2
    # Secondary plot element alpha (often overlaps with data using main_alpha)
    secondary_alpha = 0.3
    # If a semilog y axis is used, y_min will be at least this large to avoid math domain errors
    semilog_y_min_bound = 1e-5

    # Number of decimals used when showing decimal values in latex
    latex_decimal_count = 3

    def __init__(self, csv_support_path=None, column_to_properties=None,
                 progress_report_period=None):
        super().__init__(csv_support_path=csv_support_path,
                         column_to_properties=column_to_properties,
                         progress_report_period=progress_report_period)
        self.valid_render_modes = set(self.valid_render_modes)
        self.selected_render_modes = set(self.selected_render_modes)
        for mode in self.selected_render_modes:
            if mode not in self.valid_render_modes:
                raise SyntaxError(
                    f"Selected mode {repr(mode)} not in the "
                    f"list of available modes ({repr(self.valid_render_modes)}. "
                    f"(self.selected_render_modes = {self.selected_render_modes})")

    def get_df(self, full_df, target_columns,
               selected_render_modes=None,
               output_plot_dir=None, group_by=None, reference_group=None,
               column_to_properties=None,
               show_global=None, show_count=None, **render_kwargs):
        """
        Analyze a :class:`pandas.DataFrame` instance, optionally producing
        plots, and returning the computed dataframe with the analysis results.

        Rendering is performed for all modes contained
        self.selected_render_modes, which must be in self.valid_render_modes.
        You can pass additional parameters for rendering in render_kwargs,
        which will in turn be sent to enb.render.render_plds_by_group.

        You can use the @enb.aanalysis.Analyzer.normalize_parameters
        decorator when overwriting this method, to automatically transform
        None values into their defaults.

        :param full_df: full DataFrame instance with data to be plotted
          and/or analyzed.
        :param target_columns: columns to be analyzed. Typically, a list of
          column names, although each subclass may redefine the accepted format
          (e.g., pairs of column names). If None, all scalar, non string
          columns are used.
        :param selected_render_modes: a potentially empty list of mode names,
          all of which must be in self.valid_render_modes. Each mode represents
          a type of analysis or plotting. A single string can also be passed.
        :param group_by: if not None, the name of the column to be used for
          grouping.
        :param reference_group: if not None, the reference group name against
          which data are to be analyzed.
        :param output_plot_dir: path of the directory where the plot/plots
          is/are to be saved. If None, the default output plots path given by
          `enb.config.options` is used.
        :param column_to_properties: dictionary with ColumnProperties
          entries. ATable instances provide it in the
          :attr:`column_to_properties` attribute, :class:`Experiment` instances
          can also use the :attr:`joined_column_to_properties` attribute to
          obtain both the dataset and experiment's columns.
        :param show_global: if True, a group containing all elements is also
          included in the analysis. If None, self.show_count is used.
        :param show_count: if True or False, it determines whether the number
          of elements in each group is shown next to its name. If None,
          self.show_count is used.
        :param render_kwargs: additional parameters for rendering in render_kwargs,
          which will in turn be sent to enb.render.render_plds_by_group

        :return: a |DataFrame| instance with analysis results
        """
        # ATable get_df is not called here, the flag is changed to avoid incorrect warning messages
        self._was_get_df_called = True

        # pylint: disable=arguments-differ,too-many-arguments
        show_count = show_count if show_count is not None else self.show_count
        show_global = show_global if show_global is not None else self.show_global

        if self.csv_support_path is not None and os.path.exists(
                self.csv_support_path):
            # Analyzer classes store their persistence, but they erase when
            # get_df is called, so that analysis is always performed (which
            # is as expected, since the experiment results being analyzed
            # cannot be assumed to be the same as the previous invocation of
            # this analyzer's get_df method).
            os.remove(self.csv_support_path)
            enb.logger.debug(
                f"Removed {self.csv_support_path} to allow "
                f"re-analysis with {self.__class__.__name__}.")

        try:
            original_srm = self.selected_render_modes
            if isinstance(selected_render_modes, str):
                selected_render_modes = [selected_render_modes]
            srm = set(selected_render_modes if selected_render_modes else self.valid_render_modes)
            self.selected_render_modes = srm

            def normalized_wrapper(self, full_df, target_columns, output_plot_dir,
                                   selected_render_modes, group_by, reference_group,
                                   column_to_properties,
                                   **render_kwargs):
                # pylint: disable=too-many-arguments

                # Get the summary table with the requested data analysis
                enb.logger.info(f"Analyzing data with {self.__class__.__name__}...")
                summary_table = self.build_summary_atable(
                    full_df=full_df,
                    target_columns=target_columns,
                    group_by=group_by,
                    reference_group=reference_group,
                    include_all_group=show_global,
                    **render_kwargs)

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
                    target_columns=target_columns,
                    **render_kwargs)

                # Return the summary result dataframe
                return summary_df

            normalized_wrapper = self.__class__.normalize_parameters(
                fun=normalized_wrapper,
                group_by=group_by,
                column_to_properties=column_to_properties,
                target_columns=target_columns,
                reference_group=reference_group,
                output_plot_dir=output_plot_dir,
                selected_render_modes=selected_render_modes)

            return normalized_wrapper(self=self, full_df=full_df,
                                      show_count=show_count, **render_kwargs)
        finally:
            self.selected_render_modes = original_srm
            enb.logger.info("")

    def render_all_modes(
            self,
            # Dynamic arguments with every call
            summary_df, target_columns, output_plot_dir,
            reference_group, group_by, column_to_properties,
            # Arguments normalized by the
            # @enb.aanalysis.Analyzer.normalize_parameters, in turn
            # manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            selected_render_modes, show_global, show_count,
            # Rendering options, directly passed to
            # render.render_plds_by_group
            **render_kwargs):
        """Render all target modes and columns into output_plot_dir,
        with file names based on self's class name, the target column and the
        target render mode.

        Subclasses may overwrite their update_render_kwargs_one_case method
        to customize the rendering parameters that are passed to the parallel
        rendering function from enb.plotdata. These overwriting methods are
        encouraged to call
        `enb.aanalysis.Analyzer.update_render_kwargs_one_case` (directly or
        indirectly) so make sure all necessary parameters reach the rendering
        function.
        """
        # pylint: disable=too-many-arguments,too-many-locals
        # If plot rendering is requested, do so for all selected modes, in parallel
        render_ids = []
        for render_mode in selected_render_modes:
            for column_selection in target_columns:
                # The update_render_kwargs_one_case call should set all
                # rendering kwargs of interest. A call to Analyzer's or
                # super()'s update_render_kwargs_one_case is recommended to
                # guarantee consistency and minimize code duplicity. Also
                # note that column_selection may have different types (e.g.,
                # strings for column names, or tuples of column names, etc).
                column_kwargs = self.update_render_kwargs_one_case(
                    column_selection=column_selection, render_mode=render_mode,
                    reference_group=reference_group,
                    summary_df=summary_df,
                    output_plot_dir=output_plot_dir, group_by=group_by,
                    column_to_properties=column_to_properties,
                    show_global=show_global, show_count=show_count,
                    **(dict(render_kwargs or {})))

                if reference_group is not None:
                    self.update_render_kwargs_reference_group(column_kwargs,
                                                              reference_group)

                # All arguments to the parallel rendering function are ready;
                # their associated tasks as created
                render_ids.append(
                    enb.render.parallel_render_plds_by_group.start(
                        **dict(column_kwargs)))

        # Wait until all rendering tasks are done while updating about progress
        with enb.logger.debug_context(
                f"Rendering {len(render_ids)} plots with "
                f"{self.__class__.__name__}...\n"):
            if not enb.progress.is_progress_enabled():
                # Silent processing
                for _ in enb.parallel.ProgressiveGetter(
                        id_list=render_ids,
                        iteration_period=self.progress_report_period,
                        alive_bar=None):
                    pass
                enb.parallel.get(render_ids)
            else:
                # Rich progress reporting
                with enb.progress.ProgressTracker(self, len(render_ids), len(render_ids)) as progress_tracker:
                    progressive_getter = enb.parallel.ProgressiveGetter(
                        id_list=render_ids,
                        iteration_period=self.progress_report_period,
                        alive_bar=None)
                    for _ in progressive_getter:
                        progress_tracker.update_chunk_completed_rows(len(progressive_getter.completed_ids))
                    enb.parallel.get(render_ids)
                    progress_tracker.complete_chunk() # A single chunk is employed
                    progress_tracker.update_chunk_completed_rows(0)

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the
            # @enb.aanalysis.Analyzer.normalize_parameters, in turn manageable
            # through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to plotdata.render_plds_by_group
            **column_kwargs):
        """Update column_kwargs with the desired rendering arguments for this
        column and render mode. Return the updated dict.
        """
        # pylint: disable=too-many-arguments,unused-argument,too-many-branches
        if isinstance(column_selection, collections.abc.Iterable):
            all_columns = []
            for column in column_selection:
                if isinstance(column, str):
                    all_columns.append(column)
                elif isinstance(column, collections.abc.Iterable):
                    all_columns.extend(column)

            if not all(isinstance(column, str) for column in all_columns):
                raise ValueError(
                    f"Invalid column_selection={repr(column_selection)}. "
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
            in sorted(summary_df[["group_label",
                                  f"{column_selection}_render-{render_mode}"]].values,
                      key=lambda tup: tup[0])
            if self.show_reference_group or group_label != reference_group}

        # General column properties
        if "column_properties" not in column_kwargs:
            try:
                column_kwargs["column_properties"] = column_to_properties[
                    column_selection]
            except (KeyError, TypeError):
                column_kwargs[
                    "column_properties"] = enb.atable.ColumnProperties(
                    name=column_selection)

        # Generate some labels
        if "y_labels_by_group_name" not in column_kwargs or column_kwargs[
            "y_labels_by_group_name"] is None:
            column_kwargs["y_labels_by_group_name"] = {
                group: f"{group} ({count})" if show_count else f"{group}"
                for group, count in
                summary_df[["group_label", "group_size"]].values}
        if "plot_title" not in column_kwargs:
            column_kwargs["plot_title"] = self.plot_title
        if "title_y" not in column_kwargs:
            column_kwargs["title_y"] = self.title_y

        # Control group division and labeling
        if "combine_groups" not in column_kwargs:
            column_kwargs["combine_groups"] = self.combine_groups
        if "show_legend" not in column_kwargs:
            column_kwargs["show_legend"] = self.show_legend
        if "legend_position" not in column_kwargs:
            column_kwargs["legend_position"] = self.legend_position
        if self.style_list is not None:
            column_kwargs["style_list"] = self.style_list
        if "global_y_label_margin" not in column_kwargs:
            column_kwargs["global_y_label_margin"] = self.global_y_label_margin

        # Reference (baseline) group
        if "show_reference_group" in column_kwargs:
            self.show_reference_group = column_kwargs["show_reference_group"]
            del column_kwargs["show_reference_group"]

        # Grids, subgrids, tick formatting
        for attr in ("show_grid", "show_subgrid", "grid_alpha", "subgrid_alpha", "tick_direction"):
            if attr not in column_kwargs:
                column_kwargs[attr] = getattr(self, attr)

        return column_kwargs

    def update_render_kwargs_reference_group(
            self, column_kwargs, reference_group):
        """Update the default render kwargs dir when a reference group
        is selected.
        """
        assert reference_group is not None
        filtered_plds = column_kwargs["pds_by_group_name"]
        if not self.show_reference_group:
            filtered_plds = {k: v
                             for k, v in column_kwargs[
                                 "pds_by_group_name"].items()
                             if k != reference_group}

            if reference_group not in column_kwargs[
                "pds_by_group_name"]:
                enb.logger.debug(f"Requested reference_group "
                                 f"{repr(reference_group)} not found.")
            column_kwargs["pds_by_group_name"] = filtered_plds
            if "group_name_order" in column_kwargs and \
                    column_kwargs["group_name_order"]:
                column_kwargs["group_name_order"] = \
                    [n for n in column_kwargs["group_name_order"]
                     if n != reference_group]
        if "combine_groups" in column_kwargs and column_kwargs[
            "combine_groups"] is True \
                and "reference_group" in column_kwargs and \
                column_kwargs["reference_group"] is not None:
            for i, name in enumerate(filtered_plds.keys()):
                if i > 0:
                    column_kwargs["pds_by_group_name"][name] = [
                        pld for pld in
                        column_kwargs["pds_by_group_name"][name]
                        if not isinstance(pld, plotdata.VerticalLine)
                           or pld.x_position != 0]
        try:
            column_kwargs["group_name_order"] = [
                n for n in column_kwargs["group_name_order"]
                if n != reference_group]
        except KeyError:
            pass


    def get_output_pdf_path(self, column_selection, group_by, reference_group,
                            output_plot_dir, render_mode):
        """Get the path of the PDF file to be created for a single
        parameter selection.
        """
        # pylint: disable=too-many-arguments
        if isinstance(column_selection, str):
            column_selection_str = f"{column_selection}"
        elif isinstance(column_selection, collections.abc.Iterable):
            if all(isinstance(s, str) for s in column_selection):
                column_selection_str = f"columns_{'__'.join(column_selection)}"
                if len(column_selection_str) > 150:
                    # Excessively long. Show an abbreviated form
                    column_selection_str = \
                        f"{len(column_selection)}column" \
                        f"{'s' if len(column_selection) > 1 else ''}"
            else:
                column_selection_str = \
                    "columns_" + \
                    f"{'__'.join('__vs__'.join(cs) for cs in column_selection)}"
                if len(column_selection_str) > 150:
                    # Excessively long. Show an abbreviated form
                    column_selection_str = f"{len(column_selection)}columns"
        else:
            raise ValueError(
                f"Column selection {column_selection} not supported")

        return os.path.join(
            output_plot_dir,
            f"{self.__class__.__name__}-"
            f"{column_selection_str}-{render_mode}" +
            (f"-groupby__{get_groupby_str(group_by=group_by)}" if group_by else "") +
            (f"-referencegroup__{reference_group}" if reference_group else "") +
            ".pdf")

    def save_analysis_tables(
            self, group_by, reference_group,
            selected_render_modes, summary_df, summary_table,
            target_columns, **render_kwargs):
        """Save csv and tex files into enb.config.options.analysis_dir that
        summarize the results of one target_columns element. If
        enb.config.options.analysis_dir is None or empty, no analysis is
        performed.

        By default, the CSV contains the min, max, avg, std, and median of each
        group. Subclasses may overwrite this behavior.
        """
        # pylint: disable=too-many-arguments
        if options.analysis_dir:
            # Generate full csv summary
            try:
                render_mode_str = "__".join(selected_render_modes)
            except TypeError:
                render_mode_str = str(render_mode_str).replace(os.sep, "__")
            analysis_output_path = self.get_output_pdf_path(
                column_selection=target_columns,
                group_by=group_by,
                reference_group=reference_group,
                output_plot_dir=options.analysis_dir,
                render_mode=render_mode_str)[:-4] + ".csv"
            enb.logger.debug(
                f"Saving analysis results to {analysis_output_path}")
            os.makedirs(os.path.dirname(analysis_output_path), exist_ok=True)

            # Save CSV analysis
            summary_df[list(
                c for c in summary_df.columns
                if c not in summary_table.render_column_names
                and c not in ["row_created", "row_updated",
                              enb.atable.ATable.private_index_column])].to_csv(
                analysis_output_path, index=False)

            # Generate tex summary
            show_count = "show_count" in render_kwargs and render_kwargs["show_count"] is True
            summary_df[list(
                c for c in summary_df.columns
                if c not in summary_table.render_column_names
                and c not in ["row_created", "row_updated",
                              enb.atable.ATable.private_index_column]
                and (c in ("group_label", "group_size" if show_count else "")
                     or c.endswith("_avg")))].style.format(
                escape="latex",
                precision=self.latex_decimal_count).format_index(
                r"\textbf{{ {} }}", escape="latex", axis=1).hide(
                axis="index").to_latex(
                analysis_output_path[:-4] + ".tex")

    @classmethod
    def normalize_parameters(cls, fun, group_by, column_to_properties,
                             target_columns, reference_group,
                             output_plot_dir, selected_render_modes):
        """Optional decorator methods compatible with the Analyzer.get_df
        signature, so that managed attributes are used when

        This way, users may overwrite most adjustable arguments
        programmatically, or via .ini configuration files.
        """
        # pylint: disable=too-many-arguments
        column_to_properties = column_to_properties if column_to_properties is not None \
            else collections.OrderedDict()

        @functools.wraps(fun)
        def wrapper(self,
                    # Dynamic arguments with every call (full_df and group_by
                    # are not normalized)
                    full_df, target_columns=target_columns,
                    reference_group=reference_group,
                    output_plot_dir=output_plot_dir,
                    # Arguments normalized by the
                    # @enb.aanalysis.Analyzer.normalize_parameters, in turn
                    # manageable through .ini configuration files via the
                    # @enb.config.aini.managed_attributes decorator.
                    selected_render_modes=selected_render_modes,
                    show_global=None, show_count=True, plot_title=None,
                    # Rendering options, directly passed to
                    # render_plds_by_group
                    **render_kwargs):
            # pylint: disable=too-many-arguments
            selected_render_modes = selected_render_modes if selected_render_modes is not None \
                else cls.selected_render_modes

            if target_columns is None:
                target_columns = [c for c in full_df.columns if
                                  isinstance(full_df.iloc[0][c],
                                             numbers.Number)]
                if not target_columns:
                    raise ValueError(
                        f"Cannot find any numeric columns in "
                        f"{repr(full_df.columns)} and no specific "
                        f"column was chosen")
            elif isinstance(target_columns, str):
                target_columns = [target_columns]

            output_plot_dir = output_plot_dir if output_plot_dir is not None \
                else enb.config.options.plot_dir
            show_global = show_global if show_global is not None else cls.show_global
            show_count = show_count if show_count is not None else cls.show_count
            plot_title = plot_title if plot_title is not None else cls.plot_title

            for column in full_df.columns:
                if column not in column_to_properties:
                    column_to_properties[column] = enb.atable.ColumnProperties(
                        clean_column_name(column))

            return fun(self=self, full_df=full_df,
                       reference_group=reference_group,
                       selected_render_modes=selected_render_modes,
                       target_columns=target_columns,
                       output_plot_dir=output_plot_dir,
                       show_global=show_global, show_count=show_count,
                       group_by=group_by,
                       column_to_properties=column_to_properties,
                       plot_title=plot_title,
                       **render_kwargs)

        return wrapper

    @classmethod
    def adjust_common_row_axes(cls, column_kwargs, column_selection,
                               render_mode, summary_df):
        """When self.common_group_scale is True, this method is called to
        make all groups (rows) use the same scale.
        """
        global_x_min = float("inf")
        global_x_max = float("-inf")
        global_y_min = float("inf")
        global_y_max = float("-inf")
        for pld_list in summary_df[f"{column_selection}_render-{render_mode}"]:
            for pld in pld_list:
                try:
                    global_x_min = min(global_x_min, min(pld.x_values) if len(
                        pld.x_values) > 0 else global_x_min)
                    global_x_max = max(global_x_max, max(pld.x_values) if len(
                        pld.x_values) > 0 else global_x_max)
                except TypeError:
                    global_x_min = 0
                    global_x_max = max(global_x_max, len(pld.x_values))
                except AttributeError:
                    assert not isinstance(pld, plotdata.PlottableData2D)
                try:
                    global_y_min = min(global_y_min, min(pld.y_values) if len(
                        pld.y_values) > 0 else global_y_min)
                    global_y_max = max(global_y_max, max(pld.y_values) if len(
                        pld.y_values) > 0 else global_y_max)
                except AttributeError:
                    assert not isinstance(pld, plotdata.PlottableData2D)
        if "y_min" not in column_kwargs:
            column_kwargs["y_min"] = global_y_min
        if "y_max" not in column_kwargs:
            column_kwargs["y_max"] = global_y_max

    def build_summary_atable(self, full_df, target_columns, reference_group,
                             group_by, include_all_group, **render_kwargs):
        """Build a :class:`enb.aanalysis.AnalyzerSummary` instance with the
        appropriate columns to perform the intended analysis. See
        :class:`enb.aanalysis.AnalyzerSummary` for documentation on the
        meaning of each argument.

        :param full_df: dataframe instance being analyzed
        :param target_columns: list of columns specified for analysis
        :param reference_group: if not None, the column or group to be used as
          baseline in the analysis
        :param include_all_group: force inclusion of an "All" group with all
          samples
        :param render_kwargs: additional keyword arguments passed to get_df for adjusting
          the rendering process. They can be used, but are not typically needed,
          for implementing the summary table's methods.
          See :class:`enb.aanalysis.get_df` for details.

        :return: the built summary table, without having called its get_df method.
        """
        # pylint: disable=too-many-arguments
        raise SyntaxError(
            f"Subclasses must implement this method. {self.__class__} did not. "
            f"Typically, the associated AnalyzerSummary needs to be "
            f"instantiated and returned. See enb.aanalysis.Analyzer's documentation.")

    def get_render_column_name(self, column_selection, selected_render_mode):
        """Return the canonical name for columns containing plottable data instances.
        """
        # pylint: disable=no-self-use
        return f"{column_selection}_render-{selected_render_mode}"


class AnalyzerSummary(enb.atable.SummaryTable):
    """Base class for the surrogate, dynamic summary tables employed by
    :class:`enb.aanalysis.Analyzer` subclasses to gather analysis results and
    plottable data (when configured to do so).
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group,
                 group_by, include_all_group, **render_kwargs):
        """Dynamically generate the needed analysis columns and any other
        needed attributes for the analysis.

        Columns that generate plottable data are automatically defined defined
        using self.render_target, based on the analyzer's selected render modes.

        Plot rendering columns are added automatically via this call,
        with associated function self.render_target with partialed parameters
        column_selection and render_mode.

        Subclasses are encouraged to call `self.move_render_columns_back()` to
        make sure rendering columns are processed after any other intermediate
        column defined by the subclass.

        :param analyzer: :class:`enb.aanalysis.Analyzer` subclass instance
          corresponding to this summary table.
        :param full_df: full dataframe specified for analysis.
        :param target_columns: columns for which an analysis is being requested.
        :param reference_group: if not None, it must be the name of one group,
          which is used as baseline. Different subclasses may implement this in
          different ways.
        :param group_by: grouping configuration for this summary. See the specific
          subclass help for more inforamtion.
        :param include_all_group: if True, an "All" group with all input samples
          is included in the analysis.
        """
        # pylint: disable=too-many-arguments
        # Note that csv_support_path is set to None to force computation of the
        # analysis every call, instead of relying on persistence (it would make no
        # sense to load the summary for a different input dataset).
        super().__init__(full_df=full_df,
                         column_to_properties=analyzer.column_to_properties,
                         copy_df=False,
                         csv_support_path=analyzer.csv_support_path,
                         group_by=group_by,
                         include_all_group=(
                             include_all_group if include_all_group is not None
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
        """Add to column_to_properties the list of columns used to compute
        instances from the plotdata module. :return the list of column names
        added in this call:
        """
        render_column_names = []
        for selected_render_mode in self.analyzer.selected_render_modes:
            for column_selection in self.target_columns:
                render_column_name = self.analyzer.get_render_column_name(
                    column_selection, selected_render_mode)
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
            self.group_by = self.group_by if not is_family_grouping(
                self.group_by) else "family_label"
            return super().split_groups(reference_df=reference_df,
                                        include_all_group=include_all_group)
        finally:
            self.group_by = original_group_by

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function (after "partialing"-out "column_selection"
        and "render_mode"), that computes the list of
        plotdata.PlottableData instances that represent one group,
        one target column and one render mode.

        Subclasses must implement this method.

        :param args: render configuration arguments is expected to contain
          values for the signature (self, group_label, row)
        :param kwargs: dict with at least the "column_selection" and
          "render_mode" parameters.
        """
        # The following snippet can be used in overwriting implementations of
        # render_target.
        _self, group_label, row = args  # pylint: disable=unused-variable
        column_selection = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        if render_mode not in self.analyzer.valid_render_modes:
            raise ValueError(
                f"Invalid requested render mode {repr(render_mode)}")

        raise SyntaxError(
            f"Subclasses must implement this method, "
            f"which should set row[_column_name] "
            f"to a list of enb.plotdata.PlottableData instances. "
            f"{self.__class__.__name__} did not "
            f"(group_label={group_label}, "
            f"column_selection={repr(column_selection)}, "
            f"render_mode={repr(render_mode)}).")

    def move_render_columns_back(self):
        """Reorder the column definitions so that rendering columns are
        attempted after any column the subclass may have defined.
        """
        column_to_properties = collections.OrderedDict()
        for k, v in ((k, v) for k, v in self.column_to_properties.items() if
                     k not in self.render_column_names):
            column_to_properties[k] = v
        for k in self.render_column_names:
            column_to_properties[k] = self.column_to_properties[k]
        self.column_to_properties = column_to_properties

    def apply_reference_bias(self):
        """By default, no action is performed relative to the presence of a
        reference group, and not bias is introduced in the dataframe.
        Subclasses may overwrite this.
        """
        if self.reference_group:
            enb.logger.warn(
                f"A reference group {repr(self.reference_group)} is selected "
                f"but {self.__class__} does not implement "
                f"its apply_reference_bias method.")

    def remove_nans(self, column_series):
        """Remove the infinite and NaN values from a pd.Series instance.
        """
        # pylint: disable=no-self-use
        return column_series.replace([np.inf, -np.inf], np.nan,
                                     inplace=False).dropna()


def is_family_grouping(group_by):
    """Return True if and only if group_by is an iterable of one or more
    enb.experiment.TaskFamily instances.
    """
    try:
        return all(isinstance(e, TaskFamily) for e in group_by)
    except TypeError:
        return False


def get_groupby_str(group_by):
    """Return a string identifying the group_by method.
    If None, 'None' is returned.
    If a string is passed, it is returned.
    If a list of strings is passed, it is formatted adding two underscores as
    separation.
    If grouping by family was requested, 'family_label' is returned.
    """
    if not group_by:
        return "None"
    if is_family_grouping(group_by=group_by):
        return "family_label"
    if isinstance(group_by, str):
        return group_by
    if isinstance(group_by, collections.abc.Iterable) \
            and all(isinstance(s, str) for s in group_by):
        return "__".join(group_by)

    raise ValueError(group_by)


@enb.config.aini.managed_attributes
class ScalarNumericAnalyzer(Analyzer):
    """Analyzer subclass for scalar columns with numeric values.
    """
    # The following attributes are directly used for analysis/plotting,
    # and can be modified before any call to get_df. These values may be
    # updated based on .ini files, see the documentation of the
    # enb.config.aini.managed_attributes decorator for more information.
    # Common analyzer attributes:
    valid_render_modes = {"histogram", "hbar", "boxplot"}
    selected_render_modes = set(valid_render_modes)
    plot_title = None
    title_y = None
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
            # Rendering options, directly passed to render_plds_by_group
            **column_kwargs):
        """Update column_kwargs with the desired rendering arguments for this column
        and render mode. Return the updated dict.
        """
        # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
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
            self.get_render_column_name(column_selection=column_selection,
                                        selected_render_mode=render_mode)]

        if render_mode == "histogram":
            group_avg_tuples = []
            for group, plds in plds_by_group.items():
                try:
                    group_avg_tuples.append(
                        (group, [p.x_values[0] for p in plds if
                                 isinstance(p, plotdata.ScatterData)][0]))
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
                    group_avg_tuples.append(
                        (group, [p.x_values[0] for p in plds
                                 if isinstance(p, plotdata.ErrorLines)][0]))
                except IndexError:
                    # Empty group
                    group_avg_tuples.append((group, 0))
        else:
            raise ValueError(f"Unsupported render mode {render_mode}")

        if self.sort_by_average:
            column_kwargs["group_name_order"] = []
            for tup in sorted(group_avg_tuples, key=lambda tup: tup[1]):
                group_name = tup[0]
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

    def update_render_kwargs_one_case_histogram(
            self, column_selection,
            reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the
            # @enb.aanalysis.Analyzer.normalize_parameters, in turn
            # manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to
            # render_plds_by_group
            **column_kwargs):
        """Update rendering kwargs (e.g., labels) specifically for the
        histogram mode.
        """
        # pylint: disable=unused-argument
        # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
        # Update specific rendering kwargs for this analyzer:
        if "global_x_label" not in column_kwargs:
            if self.main_alpha <= 0 or self.bar_width_fraction <= 0:
                column_kwargs[
                    "global_x_label"] = \
                    f"Average {column_to_properties[column_selection].label}"
            else:
                column_kwargs["global_x_label"] = column_to_properties[
                    column_selection].label

            if reference_group is not None:
                column_kwargs["global_x_label"] += f" difference vs. {reference_group}"

        if "global_y_label" not in column_kwargs:
            if self.main_alpha > 0 and self.bar_width_fraction > 0:
                column_kwargs["global_y_label"] = "Histogram"
                if self.secondary_alpha != 0:
                    column_kwargs["global_y_label"] += ", average" \
                        if self.show_x_std else " and average"
            elif self.secondary_alpha != 0:
                column_kwargs["global_y_label"] = "Average"
            else:
                enb.logger.warn(f"Plotting with {self.__class__.__name__} "
                                "and both bar_alpha and secondary_alpha "
                                "set to zero. Expect an empty-looking plot.")
            if self.show_x_std:
                column_kwargs["global_y_label"] += r" and $\pm 1\sigma$"

            if self.main_alpha <= 0 or self.bar_width_fraction <= 0:
                column_kwargs["global_y_label"] = ""

        if self.main_alpha <= 0 or self.bar_width_fraction <= 0:
            column_kwargs["y_tick_list"] = []
            column_kwargs["y_tick_label_list"] = []

        # Calculate axis limits
        if "x_min" not in column_kwargs:
            column_kwargs["x_min"] = float(
                summary_df[f"{column_selection}_min"].min()) \
                if column_to_properties[column_selection].plot_min is None else \
                column_to_properties[column_selection].plot_min
        if "x_max" not in column_kwargs:
            column_kwargs["x_max"] = float(
                summary_df[f"{column_selection}_max"].max()) \
                if column_to_properties[column_selection].plot_max is None else \
                column_to_properties[column_selection].plot_max

        # Adjust a common scale for all subplots
        if self.common_group_scale and (
                "y_min" not in column_kwargs or "y_max" not in column_kwargs):
            with enb.logger.debug_context(
                    f"Adjusting common group scale for {repr(column_selection)}"):
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
            # pylint: disable=unused-variable
            for (group_name, group_pds), pattern in zip(
                    sorted(column_kwargs["pds_by_group_name"].items()),
                    enb.render.pattern_cycle):
                for pld in group_pds:
                    if isinstance(pld, plotdata.BarData):
                        pld.pattern = pattern

            column_kwargs["global_y_label"] = "Relative frequency"

        # Add the reference vertical line at x=0 if needed
        if reference_group:
            for name, pds in column_kwargs["pds_by_group_name"].items():
                if self.show_reference_group or name != reference_group:
                    pds.append(plotdata.VerticalLine(x_position=0, alpha=0.3,
                                                     color="black"))

        return column_kwargs

    def update_render_kwargs_one_case_hbar(
            self, column_selection,
            reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the
            # @enb.aanalysis.Analyzer.normalize_parameters, in turn
            # manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to
            # render_plds_by_group
            **column_kwargs):
        """Update rendering kwargs (e.g., labels) specifically for the hbarmode.
        """
        # pylint: disable=too-many-arguments,unused-argument,too-many-locals
        if "global_x_label" not in column_kwargs:

            column_kwargs["global_x_label"] = column_to_properties[
                column_selection].label
            if reference_group is not None:
                column_kwargs["global_x_label"] += f" difference vs. {reference_group}"

        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = ""

        # Calculate axis limits
        if "x_min" not in column_kwargs:
            column_kwargs["x_min"] = float(
                summary_df[f"{column_selection}_min"].min()) \
                if column_to_properties[column_selection].plot_min is None else \
                column_to_properties[column_selection].plot_min
        if "x_max" not in column_kwargs:
            column_kwargs["x_max"] = float(
                summary_df[f"{column_selection}_max"].max()) \
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
                    plotdata.VerticalLine(x_position=0, alpha=0.3,
                                          color="black"))

        column_kwargs["y_tick_list"] = list(
            range(len(column_kwargs["pds_by_group_name"])))
        column_kwargs["y_tick_label_list"] = list(
            column_kwargs["y_labels_by_group_name"][name]
            if "y_labels_by_group_name" in column_kwargs and name in
               column_kwargs["y_labels_by_group_name"]
            else name for name in column_kwargs["pds_by_group_name"].keys())

        column_kwargs["y_min"] = -0.5
        column_kwargs["y_max"] = len(
            column_kwargs["pds_by_group_name"]) - 1 + 0.5
        column_kwargs["show_legend"] = False

        column_kwargs["fig_height"] = 0.5 + 0.5 * len(
            column_kwargs["pds_by_group_name"])

        return column_kwargs

    def update_render_kwargs_one_case_boxplot(
            self, column_selection,
            reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the
            # @enb.aanalysis.Analyzer.normalize_parameters, in turn
            # manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to plotdata.render_plds_by_group
            **column_kwargs):
        """Update rendering kwargs (e.g., labels) specifically for the
        boxplot mode.
        """
        # pylint: disable=unused-argument
        # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
        if "global_x_label" not in column_kwargs:
            column_kwargs["global_x_label"] = column_to_properties[
                column_selection].label
            if reference_group is not None:
                column_kwargs["global_x_label"] += f" difference vs. {reference_group}"

        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = ""

        # Calculate axis limits
        forced_xmin = "x_min" in column_kwargs \
                      and column_kwargs["x_min"] is not None
        forced_xmax = "x_max" in column_kwargs \
                      and column_kwargs["x_max"] is not None
        if "x_min" not in column_kwargs:
            column_kwargs["x_min"] = float(
                summary_df[f"{column_selection}_min"].min()) \
                if column_to_properties[column_selection].plot_min is None else \
                column_to_properties[column_selection].plot_min
        if "x_max" not in column_kwargs:
            column_kwargs["x_max"] = float(
                summary_df[f"{column_selection}_max"].max()) \
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
                # All elements of a group are aligned along the same
                # horizontal position
                pld.y_values = [i] * len(pld.y_values)
            if reference_group and \
                    (self.show_reference_group or name != reference_group):
                column_kwargs["pds_by_group_name"][name].append(
                    plotdata.VerticalLine(
                        x_position=0, alpha=0.3, color="black"))

        column_kwargs["y_tick_list"] = list(
            range(len(column_kwargs["pds_by_group_name"])))
        column_kwargs["y_tick_label_list"] = list(
            column_kwargs["y_labels_by_group_name"][name]
            if "y_labels_by_group_name" in column_kwargs and name in
               column_kwargs["y_labels_by_group_name"]
            else name for name in column_kwargs["pds_by_group_name"].keys())

        column_kwargs["y_min"] = -0.5
        column_kwargs["y_max"] = len(
            column_kwargs["pds_by_group_name"]) - 1 + 0.5
        column_kwargs["show_legend"] = False

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, reference_group,
                             group_by, include_all_group, **render_kwargs):
        """Dynamically build a SummaryTable instance for scalar value analysis.
        """
        # pylint: disable=too-many-arguments
        return ScalarNumericSummary(analyzer=self, full_df=full_df,
                                    target_columns=target_columns,
                                    reference_group=reference_group,
                                    group_by=group_by,
                                    include_all_group=include_all_group)


class ScalarNumericSummary(AnalyzerSummary):
    """Summary table used in ScalarValueAnalyzer, defined dynamically with
    each call to maintain independent column definitions.

    Note that dynamically in this context implies that modifying the returned
    instance's class columns does not affect the definition of other
    instances of this class.

    Note that in most cases, the columns returned by default should suffice.

    If a reference_group is provided, its average is computed and subtracted
    from all values when generating the plot.
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group,
                 group_by, include_all_group):
        # pylint: disable=too-many-arguments
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_selection and render_mode.
        AnalyzerSummary.__init__(
            self=self,
            analyzer=analyzer, full_df=full_df, target_columns=target_columns,
            reference_group=reference_group, group_by=group_by,
            include_all_group=include_all_group)
        self.column_to_xmin_xmax = {}

        for column_name in target_columns:
            if column_name not in full_df.columns:
                raise ValueError(
                    f"Invalid column name selection {repr(column_name)}. "
                    f"Full selection: {repr(target_columns)}")

            # Get the finite-only data from each column
            finite_series = full_df[column_name].replace([np.inf, -np.inf],
                                                         np.nan,
                                                         inplace=False).dropna()

            if len(finite_series.values) == 0:
                enb.logger.warn(
                    f"Column {column_name} did not contain any finite value. "
                    f"Analysis tables and plots will be meaningless.")

            # Compute the global dynamic range of all input samples (before
            # grouping)
            self.column_to_xmin_xmax[column_name] = (
                min(finite_series.values), max(finite_series.values)) \
                if len(finite_series.values) > 0 else (0, 0)
            # Add columns that compute the summary information
            self.add_scalar_description_columns(column_name=column_name)

        self.move_render_columns_back()

    def apply_reference_bias(self):
        """Compute the average value of the reference group for each target
        column and subtract it from the dataframe being analyzed. If not
        reference group is present, no action is performed.
        """
        if self.reference_group is not None:
            if self.group_by is None:
                raise ValueError(
                    f"Cannot use a not-None reference_group if group_by is None "
                    f"(here is {repr(self.reference_group)})")

            for group_label, group_df in self.split_groups():
                if group_label == self.reference_group:
                    self.reference_avg_by_column = {
                        c: group_df[group_df[c].notna()][c].mean()
                        for c in self.target_columns
                    }

                    self.reference_df = self.reference_df.copy()
                    for column, avg in self.reference_avg_by_column.items():
                        self.reference_df[column] -= avg
                    break
            else:
                found_groups_str = ','.join(
                    repr(label) for label, _ in self.split_groups(
                        reference_df=self.reference_df,
                        include_all_group=self.include_all_group))
                raise ValueError(f"Cannot find {self.reference_group} "
                                 f"among defined groups ({found_groups_str})")
        else:
            self.reference_avg_by_column = None

    def add_scalar_description_columns(self, column_name):
        """Add the scalar description columns for a given column_name in the
        |DataFrame| instance being analyzed.
        """
        for descriptor in ["min", "max", "avg", "std", "median", "count"]:
            self.add_column_function(
                self,
                fun=functools.partial(self.set_scalar_description,
                                      column_selection=column_name),
                column_properties=enb.atable.ColumnProperties(
                    name=f"{column_name}_{descriptor}",
                    label=f"{column_name}: {descriptor}"))

    def set_scalar_description(self, *args, **kwargs):
        """Set basic descriptive statistics for the target column
        """
        _self, group_label, row = args
        column_name = kwargs["column_selection"]
        full_series = _self.label_to_df[group_label][column_name]
        for stat, value in _self.numeric_series_to_stat_dict(full_series, group_label=group_label).items():
            row[f"{column_name}_{stat}"] = value

    def numeric_series_to_stat_dict(self, series: pd.Series, group_label: str=None):
        """Convert a series of numeric data into a dictionary of
        stats ('avg', 'min', 'max', 'std', 'count').

        :param series: series of numeric scalar data to be analyzed.
          Infinite and nan values are removed before processing.
        :return: a dictionary of stats for `series`.
        """
        finite_series = self.remove_nans(series)

        if len(series) != len(finite_series):
            if len(finite_series) > 0:
                enb.logger.warn(
                    f"{self.__class__.__name__}: "
                    f"set_scalar_description is ignoring infinite or NaN values "
                    f"({100 * (1 - len(finite_series) / len(series)):.2f}%"
                    f" of the total)"
                    f"{' for ' + repr(group_label) if group_label else ''}.")
            else:
                enb.logger.warn(
                    f"{self.__class__.__name__}: "
                    f"set_scalar_description found only infinite or NaN values"
                    f"{' for ' + repr(group_label) if group_label else ''}. "
                    f"Several statistics will be 0 for this case.")

        stat_dict = dict()

        stat_dict["count"] = len(finite_series)

        if len(np.unique(finite_series.values)) > 1:
            description_df = finite_series.describe()
            stat_dict["min"] = description_df["min"]
            stat_dict["max"] = description_df["max"]
            stat_dict["avg"] = description_df["mean"]
            stat_dict["std"] = description_df["std"]
            stat_dict["median"] = description_df["50%"]
        elif len(finite_series.values) > 0:
            stat_dict["min"] = finite_series.values[0]
            stat_dict["max"] = finite_series.values[0]
            stat_dict["avg"] = finite_series.values[0]
            stat_dict["std"] = 0
            stat_dict["median"] = finite_series.values[0]
        else:
            stat_dict["min"] = 0
            stat_dict["max"] = 0
            stat_dict["avg"] = 0
            stat_dict["std"] = 0
            stat_dict["median"] = 0

        return stat_dict

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes a list of
        `enb.plotdata.PlottableData elements` for this case
        (group, column, render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        if kwargs["render_mode"] == "histogram":
            return self.compute_histogram_plottable_one_case(*args, **kwargs)
        if kwargs["render_mode"] == "hbar":
            return self.compute_hbar_plottable_one_case(*args, **kwargs)
        if kwargs["render_mode"] == "boxplot":
            return self.compute_boxplot_plottable_one_case(*args, **kwargs)

        raise ValueError(f"Invalid render mode {kwargs['render_mode']}")

    def compute_histogram_plottable_one_case(self, *args, **kwargs):
        """Compute the list of `enb.plotdata.PlottableData elements` for
        a single render mode.
        """
        # pylint: disable=unused-argument,too-many-locals,too-many-branches
        # pylint: disable=too-many-statements
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        column_series = group_df[column_name].copy()

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(
                f"Invalid requested render mode {repr(render_mode)}")
        assert render_mode == "histogram"

        # Set the analysis range based on column properties if provided,
        # or the data's dynamic range.
        try:
            analysis_range = [
                _self.analyzer.column_to_properties[column_name].plot_min,
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
            enb.logger.warn(
                f"{_self.__class__.__name__}, {render_mode}: "
                f"No finite data found for column {repr(column_name)}"
                f"{' for ' + repr(group_label) if group_label else ''}. "
                f"No plottable data is produced for this case.")
            row[_column_name] = []
            # return

        if math.isinf(analysis_range[0]):
            analysis_range[0] = finite_only_series.min()
        if math.isinf(analysis_range[1]):
            analysis_range[1] = finite_only_series.max()

        # Use numpy to obtain the absolute mass distribution of the data.
        # density=False is used so that we can detect the case where some
        # data is not used.
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
            error_msg = f"Not all samples are included in the scalar " \
                        f"value histogram for {column_name} " \
                        f"({sum(hist_y_values)} used out of {len(column_series)}). " \
                        f"The used range was [{analysis_range[0]}, {analysis_range[0]}]."
            if math.isinf(row[f"{column_name}_min"]) or math.isinf(
                    row[f"{column_name}_max"]):
                error_msg += " Note that infinite values have been found " \
                             "in the column, which are not included " \
                             "in the analysis."
                justified_difference = True
            if analysis_range[0] > row[f"{column_name}_min"] or analysis_range[
                1] < row[
                f"{column_name}_max"]:
                error_msg += " This is likely explained by the " \
                             "plot_min/plot_max or y_min/y_max " \
                             "values set for this analysis."
                justified_difference = True
            if justified_difference:
                enb.log.info(error_msg)
            else:
                raise ValueError(error_msg)

        row[_column_name] = []

        marker_y_position = 0.5
        if _self.analyzer.bar_width_fraction > 0 \
                and _self.analyzer.main_alpha > 0:
            # The relative distribution is computed based
            # on the selected analysis range only, which
            # may differ from the full column dynamic range
            # (hence the warning(s) above)
            histogram_sum = hist_y_values.sum()
            hist_x_values = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            # hist_x_values = bin_edges[:-1]
            hist_y_values = hist_y_values / histogram_sum \
                if histogram_sum != 0 else hist_y_values

            marker_y_position = 0.5 * (
                    hist_y_values.max() + hist_y_values.min())

            # Add bars to plot
            row[_column_name].append(plotdata.BarData(
                x_values=hist_x_values,
                y_values=hist_y_values,
                x_label=_self.analyzer.column_to_properties[column_name].label \
                    if column_name in _self.analyzer.column_to_properties \
                    else clean_column_name(column_name),
                alpha=_self.analyzer.main_alpha,
                extra_kwargs=dict(
                    width=_self.analyzer.bar_width_fraction * (
                            bin_edges[1] - bin_edges[0]))))

        # Add markers at the average points
        row[_column_name].append(plotdata.ScatterData(
            x_values=[row[f"{column_name}_avg"]],
            y_values=[marker_y_position],
            marker_size=4 * _self.analyzer.main_marker_size,
            alpha=_self.analyzer.main_alpha))

        # Add standard deviation error lines
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
        """Compute the list of `enb.plotdata.PlottableData elements` for
        a single render mode.
        """
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        column_series = group_df[column_name]

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(
                f"Invalid requested render mode {repr(render_mode)}")
        assert render_mode == "hbar"

        finite_only_series = self.remove_nans(column_series)
        if len(finite_only_series) == 0:
            enb.logger.warn(
                f"{_self.__class__.__name__}, {render_mode}: "
                f"No finite data found for column {repr(column_name)}"
                f"{' for ' + repr(group_label) if group_label else ''}. "
                f"No plottable data is produced for this case.")
            row[_column_name] = []
            return
        if len(column_series) != len(column_series):
            enb.logger.debug(
                "Finite and/or NaNs found in the input. Using "
                f"{100 * (len(finite_only_series) / len(column_series))}% "
                f"of the total.")

        row[_column_name] = [plotdata.BarData(
            x_values=(0,),
            y_values=(finite_only_series.mean(),),
            vertical=False,
            alpha=_self.analyzer.main_alpha), ]

    def compute_boxplot_plottable_one_case(self, *args, **kwargs):
        """Compute the list of `enb.plotdata.PlottableData elements` for
        a single render mode.
        """
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        column_series = group_df[column_name]

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(
                f"Invalid requested render mode {repr(render_mode)}")
        assert render_mode == "boxplot"

        finite_only_series = self.remove_nans(column_series)
        if len(finite_only_series) == 0:
            enb.logger.warn(
                f"{_self.__class__.__name__}, {render_mode}: "
                f"No finite data found for column {repr(column_name)}"
                f"{' for ' + repr(group_label) if group_label else ''}. "
                "No plottable data is produced for this case.")
            row[_column_name] = []
            return
        if len(column_series) != len(column_series):
            enb.logger.debug(
                "Finite and/or NaNs found in the input. Using "
                f"{100 * (len(finite_only_series) / len(column_series))}%"
                " of the total.")

        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            np.seterr(all="raise")
            try:
                description = scipy.stats.describe(finite_only_series)
                quartiles = scipy.stats.mstats.mquantiles(finite_only_series)
            except (RuntimeWarning, FloatingPointError):
                class Description:
                    """Mimic the description object produced by scipy.stats
                    for cases where automatic description cannot be obtained.
                    """
                    # pylint: disable=too-few-public-methods
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

        q1_q3_box_width = quartiles[2] - quartiles[0]
        if q1_q3_box_width < 0:
            if abs(q1_q3_box_width) > 1e7:
                enb.logger.error(
                    f"Error plotting boxplot with {self.__class__}: "
                    f"invalid negative box width ({q1_q3_box_width}). "
                    f"Setting to 0 instead.")
            q1_q3_box_width = 0

        row[_column_name] = [
            # Min-max span lines (centered around mean)
            plotdata.ErrorLines(
                x_values=(description.mean,),
                y_values=(0,),
                err_neg_values=(description.mean - description.minmax[0],),
                err_pos_values=(description.minmax[1] - description.mean,),
                vertical=False,
                line_width=_self.analyzer.main_line_width,
                marker_size=_self.analyzer.main_marker_size,
                alpha=_self.analyzer.main_alpha),
            # Box for 1st and 3rd quartiles
            plotdata.Rectangle(
                x_values=(0.5 * (quartiles[0] + quartiles[2]),), y_values=(0,),
                width=q1_q3_box_width,
                line_width=_self.analyzer.main_line_width,
                alpha=_self.analyzer.main_alpha,
                height=0.8),
            # Line for 2nd quartile (median)
            plotdata.LineSegment(
                x_values=(quartiles[1],), y_values=(0,),
                line_width=_self.analyzer.main_line_width,
                alpha=_self.analyzer.main_alpha,
                length=0.8,
                vertical=True),
        ]

        if _self.analyzer.show_individual_samples:
            row[_column_name].append(plotdata.ScatterData(
                y_values=[0] * len(finite_only_series.values),
                x_values=list(finite_only_series),
                alpha=_self.analyzer.secondary_alpha,
                marker_size=_self.analyzer.secondary_marker_size,
                marker="o",
            ))


@enb.config.aini.managed_attributes
class TwoNumericAnalyzer(Analyzer):
    """Analyze pairs of columns containing scalar, numeric values. Compute
    basic statistics and produce a scatter plot based on the obtained data.

    As opposed to ScalarNumericAnalyzer, target_columns should be an iterable
    of tuples with 2 column names (other elements are ignored). When
    applicable, the first column in each tuple is considered the x column,
    and the second the y column.
    """
    # The following attributes are directly used for analysis/plotting,
    # and can be modified before any call to get_df. These values may be
    # updated based on .ini files, see the documentation of the
    # enb.config.aini.managed_attributes decorator for more information.
    # Common analyzer attributes:
    valid_render_modes = {"scatter", "line"}
    selected_render_modes = set(valid_render_modes)
    plot_title = None
    title_y = None
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
    # grouped into a single one with the average y value. Applies only in the
    # 'line' render mode.
    average_identical_x = False
    # If True, a line displaying linear regression is shown in the 'scatter'
    # render mode
    show_linear_regression = False

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the
            # @enb.aanalysis.Analyzer.normalize_parameters, in turn
            # manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to
            # render_plds_by_group
            **column_kwargs):
        # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
        # Update common rendering kwargs, including the 'pds_by_group_name'
        # entry with the data to be plotted
        column_kwargs = super().update_render_kwargs_one_case(
            column_selection=column_selection, reference_group=reference_group,
            render_mode=render_mode,
            summary_df=summary_df, output_plot_dir=output_plot_dir,
            group_by=group_by, column_to_properties=column_to_properties,
            show_global=show_global, show_count=show_count,
            **column_kwargs)

        # Combine samples in the same x position
        if self.average_identical_x and render_mode == "line":
            # pylint: disable=unused-variable
            for group_name, group_pds in column_kwargs[
                "pds_by_group_name"].items():
                for plottable_data in group_pds:
                    x_to_ylist = collections.defaultdict(list)
                    for x_value, y_value in zip(
                            plottable_data.x_values, plottable_data.y_values):
                        x_to_ylist[x_value].append(y_value)

                    plottable_data.x_values = sorted(x_to_ylist.keys())
                    plottable_data.y_values = [
                        sum(x_to_ylist[x]) / len(x_to_ylist[x])
                        for x in plottable_data.x_values]

        # Update global x and y labels
        try:
            x_column_name, y_column_name = column_selection
        except TypeError as ex:
            raise SyntaxError(
                f"Passed invalid column selection to {self.__class__.__name__}: "
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
            column_kwargs["global_x_label"] = \
                x_column_properties.label + \
                (f" difference vs. {reference_group}"
                 if reference_group and "scatter" in self.selected_render_modes else "")
        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = \
                y_column_properties.label + \
                (f" difference vs. {reference_group}"
                 if reference_group else "")

        # Calculate axis limits
        if "x_min" not in column_kwargs:
            column_kwargs["x_min"] = float(
                summary_df[f"{x_column_name}_min"].min()) \
                if column_to_properties[x_column_name].plot_min is None \
                else column_to_properties[x_column_name].plot_min
        if "x_max" not in column_kwargs:
            column_kwargs["x_max"] = float(
                summary_df[f"{x_column_name}_max"].max()) \
                if column_to_properties[x_column_name].plot_max is None \
                else column_to_properties[x_column_name].plot_max
        if "y_min" not in column_kwargs:
            column_kwargs["y_min"] = float(
                summary_df[f"{y_column_name}_min"].min()) \
                if column_to_properties[y_column_name].plot_min is None \
                else column_to_properties[y_column_name].plot_min
        if "y_max" not in column_kwargs:
            column_kwargs["y_max"] = float(
                summary_df[f"{y_column_name}_max"].max()) \
                if column_to_properties[y_column_name].plot_max is None \
                else column_to_properties[y_column_name].plot_max

        # Adjust a common scale for all subplots
        if self.common_group_scale and (
                "y_min" not in column_kwargs or "y_max" not in column_kwargs):
            global_x_min = float("inf")
            global_x_max = float("-inf")
            global_y_min = float("inf")
            global_y_max = float("-inf")
            for pld_list in summary_df[
                f"{column_selection}_render-{render_mode}"]:
                if render_mode == "scatter":
                    candidate_plds = (pld for pld in pld_list if
                                      isinstance(pld, plotdata.ScatterData))
                elif render_mode == "line":
                    candidate_plds = (pld for pld in pld_list if
                                      isinstance(pld, plotdata.LineData))
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

    def build_summary_atable(self, full_df, target_columns, reference_group,
                             group_by, include_all_group, **render_kwargs):
        # pylint: disable=too-many-arguments
        return TwoNumericSummary(analyzer=self, full_df=full_df,
                                 reference_group=reference_group,
                                 target_columns=target_columns,
                                 group_by=group_by,
                                 include_all_group=include_all_group)

    def save_analysis_tables(
            self, group_by, reference_group, selected_render_modes, summary_df,
            summary_table, target_columns, **render_kwargs):
        """Save csv and tex files into enb.config.options.analysis_dir that
        summarize the results of one target_columns element. If
        enb.config.options.analysis_dir is None or empty, no analysis is
        performed.

        By default, the CSV contains the min, max, avg, std, and median of
        each group. Subclasses may overwrite this behavior.
        """
        # pylint: disable=too-many-arguments,too-many-locals
        for render_mode in selected_render_modes:
            if render_mode == "scatter":
                super().save_analysis_tables(
                    group_by=group_by,
                    reference_group=reference_group,
                    selected_render_modes={render_mode},
                    summary_df=summary_df,
                    summary_table=summary_table,
                    target_columns=target_columns,
                    **render_kwargs)
            elif options.analysis_dir:
                for column_pair in target_columns:
                    analysis_output_path = self.get_output_pdf_path(
                        column_selection=[column_pair],
                        group_by=group_by,
                        reference_group=reference_group,
                        output_plot_dir=options.analysis_dir,
                        render_mode=render_mode)[:-4] + ".csv"
                    os.makedirs(os.path.dirname(analysis_output_path),
                                exist_ok=True)
                    with open(analysis_output_path, "w", encoding="utf-8") \
                            as analysis_file:
                        for index, row in summary_df.iterrows():
                            group_name = re.match(
                                r"\('(.+)',\)", index).group(1)
                            x_values = row[f"{repr(column_pair)}" \
                                           f"_render-{render_mode}"][0].x_values
                            y_values = row[f"{repr(column_pair)}" \
                                           f"_render-{render_mode}"][0].y_values
                            analysis_file.write(
                                ",".join([group_name, column_pair[0]]
                                         + [str(x) for x in x_values])
                                + "\n")
                            analysis_file.write(
                                ",".join(["", column_pair[1]]
                                         + [str(y) for y in y_values])
                                + "\n")


class TwoNumericSummary(ScalarNumericSummary):
    """Summary table used in TwoNumericAnalyzer.

    For this class, target_columns must be a list of tuples, each tuple
    containing two column name, corresponding to x and y, respectively.
    Scalar analysis is provided on each column individually, as well as basic
    correlation metrics for each pair of columns.
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group,
                 group_by, include_all_group):
        # Plot rendering columns are added automatically via this call, with
        # associated function self.render_target with partialed parameters
        # column_name and render_mode.
        # pylint: disable=too-many-arguments,non-parent-init-called
        # pylint: disable=super-init-not-called
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
                    raise ValueError(
                        f"Invalid column name selection {repr(column_name)}. "
                        f"Full selection: {repr(target_columns)}")
                if column_name in self.column_to_xmin_xmax:
                    continue
                self.add_scalar_description_columns(column_name=column_name)

                if len(full_df) == 1 or len(full_df[column_name].unique()) == 1:
                    self.column_to_xmin_xmax[column_name] = (
                        full_df[column_name][0], full_df[column_name][0])
                else:
                    try:
                        finite_series = full_df[column_name].replace(
                            [np.inf, -np.inf], np.nan, inplace=False).dropna()
                        self.column_to_xmin_xmax[
                            column_name] = scipy.stats.describe(
                            finite_series.values).minmax
                    except FloatingPointError as ex:
                        enb.logger.error(f"column_name={column_name}")
                        enb.logger.error(
                            f"full_df[column_name].values={full_df[column_name].values}")
                        raise ex

            self.add_twoscalar_description_columns(column_names=x_y_names)

        self.move_render_columns_back()

    def apply_reference_bias(self):
        """If a reference group is selected, subtract the reference_group's
        average values from all groups, so that reference_group becomes the baseline.

        The scatter and line render modes cannot be simultaneously selected
        if a reference group is selected, since the bias is applied differently
        for each mode.
        """
        if self.reference_group is not None:
            if self.group_by is None:
                raise ValueError(
                    f"Cannot use a not None reference_group if group_by is None "
                    f"(here is {repr(self.reference_group)})")
            if all(mode in self.analyzer.selected_render_modes for mode in ("line", "scatter")):
                raise ValueError(f"{self.analyzer.__class__.__name__} does not support using a "
                                 f"reference group (here {self.reference_group}) "
                                 f"simultaneously for the 'line' and 'scatter' render modes. "
                                 f"Please run this analyzer twice, "
                                 f"once for 'line' and another for 'scatter', "
                                 f"if both are needed.")

            if "scatter" in self.analyzer.selected_render_modes:
                self.apply_reference_bias_scatter()
            elif "line" in self.analyzer.selected_render_modes:
                self.apply_reference_bias_line()
            else:
                raise ValueError(
                    f"Unsupported render mode(s) {self.analyzer.selected_render_modes} "
                    f"in {self.analyzer.__class__.__name__}.")
        else:
            self.reference_avg_by_column = None

    def apply_reference_bias_line(self):
        """Make the reference group the baseline (if one is selected).
        For each x value, subtract the reference group's average value of each y column.

        All groups must share their x values, i.e., must be x-aligned, or a ValueError
        is raised.

        Each y-column can only be used with one x-column, or a ValueError is raised.
        """
        if self.reference_group is None:
            return
        if "line" not in self.analyzer.selected_render_modes:
            raise ValueError("This method is meant to be called for the scatter render mode,"
                             f"but {self.analyzer.selected_render_modes=}")
        self.reference_df = self.reference_df.copy()

        for group_label, group_df in self.split_groups():
            if group_label == self.reference_group:
                # Keys are the y-column names that have been processed. Values
                # are the corresponding x-columns for each y-column
                # (each y-column can only be used with one x-column)
                processed_y_to_x_columns = dict()
                for x_column, y_column in self.target_columns:
                    try:
                        if processed_y_to_x_columns[y_column] != x_column:
                            raise ValueError(
                                "Each y-column can only be used with one x-column."
                                f"However, {repr(y_column)} was used for "
                                f"{repr(x_column)} and {repr(processed_y_to_x_columns[y_column])}")
                        processed_y_to_x_columns[y_column] = x_column
                    except KeyError:
                        pass

                reference_count_by_xvalue = dict()
                for x_value in group_df[x_column].unique():
                    reference_filtered_df = group_df.loc[group_df[x_column] == x_value]
                    reference_filtered_df = reference_filtered_df.loc[reference_filtered_df[y_column].notna()]
                    reference_count_by_xvalue[x_value] = len(reference_filtered_df)
                    self.reference_df.loc[self.reference_df[x_column] == x_value, y_column] \
                        -= reference_filtered_df[y_column].mean()


                warning_shown = False
                for target_group_label, target_group_df in self.split_groups():
                    for y_column, x_column in processed_y_to_x_columns.items():
                        for x_value in target_group_df[x_column].unique():
                            target_filtered_df = target_group_df[
                                target_group_df[x_column] == x_value].notna()
                            target_count = len(target_filtered_df)
                            if not warning_shown and target_count != reference_count_by_xvalue[x_value]:
                                enb.logger.warn(
                                    "Warning: when applying group reference bias, it was found that "
                                    f"group {repr(target_group_label)} contained {target_count} elements "
                                    f"for {x_column}={x_value} but the reference group ({self.reference_group}) "
                                    f"contained {reference_count_by_xvalue[x_value]}. This message is shown "
                                    f"only once per call: other columns and/or x values might have the same "
                                    f"problem.")

                break
        else:
            found_groups_str = ','.join(
                repr(label) for label, _ in self.split_groups(
                    reference_df=self.reference_df,
                    include_all_group=self.include_all_group))
            raise ValueError(f"Cannot find {self.reference_group} "
                             f"among defined groups ({found_groups_str})")

    def apply_reference_bias_scatter(self):
        """Subtract the reference group's average value of all requested x and y columns.
        """
        if self.reference_group is None:
            return
        if "scatter" not in self.analyzer.selected_render_modes:
            raise ValueError("This method is meant to be called for the scatter render mode,"
                             f"but {self.analyzer.selected_render_modes=}")

        for group_label, group_df in self.split_groups():
            if group_label == self.reference_group:
                target_columns = set()
                for column1, column2 in self.target_columns:
                    target_columns.add(column1)
                    target_columns.add(column2)

                self.reference_avg_by_column = {
                    column:
                        group_df[group_df[column].notna()][column].mean()
                    for column in target_columns
                }

                self.reference_df = self.reference_df.copy()
                for column, avg in self.reference_avg_by_column.items():
                    self.reference_df[column] -= avg
                break
        else:
            found_groups_str = ','.join(
                repr(label) for label, _ in self.split_groups(
                    reference_df=self.reference_df,
                    include_all_group=self.include_all_group))
            raise ValueError(f"Cannot find {self.reference_group} "
                             f"among defined groups ({found_groups_str})")

    def add_twoscalar_description_columns(self, column_names):
        """Add columns that compute several statistics considering two
        columns jointly, e.g., their correlation.
        """
        for descriptor in ["pearson_correlation", "pearson_correlation_pvalue",
                           "spearman_correlation",
                           "spearman_correlation_pvalue",
                           "linear_lse_slope", "linear_lse_intercept"]:
            column_properties = enb.atable.ColumnProperties(
                name=f"{column_names[0]}_{column_names[1]}_{descriptor}",
                label=f"{descriptor[:1].upper() + descriptor[1:]} "
                      f"for {column_names[0]}, {column_names[1]}".replace(
                    "_", " "))
            self.add_column_function(
                self,
                fun=functools.partial(self.set_twoscalar_description,
                                      column_selection=column_names),
                column_properties=column_properties)

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
                    row[
                        f"{x_column_name}_{y_column_name}_pearson_correlation_pvalue"] = \
                    scipy.stats.pearsonr(finite_series_x, finite_series_y)
                row[f"{x_column_name}_{y_column_name}_spearman_correlation"], \
                    row[
                        f"{x_column_name}_{y_column_name}_spearman_correlation_pvalue"] = \
                    scipy.stats.spearmanr(finite_series_x, finite_series_y)
                lr_results = scipy.stats.linregress(finite_series_x,
                                                    finite_series_y)
                row[f"{x_column_name}_{y_column_name}_linear_lse_slope"] = \
                    lr_results.slope
                row[
                    f"{x_column_name}_{y_column_name}_linear_lse_intercept"] = \
                    lr_results.intercept
            except (RuntimeWarning, FloatingPointError, ValueError) as ex:
                enb.logger.debug(
                    f"{self.__class__.__name__}: "
                    f"Cannot set correlation metrics for "
                    f"({x_column_name=}, {y_column_name=}, {group_label=}): "
                    f"{repr(ex)}")
                row[f"{x_column_name}_{y_column_name}_pearson_correlation"] = \
                    float("inf")
                row[
                    f"{x_column_name}_{y_column_name}_pearson_correlation_pvalue"] \
                    = float("inf")
                row[f"{x_column_name}_{y_column_name}_spearman_correlation"] = \
                    float("inf")
                row[
                    f"{x_column_name}_{y_column_name}_spearman_correlation_pvalue"] = \
                    float("inf")
                row[f"{x_column_name}_{y_column_name}_linear_lse_slope"] = \
                    float("inf")
                row[f"{x_column_name}_{y_column_name}_linear_lse_intercept"] = \
                    float("inf")

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes a list of
        `enb.plotdata.PlottableData elements` for this case (group, column,
        render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        # pylint: disable=too-many-locals,too-many-locals,too-many-branches
        _self, group_label, row = args
        group_df = self.label_to_df[group_label]
        x_column_name, y_column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        reference_group = kwargs["reference_group"]
        x_column_series = group_df[x_column_name]
        y_column_series = group_df[y_column_name]
        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(
                f"Invalid requested render mode {repr(render_mode)}")

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
                x_min, x_max = row[f"{x_column_name}_min"], row[
                    f"{x_column_name}_max"]
                slope = row[f"{x_column_name}_{y_column_name}_linear_lse_slope"]
                intercept = row[
                    f"{x_column_name}_{y_column_name}_linear_lse_intercept"]

                if any(not math.isfinite(x) for x in (
                        slope, intercept, x_min, x_max)):
                    x_values = []
                    y_values = []
                else:
                    x_values = [x_min, x_max]
                    y_values = [intercept + slope * x for x in (x_min, x_max)]
                plds_this_case.append(plotdata.LineData(
                    x_values=x_values, y_values=y_values,
                    marker_size=0, alpha=_self.analyzer.secondary_alpha,
                    line_width=_self.analyzer.secondary_line_width))
        elif render_mode == "line":
            if self.group_by == "family_label":
                # If available,
                try:
                    group_by = kwargs["task_families"]
                except KeyError:
                    group_by = self.group_by
            else:
                group_by = self.group_by

            if is_family_grouping(group_by=group_by):
                # Family line plots look into the task names and produce
                # one marker per task, linking same-family tasks with a line.
                x_values = []
                y_values = []

                current_family = \
                    [f for f in group_by if f.label == group_label][0]
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
            raise SyntaxError(
                f"Invalid render mode {repr(render_mode)} not within the "
                f"supported ones for {_self.analyzer.__class__.__name__} "
                f"({repr(_self.analyzer.valid_render_modes)}")

        # Plot the reference lines only once per plot to maintain the desired alpha
        if reference_group is not None and \
                ((group_label == sorted(self.label_to_df.keys())[
                    0] and group_label != reference_group)
                 or (sorted(self.label_to_df.keys())[0] == reference_group
                     and sorted(self.label_to_df.keys())[0] == group_label)):
            if "scatter" in self.analyzer.selected_render_modes:
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
    """Analyzer for columns with associated ColumnProperties having
    has_dict=True. Dictionaries are expected to have numeric entries.
    """
    # The following attributes are directly used for analysis/plotting,
    # and can be modified before any call to get_df. These values may be
    # updated based on .ini files, see the documentation of the
    # enb.config.aini.managed_attributes decorator for more information.
    # Common analyzer attributes:
    valid_render_modes = {"line"}
    selected_render_modes = set(valid_render_modes)
    plot_title = None
    title_y = None
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
               output_plot_dir=None, group_by=None, reference_group=None,
               column_to_properties=None,
               show_global=None, show_count=True,
               key_to_x=None,
               **render_kwargs):
        """Analyze and plot columns containing dictionaries with numeric data.

        :param full_df: full DataFrame instance with data to be plotted
          and/or analyzed.
        :param target_columns: columns to be analyzed. Typically, a list of
          column names, although each subclass may redefine the accepted format
          (e.g., pairs of column names). If None, all scalar, non string
          columns are used.
        :param selected_render_modes: a potentially empty list of mode names,
          all of which must be in self.valid_render_modes. Each mode represents
          a type of analysis or plotting.
        :param group_by: if not None, the name of the column to be used for
          grouping.
        :param reference_group: if not None, the reference group name against
          which data are to be analyzed.
        :param output_plot_dir: path of the directory where the plot/plots
          is/are to be saved. If None, the default output plots path given by
          `enb.config.options` is used.
        :param column_to_properties: dictionary with ColumnProperties
          entries. ATable instances provide it in the
          :attr:`column_to_properties` attribute, :class:`Experiment` instances
          can also use the :attr:`joined_column_to_properties` attribute to
          obtain both the dataset and experiment's columns.
        :param show_global: if True, a group containing all elements is also
          included in the analysis
        :param key_to_x: if provided, it can be a mapping between the keys
          found in the column data dictionaries, and the x value in which they
          should be plotted.
        :return: a |DataFrame| instance with analysis results
        """
        # pylint: disable=too-many-arguments,too-many-locals,arguments-differ
        # pylint: disable=attribute-defined-outside-init
        try:
            self.key_to_x = dict(key_to_x) if key_to_x is not None else key_to_x

            combined_df = full_df.copy()
            self.column_name_to_keys = {}

            # Keys are combined before analyzing. This allows to compute just
            # once the key_to_x dictionary shared across all groups.
            for column_name in target_columns:
                if self.combine_keys_callable:
                    combined_df[f"__{column_name}_combined"] = combined_df[
                        column_name].apply(
                        self.combine_keys_callable)
                else:
                    combined_df[f"__{column_name}_combined"] = combined_df[
                        column_name]
                self.column_name_to_keys[column_name] = set()
                for key_set in combined_df[f"__{column_name}_combined"].apply(
                        lambda d: tuple(d.keys())).unique():
                    for k in key_set:
                        self.column_name_to_keys[column_name].add(k)
                self.column_name_to_keys[column_name] = sorted(
                    self.column_name_to_keys[column_name])

            return super().get_df(full_df=combined_df,
                                  target_columns=target_columns,
                                  output_plot_dir=output_plot_dir,
                                  group_by=group_by,
                                  reference_group=reference_group,
                                  column_to_properties=column_to_properties,
                                  selected_render_modes=selected_render_modes,
                                  show_global=show_global,
                                  show_count=show_count,
                                  **render_kwargs)
        finally:
            if self.key_to_x is not None:
                self.key_to_x = None

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the
            # @enb.aanalysis.Analyzer.normalize_parameters, in turn
            # manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to
            # plotdata.render_plds_by_group
            **column_kwargs):
        # pylint: disable=too-many-arguments
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
            column_kwargs["global_y_label"] = ""

        # Adjust a common scale for all subplots
        if self.common_group_scale and (
                "y_min" not in column_kwargs and "y_max" not in column_kwargs):
            self.adjust_common_row_axes(column_kwargs=column_kwargs,
                                        column_selection=column_selection,
                                        render_mode=render_mode,
                                        summary_df=summary_df)

        # Set the x ticks and labels
        if "x_tick_list" not in column_kwargs:
            column_kwargs["x_tick_list"] = list(
                range(len(self.column_name_to_keys[column_name])))
        if "x_tick_label_list" not in column_kwargs:
            column_kwargs["x_tick_label_list"] = [str(x) for x in
                                                  column_kwargs["x_tick_list"]]

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, reference_group,
                             group_by, include_all_group, **render_kwargs):
        # pylint: disable=too-many-arguments
        return DictNumericSummary(
            analyzer=self, full_df=full_df, target_columns=target_columns,
            reference_group=reference_group,
            group_by=group_by, include_all_group=include_all_group)


class DictNumericSummary(AnalyzerSummary):
    """Summary table for the DictNumericAnalyzer.
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group,
                 group_by, include_all_group):
        # pylint: disable=too-many-arguments
        # Plot rendering columns are added automatically via this call,
        # with associated function self.render_target with partialed
        # parameters column_name and render_mode.
        AnalyzerSummary.__init__(
            self=self, analyzer=analyzer, full_df=full_df,
            target_columns=target_columns, reference_group=reference_group,
            group_by=group_by, include_all_group=include_all_group)

        for column_name in target_columns:
            # The original dicts are combined based on the analyzer's
            # combine_keys_callable
            try:
                if not self.analyzer.column_to_properties[
                    column_name].has_dict_values:
                    raise ValueError(
                        f"Attempting to use {self.__class__.__name__} on "
                        f"column {repr(column_name)}, which is does not have "
                        f"has_dict_values=True in its column properties.")
            except KeyError:
                pass

        self.add_group_description_columns()
        self.move_render_columns_back()

    def add_group_description_columns(self):
        """Add several columns that compute basic (scalar) numerical stats
        including min, max, avg, standard deviation and median.
        """
        for column_name in self.target_columns:
            for descriptor in ["min", "max", "avg", "std", "median"]:
                self.add_column_function(
                    self,
                    fun=functools.partial(self.set_group_description,
                                          column_selection=column_name),
                    column_properties=enb.atable.ColumnProperties(
                        name=f"{column_name}_{descriptor}",
                        label=f"{column_name}: {descriptor}",
                        has_dict_values=True))

    def set_group_description(self, *args, **kwargs):
        """Set the columns that compute basic (scalar) numerical stats
        including min, max, avg, standard deviation and median.
        """
        # pylint: disable=too-many-locals
        _self, group_label, row = args
        column_name = kwargs["column_selection"]
        group_df = _self.label_to_df[group_label]
        full_series = group_df[column_name]
        finite_series = self.remove_nans(full_series)

        if len(full_series) != len(finite_series):
            if len(finite_series) > 0:
                enb.logger.warn(
                    f"{_self.__class__.__name__}: "
                    f"set_scalar_description for group {repr(group_label)}, "
                    f"column {repr(column_name)} "
                    f"is ignoring infinite values "
                    f"({100 * (1 - len(finite_series) / len(full_series)):.2f}%"
                    f" of the total).")
            else:
                enb.logger.warn(
                    f"{_self.__class__.__name__}: "
                    f"set_scalar_description for group {repr(group_label)}, "
                    f"column {repr(column_name)} "
                    f"found only infinite values. "
                    f"Several statistics will be nan for this case.")

        x_values = []
        min_values = []
        max_values = []
        avg_values = []
        std_values = []
        median_values = []
        key_values = []
        for i, k in enumerate(_self.analyzer.column_name_to_keys[column_name]):
            # pylint: disable=cell-var-from-loop
            values = group_df[f"__{column_name}_combined"].apply(
                lambda d: d[k] if k in d else None).dropna()
            if len(values) > 0:
                if _self.analyzer.key_to_x:
                    try:
                        x_values.append(_self.analyzer.key_to_x[k])
                    except KeyError:
                        enb.logger.debug(
                            f"{self.__class__.__name__}: "
                            f"Key {k} not present in "
                            f"{self.analyzer.__class__.__name__}'s key_to_x. "
                            f"Ignoring.")
                        continue
                else:
                    x_values.append(i)
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
                        std_values.append(
                            values.std() if len(np.unique(values)) > 1 else 0)
                        median_values.append(values.median())

        for label, data_list in (("min", min_values),
                                 ("max", max_values),
                                 ("avg", avg_values),
                                 ("std", std_values),
                                 ("median", median_values)):
            row[f"{column_name}_{label}"] = dict(zip(key_values, data_list))

    def combine_keys(self, *args, **kwargs):
        """Combine the keys of a column
        """
        _self, group_label, row = args  # pylint: disable=unused-variable
        column_name = kwargs["column_selection"]
        try:
            row[_column_name] = self.analyzer.combine_keys_callable(
                row[column_name])
        except TypeError:
            row[_column_name] = row[column_name]

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes a list of
        `enb.plotdata.PlottableData elements` for this case (group, column,
        render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        _self, group_label, row = args  # pylint: disable=unused-variable
        column_name = kwargs["column_selection"]
        render_mode = kwargs["render_mode"]
        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(
                f"Invalid requested render mode {repr(render_mode)}")

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

        if _self.analyzer.show_individual_samples and \
                (self.analyzer.secondary_alpha is None
                 or self.analyzer.secondary_alpha > 0):
            row[_column_name].append(plotdata.ScatterData(
                x_values=x_values,
                y_values=avg_values,
                alpha=self.analyzer.secondary_alpha))
        if render_mode == "line":
            row[_column_name].append(plotdata.LineData(
                x_values=x_values, y_values=avg_values,
                alpha=self.analyzer.main_alpha,
                line_width=_self.analyzer.main_line_width,
                marker_size=_self.analyzer.main_marker_size, ))
            if _self.analyzer.show_y_std:
                _, std_values = zip(*sorted(row[f"{column_name}_std"].items()))
                assert len(_) == len(x_values)
                row[_column_name].append(plotdata.ErrorLines(
                    x_values=x_values, y_values=avg_values,
                    err_neg_values=std_values, err_pos_values=std_values,
                    alpha=_self.analyzer.secondary_alpha,
                    vertical=True))
        else:
            raise ValueError(
                f"Unexpected render mode {render_mode} "
                f"for {self.__class__.__name__}")


@enb.config.aini.managed_attributes
class ScalarNumeric2DAnalyzer(ScalarNumericAnalyzer):
    """Analyzer able to process scalar numeric values located on an (x, y) plane.
    The target_columns parameter must be an iterable of tuples with
    3 elements, containing the columns with the x, y and data coordinates,
    e.g., ("column_x", "column_y", "column_data").

    Each of the three columns must contain scalar numerical data and are treated as such.

    In order to do something similar but with categorical (string) x and y axis
    (e.g., to display a table of numerical means indexed by corpus and task label)
    please see the ScalarTwoGroupAnalyzer class.
    """

    bin_count = 50
    valid_render_modes = {"colormap"}
    selected_render_modes = {"colormap"}
    x_tick_format_str = "{:.2f}"
    y_tick_format_str = "{:.2f}"
    color_map = "inferno"
    no_data_color = (1, 1, 1, 0)
    bad_data_color = "magenta"

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the
            # @enb.aanalysis.Analyzer.normalize_parameters, in turn
            # manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to
            # plotdata.render_plds_by_group
            **column_kwargs):
        # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
        # pylint: disable=too-many-statements
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
                # p and pd are PlottableData instances
                for plottable_data in (pld for pld in plds if
                                       isinstance(pld, plotdata.Histogram2D)):
                    data_column_name = column_selection[2]
                    try:
                        data_column_label = column_to_properties[data_column_name].label
                    except (TypeError, KeyError):
                        data_column_label = enb.atable.clean_column_name(data_column_name)
                    plottable_data.colormap_label = data_column_label

            histogram_pds = list(
                p for group_name, plds in
                column_kwargs["pds_by_group_name"].items()
                for p in plds if isinstance(p, plotdata.Histogram2D))
            assert histogram_pds

            h2d = histogram_pds[0]

            if "x_tick_list" not in column_kwargs:
                column_kwargs["x_tick_list"] = list(h2d.x_values)
                column_kwargs["x_tick_label_list"] = [
                    self.x_tick_format_str.format(e) for e in h2d.x_edges]
                if len(column_kwargs["x_tick_label_list"]) > 5:
                    column_kwargs["x_tick_list"] = [
                        h2d.x_values[0],
                        0.5 * (h2d.x_values[0] + h2d.x_values[-1]),
                        h2d.x_values[-1],
                    ]
                    column_kwargs["x_tick_label_list"] = [
                        h2d.x_edges[0],
                        0.5 * (h2d.x_edges[0] + h2d.x_edges[-1]),
                        h2d.x_edges[-1],
                    ]

            if "y_tick_list" not in column_kwargs:
                column_kwargs["y_tick_list"] = list(h2d.y_values)
                column_kwargs["y_tick_label_list"] = [
                    self.y_tick_format_str.format(e) for e in h2d.y_edges]
                if len(column_kwargs["y_tick_label_list"]) > 5:
                    column_kwargs["y_tick_list"] = [
                        h2d.y_values[0],
                        0.5 * (h2d.y_values[0] + h2d.y_values[-1]),
                        h2d.y_values[-1],
                    ]
                    column_kwargs["y_tick_label_list"] = [
                        h2d.y_edges[0],
                        0.5 * (h2d.y_edges[0] + h2d.y_edges[-1]),
                        h2d.y_edges[-1],
                    ]

            if "x_min" not in column_kwargs:
                column_kwargs["x_min"] = -0.5
            if "x_max" not in column_kwargs:
                column_kwargs["x_max"] = h2d.x_values[-1]
            if "y_min" not in column_kwargs:
                column_kwargs["y_min"] = -0.5
            if "y_max" not in column_kwargs:
                column_kwargs["y_max"] = h2d.y_values[-1]
            column_kwargs["x_tick_label_angle"] = 90

            column_kwargs["left_y_label"] = True

            y_column_name = column_selection[1]
            try:
                y_column_label = column_to_properties[y_column_name].label
            except (TypeError, KeyError):
                y_column_label = enb.atable.clean_column_name(y_column_name)

            if not column_kwargs["combine_groups"] and len(
                    column_kwargs["pds_by_group_name"]) > 1:
                for group_name, pds in column_kwargs[
                    "pds_by_group_name"].items():
                    for plottable_data in (p for p in pds
                                           if isinstance(p,
                                                         plotdata.Histogram2D)):
                        plottable_data.colormap_label = \
                            f"{plottable_data.colormap_label}" \
                            + (
                                f" vs {column_kwargs['y_labels_by_group_name'][reference_group]}"
                                if reference_group and plottable_data.colormap_label else "") \
                            + ("\n" if plottable_data.colormap_label else "") \
                            + f"{column_kwargs['y_labels_by_group_name'][group_name]}"

            # The y_labels_by_group_name key is set to the y label name; the
            # group name is shown to the right of the colorbar.
            column_kwargs["y_labels_by_group_name"] = {
                group_name: y_column_label
                for group_name in column_kwargs["pds_by_group_name"].keys()}

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, reference_group,
                             group_by, include_all_group, **render_kwargs):
        """Dynamically build a SummaryTable instance for scalar value analysis.
        """
        # pylint: disable=too-many-arguments
        return ScalarNumeric2DSummary(analyzer=self, full_df=full_df,
                                      target_columns=target_columns,
                                      reference_group=reference_group,
                                      group_by=group_by,
                                      include_all_group=include_all_group)


class ScalarNumeric2DSummary(ScalarNumericSummary):
    """Compute the numerical summaries for a :class:`ScalarNumeric2DAnalyzer`.
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group,
                 group_by, include_all_group):
        # Plot rendering columns are added automatically via this call,
        # with associated function self.render_target with partialed
        # parameters column_selection and render_mode.
        # pylint: disable=too-many-arguments,
        # pylint: disable=non-parent-init-called,super-init-not-called
        AnalyzerSummary.__init__(
            self=self,
            analyzer=analyzer, full_df=full_df, target_columns=target_columns,
            reference_group=reference_group, group_by=group_by,
            include_all_group=include_all_group)
        self.column_to_min_max = {}

        for column_tuple in target_columns:
            for column_name in column_tuple:
                if column_name not in full_df.columns:
                    raise ValueError(
                        f"Invalid column name selection {repr(column_name)}. "
                        f"Full selection: {repr(target_columns)}")

                if column_name in self.column_to_min_max:
                    continue

                # Add columns that compute the summary information
                self.add_scalar_description_columns(column_name=column_name)

                # Compute the global dynamic range of all input samples (before grouping)
                finite_series = full_df[column_name].replace([np.inf, -np.inf],
                                                             np.nan,
                                                             inplace=False).dropna()
                if len(finite_series) > 1:
                    try:
                        self.column_to_min_max[
                            column_name] = scipy.stats.describe(
                            finite_series.values).minmax
                    except FloatingPointError as ex:
                        raise FloatingPointError(
                            f"Invalid finite_series.values="
                            f"{finite_series.values}") from ex
                elif len(finite_series) == 1:
                    self.column_to_min_max[column_name] = [
                        finite_series.values[0], finite_series.values[0]]
                else:
                    self.column_to_min_max[column_name] = [None, None]

        self.move_render_columns_back()

    def apply_reference_bias(self):
        """Compute the average value of the reference group for each target
        column and subtract it from the dataframe being analyzed. If not
        reference group is present, no action is performed.
        """
        if self.reference_group is not None:
            if self.group_by is None:
                raise ValueError(
                    f"Cannot use a not-None reference_group if group_by is None "
                    f"(here is {repr(self.reference_group)})")

            for group_label, group_df in self.split_groups():
                if group_label == self.reference_group:
                    self.reference_avg_by_column = {
                        colum: group_df[group_df[colum].notna()][colum].mean()
                        for colum in (t[2] for t in self.target_columns)
                    }

                    self.reference_df = self.reference_df.copy()
                    for column, avg in self.reference_avg_by_column.items():
                        self.reference_df[column] -= avg
                    break
        else:
            self.reference_avg_by_column = None

    def compute_plottable_data_one_case(self, *args, **kwargs):
        """Column-setting function that computes a list of
        `enb.plotdata.PlottableData elements` for this case (group, column,
        render_mode).

        See `enb.aanalysis.AnalyzerSummary.compute_plottable_data_one_case`
        for additional information.
        """
        if kwargs["render_mode"] == "colormap":
            return self.compute_colormap_plottable_one_case(*args, **kwargs)

        raise ValueError(f"Invalid render mode {kwargs['render_mode']}")

    def compute_colormap_plottable_one_case(self, *args, **kwargs):
        """Compute the list of `enb.plotdata.PlottableData elements` for
        a single render mode.
        """
        # pylint: disable=too-many-locals
        _self, group_label, row = args
        group_df = _self.label_to_df[group_label]
        x_column_name, y_column_name, data_column_name = \
            kwargs["column_selection"]
        try:
            data_column_label = \
                kwargs["column_to_properties"][data_column_name].label
        except (TypeError, KeyError):
            data_column_label = enb.atable.clean_column_name(data_column_name)

        render_mode = kwargs["render_mode"]
        x_column_series = group_df[x_column_name].apply(float)
        y_column_series = group_df[y_column_name].apply(float)
        data_column_series = group_df[data_column_name].apply(float)

        if render_mode not in _self.analyzer.valid_render_modes:
            raise ValueError(
                f"Invalid requested render mode {repr(render_mode)}")

        common_range = np.array(
            [list(self.column_to_min_max[x_column_name]),
             list(self.column_to_min_max[y_column_name])])

        histogram, x_edges, y_edges = np.histogram2d(
            x=x_column_series, y=y_column_series, density=False,
            range=common_range,
            weights=data_column_series, bins=self.analyzer.bin_count)

        counts, _, _ = np.histogram2d(
            x=x_column_series, y=y_column_series, density=False,
            range=common_range,
            bins=self.analyzer.bin_count)
        histogram /= np.clip(counts, 1, None)

        try:
            vmin = kwargs["column_to_properties"][data_column_name].plot_min
        except (TypeError, KeyError):
            vmin = None
        try:
            vmax = kwargs["column_to_properties"][data_column_name].plot_max
        except (TypeError, KeyError):
            vmax = None

        row[_column_name] = [plotdata.Histogram2D(
            x_edges=x_edges, y_edges=y_edges, matrix_values=histogram,
            colormap_label=data_column_label,
            vmin=vmin,
            vmax=vmax,
            no_data_color=self.analyzer.no_data_color,
            color_map=self.analyzer.color_map)]


@enb.config.aini.managed_attributes
class ScalarNumericJointAnalyzer(Analyzer):
    """Analyze scalar numeric data, providing joint (simultaneous)
    grouping by two categories. This is useful to produce tables
    of averages, e.g., for each corpus/task combination.
    """
    valid_render_modes = {"table"}
    selected_render_modes = set(valid_render_modes)
    # Show the global "All" row
    show_global_row = False
    # Show the global "All" column
    show_global_column = False
    # Show the reference group when one is selected?
    show_reference_group = False
    # Optionally highlight the best results in each row. Must be one of "low", "high" or None
    highlight_best_column = None
    # Optionally highlight the best results in each column. Must be one of "low", "high" or None
    highlight_best_row = None
    # Number format used for displaying cell data. Note that latex_decimal_count is not used in this class
    number_format = "{:.3f}"
    # Alignment ("left", "center", "right") of the data cells
    cell_alignment = "center"
    # Alignment ("left", "center", "right") of the column headers
    col_header_alignment = "center"
    # Alignment ("left", "center", "right") of the row headers
    row_header_alignment = "left"
    # Table width
    fig_width = None
    # Table height
    fig_height = None
    # "edges" parameter passed to plt.table
    # (substring of 'BRTL' or {'open', 'closed', 'horizontal', 'vertical'})
    edges = "closed"

    def get_df(self, full_df, target_columns,
               selected_render_modes=None,
               output_plot_dir=None, group_by=None, reference_group=None,
               column_to_properties=None,
               show_global_row=None, show_global_column=None,
               show_count=None,
               x_header_list=None, y_header_list=None,
               highlight_best_column=None, highlight_best_row=None,
               **render_kwargs):
        """Wrapper for enb.aanalysis.Analyzer.get_df, but adding support for the
        x_header_list and y_header_list parameters to control the row and column order.

        :param x_header_list: non-empty list of strings corresponding to the x categories (column headers).
          All strings in this list must exist as a category. However, not all categories need to
          be present in this list. If None, all headers are used in alphabetical order.
          Note that this applies to all elements of target_columns - please
          invoke this function multiple times if different headers (or ordering) are needed for
          different elements in target_columns.
        :param y_header_list: non-empty list of strings corresponding to the y categories (row headers).
          All strings in this list must exist as a category. However, not all categories need to
          be present in this list. If None, all headers are used in alphabetical order.
          Note that this applies to all elements of target_columns - please
          invoke this function multiple times if different headers (or ordering) are needed for
          different elements in target_columns.
        :param highlight_best_column: Optionally highlight the best results in each row.
          Must be one of "low", "high" or None.
        :param highlight_best_row:  Optionally highlight the best results in each column.
          Must be one of "low", "high" or None
        :param show_global_row: if True, or if None and self.show_global is True, an extra row is
          added to the analysis, corresponding to not splitting the data into the y categories
          (i.e., considering the average for all possible y categories). Note that if y_header_list is selected,
          averages are considered only for those categories.
        :param show_global_column: like show_global_row, but adds a new column corresponding to not splitting
          into x categories. Note that if x_header_list is selected, averages are considered only for those categories.
        """
        if highlight_best_column is not None and str(highlight_best_column).lower() not in ("low", "high"):
            raise ValueError(
                f"Invalid {highlight_best_column=}. Must be one of {('low', 'high', None)}")
        if highlight_best_row is not None and str(highlight_best_row).lower() not in ("low", "high"):
            raise ValueError(
                f"Invalid {highlight_best_row=}. Must be one of {('low', 'high', None)}")

        if "show_global" in render_kwargs:
            enb.logger.warn(f"Warning: `show_global` is ignored in {self.__class__.__name__}; "
                            f"use `show_global_row` and/or `show_global_column` instead.")

        render_kwargs = dict(render_kwargs)
        render_kwargs["x_header_list"] = x_header_list
        render_kwargs["y_header_list"] = y_header_list
        render_kwargs["highlight_best_column"] = highlight_best_column
        render_kwargs["highlight_best_row"] = highlight_best_row
        render_kwargs["show_global_row"] = show_global_row
        render_kwargs["show_global_column"] = show_global_column
        return super().get_df(full_df=full_df, target_columns=target_columns,
                              selected_render_modes=selected_render_modes,
                              output_plot_dir=output_plot_dir,
                              group_by=group_by,
                              reference_group=reference_group,
                              column_to_properties=column_to_properties,
                              show_count=show_count,
                              **render_kwargs)

    def update_render_kwargs_one_case(
            self, column_selection, reference_group, render_mode,
            # Dynamic arguments with every call
            summary_df, output_plot_dir,
            group_by, column_to_properties,
            # Arguments normalized by the @enb.aanalysis.Analyzer.normalize_parameters,
            # in turn manageable through .ini configuration files via the
            # @enb.config.aini.managed_attributes decorator.
            show_global, show_count,
            # Rendering options, directly passed to render_plds_by_group
            **column_kwargs):
        # Update common rendering kwargs
        column_kwargs = super().update_render_kwargs_one_case(
            column_selection=column_selection, reference_group=reference_group,
            render_mode=render_mode,
            summary_df=summary_df, output_plot_dir=output_plot_dir,
            group_by=group_by, column_to_properties=column_to_properties,
            show_global=None, show_count=show_count,
            **column_kwargs)

        if "global_x_label" not in column_kwargs:
            column_kwargs["global_x_label"] = None
        if "global_y_label" not in column_kwargs:
            column_kwargs["global_y_label"] = None

        column_kwargs["fig_height"] = self.fig_height
        column_kwargs["fig_width"] = self.fig_width

        for group_name, pds in column_kwargs["pds_by_group_name"].items():
            table = [pd for pd in pds if isinstance(pd, enb.plotdata.Table)]
            assert len(table) == 1
            table = table[0]

        if column_kwargs["fig_height"] is None:
            column_kwargs["fig_height"] = 0
            column_kwargs["fig_height"] += \
                0.3 * len(table.y_values) * len(column_kwargs["pds_by_group_name"]) \
                + 0.15 * len(column_kwargs["pds_by_group_name"])
        if column_kwargs["fig_width"] is None:
            column_kwargs["fig_width"] = 0.2 * (len(table.x_values) + 1)
            column_kwargs["fig_width"] += 0.25 * max(
                sum(len(cell) for cell in row) for row in table.cell_text)

        # These parameters should not be passed to enb.render
        del column_kwargs["x_header_list"]
        del column_kwargs["y_header_list"]
        del column_kwargs["highlight_best_row"]
        del column_kwargs["highlight_best_column"]
        del column_kwargs["show_global_column"]
        del column_kwargs["show_global_row"]

        return column_kwargs

    def build_summary_atable(self, full_df, target_columns, reference_group,
                             group_by, include_all_group, **render_kwargs):

        return ScalarNumericJointSummary(analyzer=self, full_df=full_df,
                                         target_columns=target_columns,
                                         reference_group=reference_group,
                                         group_by=group_by,
                                         show_global_row=render_kwargs["show_global_row"],
                                         show_global_column=render_kwargs["show_global_column"],
                                         x_header_list=render_kwargs["x_header_list"],
                                         y_header_list=render_kwargs["y_header_list"],
                                         highlight_best_row=render_kwargs["highlight_best_row"],
                                         highlight_best_column=render_kwargs["highlight_best_column"])

    def save_analysis_tables(
            self, group_by, reference_group,
            selected_render_modes, summary_df, summary_table,
            target_columns, **render_kwargs):
        """
        Store the joint analysis results in CSV and latex formats.

        If enb.config.options.analysis_dir is None or empty, no analysis is
        performed.
        """
        # pylint: disable=too-many-arguments
        if options.analysis_dir:
            # Generate the base output path
            try:
                render_mode_str = "__".join(selected_render_modes)
            except TypeError:
                render_mode_str = str(render_mode_str).replace(os.sep, "__")
            analysis_output_path = self.get_output_pdf_path(
                column_selection=target_columns,
                group_by=group_by,
                reference_group=reference_group,
                output_plot_dir=options.analysis_dir,
                render_mode=render_mode_str)[:-4] + ".csv"
            enb.logger.debug(
                f"Saving analysis results to {analysis_output_path}")
            os.makedirs(os.path.dirname(analysis_output_path), exist_ok=True)

            assert set(selected_render_modes) == {"table"}, \
                f"Only the table render mode is currently supported by {self.__class__.__name__}"

            # Generate CSV tables
            with open(analysis_output_path, "w") as csv_file:
                for x_column, y_column, data_column in target_columns:
                    csv_file.write(f"\n\n# Column selection: "
                                   f"{repr(x_column)} {repr(y_column)} {repr(data_column)}\n")

                    for stat in ["avg", "count", "min", "max", "std", "median"]:
                        csv_file.write(f"\n## Statistic: {stat}\n")

                        for group_name, group_df in summary_df.iterrows():
                            summary_dict = group_df[f"{x_column}_{y_column}_{data_column}_{stat}"]

                            group_label = " ".join(repr(s) for s in ast.literal_eval(group_name))
                            csv_file.write(f"### Group: {group_label}\n")

                            x_categories, y_categories = self.get_filtered_x_y_categories(
                                x_categories=summary_table.category_to_values[x_column],
                                y_categories=summary_table.category_to_values[y_column],
                                reference_group=summary_table.reference_group)

                            if summary_table.show_global_row and len(y_categories) > 1:
                                y_categories.append(None)
                            if summary_table.show_global_column and len(x_categories) > 1:
                                x_categories.append(None)

                            csv_file.write("," + ",".join(
                                str(x or self.global_group_name) for x in x_categories) + "\n")
                            number_format = self.number_format if stat != "count" else "{:d}"
                            for y_category in y_categories:
                                csv_file.write(str(y_category or self.global_group_name))
                                for x_category in x_categories:
                                    try:
                                        csv_file.write("," + number_format.format(
                                            summary_dict[(x_category, y_category)]))
                                    except KeyError:
                                        csv_file.write(",")
                                csv_file.write("\n")
                            if summary_table.include_all_group and len(y_categories) > 1:
                                csv_file.write(self.global_group_name)
                                for x_category in x_categories:
                                    try:
                                        csv_file.write("," + number_format.format(
                                            summary_dict[(x_category, None)]))
                                    except KeyError:
                                        csv_file.write(",")
                                csv_file.write("\n")

            # Generate latex tables
            with (open(analysis_output_path[:-4] + ".tex", "w") as latex_file):
                for x_column, y_column, data_column in target_columns:
                    column_header_count = len(summary_table.category_to_values[x_column])
                    longest_row_header = max(
                        len(str(y)) for y in summary_table.category_to_values[y_column])
                    if summary_table.include_all_group and len(
                            summary_table.category_to_values[y_column]) > 1:
                        longest_row_header = max(len(self.global_group_name), longest_row_header)
                    longest_row_header += len(r"\textbf{}")

                    latex_file.write(f"\n\n% Column selection: "
                                     f"{repr(x_column)} {repr(y_column)} {repr(data_column)}\n")
                    for stat in ["avg", "count", "min", "max", "std", "median"]:
                        latex_file.write(f"\n% Statistic: {enb.misc.escape_latex(stat)}\n")
                        latex_file.write(
                            r"\begin{tabular}{l" + "c" * column_header_count + r"}" + "\n")
                        latex_file.write(r"\toprule" + "\n")

                        for group_name, group_df in summary_df.iterrows():
                            x_categories, y_categories = self.get_filtered_x_y_categories(
                                x_categories=summary_table.category_to_values[x_column],
                                y_categories=summary_table.category_to_values[y_column],
                                reference_group=summary_table.reference_group)

                            summary_dict = group_df[f"{x_column}_{y_column}_{data_column}_{stat}"]
                            number_format = self.number_format if stat != "count" else "{:d}"
                            longest_cell_length = max(
                                max(len(number_format.format(val)) for val in summary_dict.values()),
                                max(len(str(x)) for x in x_categories)) + len(r"\textbf{}")
                            row_header_format = f"{{:{longest_row_header}s}}"
                            cell_format = f"{{:{longest_cell_length}s}}"

                            # Write group separator if there is more than one group
                            if len(summary_df) > 1:
                                group_label = " ".join(
                                    repr(s) for s in ast.literal_eval(group_name))
                                group_label = " ".join(ast.literal_eval(group_label))
                                latex_file.write("\\midrule\n")
                                latex_file.write(f"\\multicolumn{{{column_header_count + 1}}}{{c}}"
                                                 f"{{{enb.misc.escape_latex(group_label)}}} \\\\\n")
                                latex_file.write("\\midrule\n")

                            if summary_table.show_global_row and len(y_categories) > 1:
                                y_categories.append(None)
                            if summary_table.show_global_column and len(x_categories) > 1:
                                x_categories.append(None)

                            # Write the (sub) table headers
                            latex_file.write(
                                " " * longest_row_header + " & "
                                + " & ".join(cell_format.format(r"\textbf{" + str(x or self.global_group_name) + r"}")
                                             for x in x_categories)
                                + " \\\\\n")
                            latex_file.write("\\toprule\n")

                            # Write data rows
                            for y_category in y_categories:
                                latex_file.write(row_header_format.format(
                                    f"\\textbf{{{enb.misc.escape_latex(str(y_category or self.global_group_name))}}}"))
                                for x_category in x_categories:
                                    highlight = self.should_highlight_cell(
                                        summary_dict=summary_dict, summary_table=summary_table,
                                        x_categories=x_categories, x_category=x_category,
                                        y_categories=y_categories, y_category=y_category)
                                    try:
                                        latex_file.write(
                                            " & " + cell_format.format(
                                                ("\\textbf{" if highlight else "")
                                                + number_format.format(
                                                    summary_dict[(x_category, y_category)])
                                                + ("}" if highlight else "")))
                                    except KeyError:
                                        latex_file.write(" & " + " " * longest_cell_length)
                                latex_file.write(" \\\\\n")
                            if summary_table.show_global_row and len(y_categories) > 1:
                                latex_file.write("\\midrule\n")
                                latex_file.write(row_header_format.format(f"\\textbf{{{self.global_group_name}}}"))
                                for x_category in x_categories:
                                    highlight = self.should_highlight_cell(
                                        summary_dict=summary_dict, summary_table=summary_table,
                                        x_categories=x_categories, x_category=x_category,
                                        y_categories=y_categories, y_category=None)
                                    try:
                                        latex_file.write(
                                            " & " + cell_format.format(
                                                ("\\textbf{" if highlight else "")
                                                + number_format.format(
                                                    summary_dict[(x_category, None)])
                                                + ("}" if highlight else "")))
                                    except KeyError:
                                        latex_file.write(" & " + " " * longest_cell_length)
                                latex_file.write(" \\\\\n")
                            latex_file.write(r"\bottomrule" + "\n")
                            latex_file.write(r"\end{tabular}" + "\n")

    def should_highlight_cell(self, summary_dict, summary_table, x_categories, x_category,
                              y_categories, y_category):
        highlight = False

        if summary_table.highlight_best_row:
            if summary_table.highlight_best_row.lower() == "low":
                best_value = min(summary_dict[(x_category, y)]
                                 for y in y_categories
                                 if (x_category, y) in summary_dict)
            else:
                assert summary_table.highlight_best_row.lower() == "high"
                best_value = max(summary_dict[(x_category, y)]
                                 for y in y_categories
                                 if (x_category, y) in summary_dict)
            highlight = highlight or summary_dict[(x_category, y_category)] == best_value
        if summary_table.highlight_best_column:
            if summary_table.highlight_best_column.lower() == "low":
                best_value = min(summary_dict[(x, y_category)]
                                 for x in x_categories
                                 if (x, y_category) in summary_dict)
            else:
                assert summary_table.highlight_best_column.lower() == "high"
                best_value = max(summary_dict[(x, y_category)]
                                 for x in x_categories
                                 if (x, y_category) in summary_dict)
            highlight = highlight or summary_dict[(x_category, y_category)] == best_value

        return highlight

    def get_filtered_x_y_categories(self, x_categories, y_categories, reference_group):
        """Take the list of x and y category values and filter out the reference group if show_reference_group
        is False.
        """
        if reference_group and not self.show_reference_group:
            if reference_group in x_categories and reference_group in y_categories:
                enb.logger.warn(f"Reference group {reference_group} is present "
                                f"both in the row and the column headers. "
                                f"It will only be considered as a reference column and not "
                                f"as a reference row.")
            if reference_group in x_categories:
                x_categories = [c for c in x_categories if c != reference_group]
            elif reference_group in y_categories:
                y_categories = [c for c in y_categories if c != reference_group]
            else:
                enb.logger.warn(f"Warning: trying to remove {reference_group=} from "
                                f"{x_categories=} and {y_categories=}, but it was not found in "
                                f"either")

        return list(x_categories), list(y_categories)


class ScalarNumericJointSummary(ScalarNumericSummary):
    """Summary tables for the ScalarNumericJoinAnalyzer class.
    """

    def __init__(self, analyzer, full_df, target_columns, reference_group,
                 group_by, show_global_row, show_global_column,
                 x_header_list, y_header_list, highlight_best_row, highlight_best_column):
        """
        Identical to :meth:`enb.aanalysis.ScalarNumericSummary.__init__`, but calculates
        the scalar numeric description for each x-category/y-category combination (instead of for all samples,
        like ScalarNumericSummary does).
        It also allows defining the column and row order with x_header_list, y_header_list.

        The following parameters differ from :meth:`enb.aanalysis.ScalarNumericSummary.__init__`:

        :param reference_group: if not None, it must be either an x-category value (column header)
          or a y-category value (row header). If present, the data columns are subtracted the averages
          of the entries of the selected category so that that column (if an x-category value is selected)
          or that row (if a y-category value is selected) is all zeros, and all other entries are relative
          to the selected category.
        :param x_header_list: non-empty list of strings corresponding to the x categories (column headers).
          All strings in this list must exist as a category. However, not all categories need to
          be present in this list. If None, all headers are used in alphabetical order.
        :param y_header_list: non-empty list of strings corresponding to the y categories (row headers).
          All strings in this list must exist as a category. However, not all categories need to
          be present in this list. If None, all headers are used in alphabetical order.
        :param highlight_best_row: if not None, it must be "low" or "hight", which determines how the best
          element in each column is selected, and highlighted.
        :param highlight_best_column: if not None, it must be "low" or "hight", which determines how the best
          element in each row is selected, and highlighted.
        :param show_global_row: if True, an "All" row is added with the average of all rows (assuming at least
          two rows are present)
        :param show_global_column: if True, an "All" row is added with the average of all columns (assuming at least
          two columns are present)
        """
        AnalyzerSummary.__init__(
            self=self,
            analyzer=analyzer, full_df=full_df, target_columns=target_columns,
            reference_group=reference_group, group_by=group_by,
            include_all_group=None)
        self.show_global_row = show_global_row
        self.show_global_column = show_global_column
        self.highlight_best_row = highlight_best_row
        self.highlight_best_column = highlight_best_column
        self.x_header_list = [str(x) for x in x_header_list] if x_header_list else x_header_list
        self.y_header_list = [str(y) for y in y_header_list] if y_header_list else y_header_list

        self.category_to_values = {}
        for x_column, y_column, data_column in target_columns:
            # Store the list of unique categories (unique values in the x and y columns)
            self.category_to_values[x_column] = sorted(
                (str(o) for o in self.reference_df[x_column].unique()),
                key=lambda o: str.casefold(str(o))) \
                if x_column not in self.category_to_values else self.category_to_values[x_column]
            self.category_to_values[y_column] = sorted(
                (str(o) for o in self.reference_df[y_column].unique()),
                key=lambda o: str.casefold(str(o))) \
                if y_column not in self.category_to_values else self.category_to_values[y_column]

            # Categories can be sorted y lists are manually passed to this analyzer's get_df method
            for header_list, column_name, label in (
                    (x_header_list, x_column, "x"), (y_header_list, y_column, "y")):
                if header_list is not None:
                    if not header_list:
                        raise ValueError(
                            f"Invalid empty {label}_header_list for {self.__class__.__name__}. "
                            f"It must contain at least one element.")
                    for header in header_list:
                        if header not in self.category_to_values[column_name]:
                            raise ValueError(
                                f"Invalid element {repr(header)} in {label}_header_list={header_list} "
                                f"for {self.__class__.__name__}. "
                                f"In this call, it must contain one or more of "
                                f"{self.category_to_values[column_name]}.")
                    self.category_to_values[column_name] = list(header_list)

            # Add the column functions for computing scalar numeric statistics for each (x,y,data) combination
            self.add_joint_scalar_description_columns(
                x_column=x_column, y_column=y_column, data_column=data_column)

        # Plot data elements are computed after all other columns so that they can use the results
        self.move_render_columns_back()

    def add_joint_scalar_description_columns(self, x_column, y_column, data_column):
        """Add column_functions to this summary table that generate the scalar data
        description of data_column grouped by (x_column, y_column).
        """
        for descriptor in ["min", "max", "avg", "std", "median", "count"]:
            self.add_column_function(
                self,
                fun=functools.partial(self.set_joint_scalar_description,
                                      x_column=x_column, y_column=y_column,
                                      data_column=data_column),
                column_properties=enb.atable.ColumnProperties(
                    name=f"{x_column}_{y_column}_{data_column}_{descriptor}",
                    label=f"{data_column} by {x_column} and {y_column}: {descriptor}",
                    has_dict_values=True))

    def set_joint_scalar_description(self, *args, **kwargs):
        """Set the joint scalar description of a row's column.
        For each descriptor (e.g., min or std), a dictionary is stored indexed by
        the group's (x_column,y_column) categories.
        """
        _self, group_label, row = args
        x_column, y_column, data_column = (
            kwargs[c] for c in ("x_column", "y_column", "data_column"))

        row[f"{x_column}_{y_column}_{data_column}_min"] = dict()
        row[f"{x_column}_{y_column}_{data_column}_max"] = dict()
        row[f"{x_column}_{y_column}_{data_column}_avg"] = dict()
        row[f"{x_column}_{y_column}_{data_column}_std"] = dict()
        row[f"{x_column}_{y_column}_{data_column}_median"] = dict()
        row[f"{x_column}_{y_column}_{data_column}_count"] = dict()

        full_df = _self.label_to_df[group_label]
        full_df = self.remove_nans(full_df)

        # If a reference group is defined, subtract its average
        if _self.reference_group is not None:
            if _self.reference_group in self.category_to_values[x_column]:
                for y_category in self.category_to_values[y_column]:
                    reference_average = full_df[
                        (full_df[y_column] == y_category)
                        & (full_df[x_column] == _self.reference_group)][data_column].mean()
                    full_df.loc[full_df[y_column] == y_category, data_column] -= reference_average
            elif _self.reference_group in self.category_to_values[y_column]:
                for x_category in self.category_to_values[x_column]:
                    reference_average = full_df[
                        (full_df[x_column] == x_category)
                        & (full_df[y_column] == _self.reference_group)][data_column].mean()
                    full_df.loc[full_df[x_column] == x_category, data_column] -= reference_average

        # Add the (x,y) cell values
        for (x_category, y_category), split_df in full_df.groupby([x_column, y_column]):
            if _self.x_header_list and str(x_category) not in _self.x_header_list:
                continue
            if _self.y_header_list and str(y_category) not in _self.y_header_list:
                continue
            for stat, value in _self.numeric_series_to_stat_dict(split_df[data_column]).items():
                row[f"{x_column}_{y_column}_{data_column}_{stat}"][(str(x_category), str(y_category))] = value

        # Add the "All" row
        if _self.show_global_row:
            # If a list of y categories is specified, only those are used for the global row "All"
            if _self.y_header_list:
                global_df = full_df[full_df[y_column].apply(str).isin(_self.y_header_list)]
            else:
                global_df = full_df

            for x_category, split_df in global_df.groupby(x_column):
                for stat, value in _self.numeric_series_to_stat_dict(split_df[data_column]).items():
                    row[f"{x_column}_{y_column}_{data_column}_{stat}"][(str(x_category), None)] = value

        # Add the "All" column
        if _self.show_global_column:
            # If a list of x categories is specified, only those are used for the global column "All"
            if _self.x_header_list:
                global_df = full_df[full_df[x_column].apply(str).isin(_self.x_header_list)]
            else:
                global_df = full_df

            for y_category, split_df in global_df.groupby(y_column):
                for stat, value in _self.numeric_series_to_stat_dict(split_df[data_column]).items():
                    row[f"{x_column}_{y_column}_{data_column}_{stat}"][(None, y_category)] = value

        # Add the "All"x"All" cell
        if _self.show_global_row and _self.show_global_column:
            for stat, value in _self.numeric_series_to_stat_dict(full_df[data_column]).items():
                row[f"{x_column}_{y_column}_{data_column}_{stat}"][(None, None)] = value

    def compute_plottable_data_one_case(self, *args, **kwargs):
        _self, group_label, row = args  # pylint: disable=unused-variable
        x_column, y_column, data_column = kwargs["column_selection"]

        assert kwargs["render_mode"] == "table", (f"Only the 'table' render mode is currently "
                                                  f"supported by {_self.analyzer.__class__.__name__}")

        x_categories, y_categories = _self.analyzer.get_filtered_x_y_categories(
            _self.category_to_values[x_column],
            _self.category_to_values[y_column],
            _self.reference_group)

        avg_dict = row[f"{x_column}_{y_column}_{data_column}_avg"]
        cell_text = [[_self.analyzer.number_format.format(avg_dict[(x_category, y_category)])
                      if (str(x_category), str(y_category)) in avg_dict else ""
                      for x_category in x_categories]
                     for y_category in y_categories]

        if _self.show_global_row and len(y_categories) > 1:
            # show_global option
            y_categories.append(_self.analyzer.global_group_name)
            cell_text.append([_self.analyzer.number_format.format(avg_dict[(x_category, None)])
                              for x_category in x_categories])

        if _self.show_global_column and len(x_categories) > 1:
            x_categories.append("All")
            if _self.show_global_row and len(y_categories) > 1:
                y_cat_iterable = y_categories[:-1] + [None]
            else:
                y_cat_iterable = y_categories
            cell_text = [row + [_self.analyzer.number_format.format(avg_dict[(None, y_category)])]
                         for row, y_category in zip(cell_text, y_cat_iterable)]

        return [enb.plotdata.Table(x_values=x_categories, y_values=y_categories,
                                   cell_text=cell_text, x_label=x_column, y_label=y_column,
                                   cell_alignment=_self.analyzer.cell_alignment,
                                   col_header_aligment=_self.analyzer.col_header_alignment,
                                   row_header_alignment=_self.analyzer.row_header_alignment,
                                   edges=_self.analyzer.edges,
                                   highlight_best_row=_self.highlight_best_row,
                                   highlight_best_column=_self.highlight_best_column)]

    def apply_reference_bias(self):
        """If applicable, group reference bias is applied when computing the joint scalar descriptions.
        """
        pass


class HistogramKeyBinner:
    """Helper class to transform numeric-to-numeric dicts into other dicts
    binning keys like an histogram.
    """

    def __init__(self, min_value, max_value, bin_count, normalize=False):
        """
        :param min_value: minimum expected key value
        :param max_value: maximum expected key value
        :param bin_count: number of bins in the histogram
        :param normalize: if True, the relative frequencies are computed,
          instead of the absolute frequences
        """
        # pylint: disable=too-many-locals
        self.min_value = min_value
        self.max_value = max_value
        self.bin_count = bin_count
        assert self.bin_count > 0
        self.bin_width = max(1e-10, (max_value - min_value) / self.bin_count)
        self.intervals = [
            (min_value, min(min_value + self.bin_width, max_value))
            for min_value in
            np.linspace(min_value, max(min_value, max_value - self.bin_width),
                        self.bin_count, endpoint=True)]

        # Define the [a,b), ..., [y,z] binned keys (used by default for
        # plotting)
        self.binned_keys = []
        for i, interval in enumerate(self.intervals):
            interval_str = "["
            interval_str += ",".join(
                f"{v:.2f}" if int(v) != v else str(v) for v in interval)
            interval_str += ")" if i < len(self.intervals) - 1 else "]"
            self.binned_keys.append(interval_str)
        self.normalize = normalize

    def __call__(self, input_dict):
        """When an instance of this class is called, it takes an input
        dictionary with numeric keys and values (e.g., something like {x:f(x)
        for x in x_values}). The specified range of key values is split into
        a given number of bins (intervals), and a dictionary is returned,
        with keys being those intervals and the values being the sum of all
        elements in the input dict with keys inside that bin.
        """
        index_to_sum = [0] * len(self.binned_keys)
        total_sum = 0
        ignored_sum = 0
        for k, v in input_dict.items():
            try:
                index_to_sum[
                    math.floor((k - self.min_value) / self.bin_width)] += v
            except IndexError:
                if k == self.max_value:
                    index_to_sum[-1] += v
                else:
                    ignored_sum += v
            total_sum += v

        if ignored_sum > 0 and enb.logger.level_active(enb.logger.level_debug.name):
            enb.log.warn(
                f"{self.__class__.__name__} is ignorning "
                f"{100 * ignored_sum / total_sum:.6f}% "
                f"of the values, which lie outside "
                f"{self.min_value, self.max_value}. "
                f"This is likely OK if you specified x_min or x_max manually.")

        output_dict = collections.OrderedDict()
        for i, k in enumerate(self.binned_keys):
            output_dict[k] = index_to_sum[i] / (
                total_sum if self.normalize else 1)

        return output_dict

    def __repr__(self):
        return f"{self.__class__.__name__}" \
               f"({','.join(f'{k}={v}' for k, v in self.__dict__.items())})"


def columnname_to_labels(column_name):
    """Guess x_label and y_label from a name column. If _to_ is found once in
    the string, x_label will be obtained from the text to the left,
    and y_label from the text to the right. Otherwise, x_label is set using
    the complete column_name string, and y_label is None
    """
    parts = column_name.split("_to_")
    if len(parts) == 2:
        x_label, y_label = clean_column_name(parts[0]), clean_column_name(
            parts[1])
    else:
        x_label, y_label = clean_column_name(column_name), None
    return x_label, y_label
