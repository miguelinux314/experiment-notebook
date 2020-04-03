#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Automatic analysis and report of of pandas :class:`pandas.DataFrames`
(e.g., produced by :class:`enb.experiment.Experiment` instances)
using pyplot
"""

import os
import itertools
import math
import collections
import matplotlib
from matplotlib.ticker import (AutoMinorLocator, MaxNLocator, LogLocator)

matplotlib.use('Agg')
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import ray

from enb.atable import parse_dict_string
from enb import plotdata
from enb import config
from enb.config import get_options

options = get_options()


@ray.remote
def render_plds_by_group(pds_by_group_name, output_plot_path, column_properties, horizontal_margin, global_x_label,
                         y_min=None, y_max=None, y_labels_by_group_name=None, color_by_group_name=None,
                         global_y_label="Relative frequency", semilog_hist_min=1e-10, options=None):
    """Ray wrapper for render_plds_by_group_local"""
    return render_plds_by_group_local(pds_by_group_name=pds_by_group_name, output_plot_path=output_plot_path,
                                      column_properties=column_properties, global_x_label=global_x_label,
                                      horizontal_margin=horizontal_margin, y_min=y_min, y_max=y_max,
                                      y_labels_by_group_name=y_labels_by_group_name,
                                      color_by_group_name=color_by_group_name, global_y_label=global_y_label,
                                      semilog_hist_min=semilog_hist_min, options=options)


@config.propagates_options
def render_plds_by_group_local(pds_by_group_name, output_plot_path, column_properties, global_x_label,
                               horizontal_margin, y_min=None, y_max=None, y_labels_by_group_name=None,
                               color_by_group_name=None, global_y_label="Relative frequency", semilog_hist_min=1e-10,
                               options=None):
    """Render lists of plotdata.PlottableData instances indexed by group name,
    each group in a row, with a shared X axis, which is set automatically in common
    for all groups for easier comparison.

    :param pds_by_group_name: dictionary of lists of PlottableData instances
    :param output_plot_path: path to the file to be created with the plot
    :param column_properties: ColumnProperties instance for the column being plotted
    :param y_min, y_max: range of values to be plotted in the Y axis. If any is None,
      the plot automatically adjusts to column_properties, or the data if limits
      are not specified there either.
    :param global_x_label, param global_y_label: common X and Y labels
    :param horizontal_margin: Total horizontal margin (in plot units) to be left horizontally
    :param y_labels_by_group_name: if not None, a dictionary of labels for the groups,
      indexed with the same keys as pds_by_group_name
    :param color_by_group_name: if not None, a dictionary of pyplot colors for the groups,
      indexed with the same keys as pds_by_group_name
    :param options: additional runtime configuration options (see config.py)
    """
    if options and options.verbose > 1:
        print(f"[R]endering groupped Y plot to {output_plot_path} ...")

    y_min = column_properties.hist_min if y_min is None else y_min
    y_min = max(semilog_hist_min, y_min if y_min is not None else 0) if column_properties.semilog_y else y_min
    y_max = column_properties.hist_max if y_max is None else y_max

    options = options if options is None else options
    sorted_group_names = sorted(pds_by_group_name.keys(),
                                key=lambda s: "" if s == "all" else s.strip().lower())

    y_labels_by_group_name = {g: g for g in sorted_group_names} \
        if y_labels_by_group_name is None else y_labels_by_group_name
    if color_by_group_name is None:
        color_by_group_name = {}
        for i, group_name in enumerate(sorted_group_names):
            color_by_group_name[group_name] = f"C{i % 10}"
    os.makedirs(os.path.dirname(output_plot_path), exist_ok=True)
    fig, group_axis_list = plt.subplots(
        nrows=len(sorted_group_names), ncols=1, sharex=True, sharey=False)
    if len(sorted_group_names) == 1:
        group_axis_list = [group_axis_list]

    semilog_x, semilog_y = False, False
    x_min, x_max = None, None
    for i, (group_name, group_axes) in enumerate(zip(
            sorted_group_names, group_axis_list)):
        if column_properties:
            x_min = column_properties.plot_min
            x_max = column_properties.plot_max
        if x_min is None:
            x_min = min(min(pd.x_values) for pd in pds_by_group_name[group_name])
        if x_max is None:
            x_max = max(max(pd.x_values) for pd in pds_by_group_name[group_name])
        if x_max - x_min > 1:
            x_min = math.floor(x_min)
            x_max = math.ceil(x_max)

        group_color = color_by_group_name[group_name]
        for pld in pds_by_group_name[group_name]:
            pld.x_label = None
            pld.y_label = None
            d = dict(color=group_color)
            try:
                pld.extra_kwargs.update(d)
            except AttributeError:
                pld.extra_kwargs = d

            if column_properties and column_properties.plot_max is not None:
                pld.x_values = [x for x in pld.x_values if x <= column_properties.plot_max + horizontal_margin]
                pld.y_values = pld.y_values[:len(pld.x_values)]
            try:
                pld.render(axes=group_axes)
            except Exception as ex:
                raise Exception(f"Error rendering {pld} -- {group_name} -- {output_plot_path}") from ex
            semilog_x = semilog_x or (column_properties.semilog_x if column_properties else False)
            semilog_y = semilog_y or (column_properties.semilog_y if column_properties else False)

    for (group_name, group_axes) in zip(sorted_group_names, group_axis_list):
        group_axes.get_xaxis().set_major_locator(MaxNLocator(nbins="auto", integer=True, min_n_ticks=5))
        group_axes.get_xaxis().set_minor_locator(AutoMinorLocator())

        group_axes.set_ylim(y_min, y_max)
        if semilog_x:
            group_axes.semilogx()
        if semilog_y:
            group_axes.semilogy()
            if len(sorted_group_names) <= 2:
                numticks = 11
            elif len(sorted_group_names) <= 5:
                numticks = 6
            elif len(sorted_group_names) <= 10:
                numticks = 4
            else:
                numticks = 3
            group_axes.get_yaxis().set_major_locator(LogLocator(numticks=numticks))
            group_axes.grid(True, "major", axis="y", alpha=0.2)
        else:
            group_axes.get_yaxis().set_major_locator(MaxNLocator(nbins="auto", integer=False))
            group_axes.get_yaxis().set_minor_locator(AutoMinorLocator())
        group_axes.get_yaxis().set_label_position("right")
        group_axes.set_ylabel(y_labels_by_group_name[group_name], rotation=0,
                              ha="left", va="center")

    plt.xlabel(global_x_label)
    if column_properties and column_properties.hist_label_dict is not None:
        x_tick_values = sorted(column_properties.hist_label_dict.keys())
        x_tick_labels = [column_properties.hist_label_dict[x] for x in x_tick_values]
        plt.xticks(x_tick_values, x_tick_labels)

    plt.xlim(x_min - horizontal_margin / 2, x_max + horizontal_margin / 2)
    if len(sorted_group_names) > 5:
        plt.subplots_adjust(hspace=0.3)
    elif len(sorted_group_names) > 10:
        plt.subplots_adjust(hspace=0.5)

    if global_y_label:
        fig.text(0.0, 0.5, global_y_label, va='center', rotation='vertical')

    plt.savefig(output_plot_path, bbox_inches="tight")
    plt.close()
    if options.verbose:
        print(f"Saved plot to {output_plot_path}")


class Analyzer:
    def analyze_df(self, full_df, target_columns,
                   output_plot_dir, output_csv_file=None,
                   column_to_properties=None, group_by=None, show_global=True,
                   version_name=None):
        raise NotImplementedError(self)


class ScalarDistributionAnalyzer(Analyzer):
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
    errorbar_alpha = 0.6

    semilog_hist_min = 1e-5

    def analyze_df(self, full_df, target_columns,
                   output_plot_dir, output_csv_file=None,
                   column_to_properties=None, group_by=None, show_global=True,
                   version_name=None):
        """Perform an analysis of target_columns, grouping as specified.

        :param output_csv_file: path where the CSV report is stored
        :param output_plot_dir: path where the distribution plots are stored
        :param target_columns: list of column names for which an analysis is to be performed.
          A single string is also accepted (as a single column name).
        :param column_to_properties: if not None, a dict indexed by column name (as given
          in the column parameter of the @atable.column_function decorator), entries being
          an atable.ColumnProperties instance
        :param group_by: if not None, analysis is performed after grouping by that column name
        :param show_global: if True, distribution for all entries (without grouping) is also shown
        :param version_name: if not None, the version name is prepended to the x axis' label
        """
        target_columns = [target_columns] if isinstance(target_columns, str) else target_columns
        column_to_properties = collections.defaultdict(None) if column_to_properties is None else column_to_properties
        min_max_by_column = get_scalar_min_max_by_column(
            df=full_df, target_columns=target_columns, column_to_properties=column_to_properties)

        pooler_suffix_tuples = [(pd.DataFrame.min, "min"), (pd.DataFrame.max, "max"),
                                (pd.DataFrame.mean, "avg"), (pd.DataFrame.std, "std")]
        analysis_df = pd.DataFrame(columns=["count"] + list(
            itertools.chain([f"{column}_{suffix}"
                             for column in target_columns
                             for _, suffix in pooler_suffix_tuples])))

        # Fill analysis_df and gather pltdata.PlottableData instances
        label_column_to_pds = {}
        lengths_by_group_name = {}
        if group_by:
            for group_name, group_df in full_df.groupby(group_by):
                pool_scalar_into_analysis_df(analysis_df=analysis_df, analysis_label=group_name, data_df=group_df,
                                             pooler_suffix_tuples=pooler_suffix_tuples, columns=target_columns)
                analysis_df.at[group_name, "count"] = len(group_df)
                label_column_to_pds.update({
                    (group_name, column): scalar_column_to_pds(
                        column=column, properties=column_to_properties[column],
                        df=group_df, min_max_by_column=min_max_by_column,
                        hist_bin_count=self.hist_bin_count, bar_width_fraction=self.bar_width_fraction,
                        semilogy_min_y=self.semilog_hist_min,
                        bar_alpha=self.bar_alpha, errorbar_alpha=self.errorbar_alpha)
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
                    semilogy_min_y=self.semilog_hist_min,
                    bar_alpha=self.bar_alpha, errorbar_alpha=self.errorbar_alpha)
                for column in target_columns})
            lengths_by_group_name["all"] = len(full_df)
        if output_csv_file:
            os.makedirs(os.path.dirname(output_csv_file), exist_ok=True)
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

            histogram_bin_width = None
            if column_name in column_to_properties and column_to_properties[column_name].hist_bin_width is not None:
                histogram_bin_width = column_to_properties[column_name].hist_bin_width
            if histogram_bin_width is None:
                histogram_bin_width = ((min_max_by_column[column_name][1] - min_max_by_column[column_name][0])
                                       / self.hist_bin_count)
            y_min = 0 if not column_name in column_to_properties \
                         or not column_to_properties[column_name].semilog_y else self.semilog_hist_min
            y_max = 1
            expected_return_ids.append(
                render_plds_by_group.remote(
                    options=ray.put(options),
                    pds_by_group_name=ray.put(pds_by_group_name),
                    output_plot_path=ray.put(os.path.join(output_plot_dir,
                                                          f"distribution_{column_name}.pdf")),
                    column_properties=ray.put(column_to_properties[column_name]
                                              if column_name in column_to_properties else None),
                    horizontal_margin=ray.put(histogram_bin_width),
                    global_x_label=ray.put(x_label),
                    y_labels_by_group_name=ray.put({group: f"{group} ({length})"
                                                    for group, length in
                                                    lengths_by_group_name.items()}),
                    y_min=ray.put(y_min), y_max=ray.put(y_max),
                    semilog_hist_min=self.semilog_hist_min))

        ray.get(expected_return_ids)

        print("TODO: fill analysis df")
        return analysis_df


def scalar_column_to_pds(column, properties, df, min_max_by_column, hist_bin_count, bar_width_fraction,
                         semilogy_min_y, bar_alpha=0.5, errorbar_alpha=0.75, ):
    """Add the pooled values and get a PlottableData instance with the
    relative distribution
    """
    column_df = df[column]
    # Histogram with bins in [0,1] that sum 1
    hist_y_values, bin_edges = np.histogram(column_df.values, bins=hist_bin_count,
                                            range=min_max_by_column[column],
                                            density=False)
    hist_y_values = hist_y_values / len(column_df)
    assert abs(sum(hist_y_values) - 1) < 1e-10, \
        f"The forced range for {column} {tuple(min_max_by_column[column])} " \
        f"misses {100 * (1 - sum(hist_y_values)):.0f}% of the actual values. " \
        f"Actual range is ({column_df.min(), column_df.max()}."
    hist_y_values = hist_y_values / hist_y_values.sum()

    x_label = column if not properties.label else properties.label

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
    if properties and properties.semilog_y:
        average_point_position = 10 ** (0.5 * (math.log10(semilogy_min_y) + math.log10(1)))
    error_lines = plotdata.ErrorLines(
        x_values=[column_df.mean()],
        y_values=[average_point_position],
        marker_size=5,
        alpha=errorbar_alpha,
        err_neg=[column_df.std()], err_pos=[column_df.std()],
        line_width=2,
        vertical=False)

    return [plot_data, error_lines]


def pool_scalar_into_analysis_df(analysis_df, analysis_label, data_df, pooler_suffix_tuples, columns):
    """Pull columns into analysis using the poolers in pooler_suffix_tuples, with the specified
    suffixes.
    """
    for column in columns:
        for pool_fun, suffix in pooler_suffix_tuples:
            analysis_df.at[analysis_label, f"{column}_{suffix}"] = pool_fun(data_df[column])


def get_scalar_min_max_by_column(df, target_columns, column_to_properties):
    """Get a dictionary indexed by column name with minimum and maximum values.
    (useful e.g., for normalized processing of subgroups)
    """
    min_max_by_column = {}
    for column in target_columns:
        if column_to_properties and column in column_to_properties:
            min_max_by_column[column] = [column_to_properties[column].plot_min,
                                         column_to_properties[column].plot_max]
        else:
            min_max_by_column[column] = [None, None]
        if min_max_by_column[column][0] is None:
            min_max_by_column[column][0] = df[column].min()
        if min_max_by_column[column][1] is None:
            min_max_by_column[column][1] = df[column].max()

        if min_max_by_column[column][1] > 1:
            min_max_by_column[column][0] = \
                math.floor(min_max_by_column[column][0])
            min_max_by_column[column][1] = \
                math.ceil(min_max_by_column[column][1])
    return min_max_by_column


def histogram_overlap_column_to_pds(df, column, column_properties=None, line_alpha=0.2, line_width=0.5):
    pld_list = []
    for d in df[column]:
        x_values = sorted(d.keys())
        y_values = [d[x] for x in x_values]
        pld_list.append(plotdata.LineData(
            x_values=x_values, y_values=y_values, alpha=line_alpha,
            extra_kwargs=dict(lw=line_width)))
    return pld_list


class HistogramDistributionAnalyzer(Analyzer):
    """Analyze DFs with vector mappings, i.e., dictionary-like instances from
    value to weights (e.g., counts).
    """
    alpha_global = 0.5
    alpha_individual = 0.25

    histogram_bin_width = 1

    # Fraction in 0,1 of the bar width for histogram
    bar_width_fraction = 1
    # Margin height in heights of each individual histogram
    histogram_margin = 0.3

    subdivision_count = 10

    hist_min = 0
    hist_max = 1
    semilog_hist_min = 1e-5

    color_sequence = ["blue", "orange", "r", "g", "magenta", "yellow"]

    def analyze_df(self, full_df, target_columns,
                   output_plot_dir, output_csv_file=None, show_global=True,
                   column_to_properties=None, group_by=None, version_name=None):
        """
        Analyze a column, where each cell contains a real to real mapping.
        :param full_df: full df from which the column is to be extracted
        :param target_columns: list of column names containing tensor (mapping) data
        :param output_plot_dir: path of the directory where the plot is to be saved
        :param output_csv_file: path of the csv file where basic analysis results are stored
        :param column_to_properties: dictionary with ColumnProperties entries
        :param group_by: if not None, the name of the column to be used for grouping
        :param version_name: if not None, a string identifying the file version that
          produced full_df
        """
        full_df = pd.DataFrame(full_df)
        column_to_properties = collections.defaultdict(None) if column_to_properties is None else column_to_properties

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
                group: f"{group} (n={length})"
                for group, length in lengths_by_group.items()
            }
            x_label = column_to_properties[column_name].label if column_name in column_to_properties else None
            x_label = clean_column_name(column_name) if x_label is None else x_label
            if version_name:
                x_label = f"{version_name} {x_label}"
            y_label = column_to_properties[column_name].hist_label if column_name in column_to_properties else None
            y_label = "Relative frequency" if y_label is None else y_label
            #
            y_min = column_to_properties[column_name].hist_min if column_name in column_to_properties else None
            y_min = self.hist_min if y_min is None else y_min
            if y_min is not None and column_to_properties[column_name].semilog_y:
                y_min = max(y_min, self.semilog_hist_min)
            y_max = column_to_properties[column_name].hist_max if column_name in column_to_properties else None
            y_max = self.hist_max if y_max is None else y_max
            #
            return_ids.append(render_plds_by_group.remote(
                options=ray.put(options),
                pds_by_group_name=ray.put(pds_by_group_name),
                output_plot_path=ray.put(output_plot_path),
                horizontal_margin=ray.put(histogram_bin_width),
                column_properties=ray.put(column_properties),
                global_x_label=ray.put(x_label),
                global_y_label=ray.put(y_label),
                y_min=ray.put(y_min),
                y_max=ray.put(y_max),
                y_labels_by_group_name=ray.put(labels_by_group)))

        if options.verbose > 1:
            print(f"TODO: Save results in CSV at output_csv_file?")

        return ray.get(return_ids)


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
                                            err_neg=global_hist_std,
                                            err_pos=global_hist_std,
                                            marker_size=0.5,
                                            alpha=individual_pd_alpha,
                                            vertical=True,
                                            line_width=0.5))

    return produced_pds


class OverlappedHistogramAnalyzer(HistogramDistributionAnalyzer):
    """Plot multiple overlapped histograms (e.g. dicts from float to float)
    per group, one per row
    """
    line_alpha = 0.3
    line_width = 0.5

    def analyze_df(self, full_df, target_columns,
                   output_plot_dir, output_csv_file=None,
                   column_to_properties=None, group_by=None, show_global=True,
                   version_name=None):
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

            #
            y_min = column_to_properties[column_name].hist_min if column_name in column_to_properties else None
            y_min = self.hist_min if y_min is None else y_min
            if y_min is not None and column_to_properties[column_name].semilog_y:
                y_min = max(y_min, self.semilog_hist_min)
            y_max = column_to_properties[column_name].hist_max if column_name in column_to_properties else None
            y_max = self.hist_max if y_max is None else y_max
            #

            result_ids.append(render_plds_by_group.remote(
                options=ray.put(options),
                pds_by_group_name=ray.put(pds_by_group),
                output_plot_path=ray.put(output_plot_path),
                column_properties=ray.put(properties), horizontal_margin=ray.put(0),
                global_x_label=ray.put(x_label), y_labels_by_group_name=ray.put(y_labels_by_group_name),
                global_y_label=ray.put(y_label), color_by_group_name=ray.put(None),
                y_min=ray.put(y_min), y_max=ray.put(y_max)))

        ray.get(result_ids)
        if options.verbose > 1:
            "TODO: fill csv and save to output_csv_file"


class TwoColumnScatterAnalyzer(Analyzer):
    marker_size = 5
    alpha = 0.5

    def analyze_df(self, full_df, target_columns,
                   output_plot_dir, output_csv_file=None,
                   column_to_properties=None, group_by=None, show_global=True,
                   version_name=None):
        """
        :param target_columns: must be a list of tuple-like instances, each with two elements.
          The first element is the name of the column to use for the x axis,
          the second element is the name of the column for the y axis.
        """
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
            pds_by_group = {}
            x_label = column_to_properties[column_x].label if column_x in column_to_properties else None
            x_label = clean_column_name(column_x) if x_label is None else x_label
            y_label = column_to_properties[column_y].label if column_y in column_to_properties else None
            y_label = clean_column_name(column_y) if y_label is None else y_label
            if group_by is not None:
                for group_label, group_df in full_df.groupby(by=group_by):
                    x_values, y_values = zip(*sorted(zip(
                        group_df[column_x].values, group_df[column_y].values)))
                    pds_by_group[group_label] = [plotdata.ScatterData(
                        x_values=x_values, y_values=y_values,
                        alpha=self.alpha)]
            if group_by is None or show_global:
                x_values, y_values = zip(*sorted(zip(
                    full_df[column_x].values, full_df[column_y].values)))
                pds_by_group["all"] = [plotdata.ScatterData(
                    x_values=x_values, y_values=y_values, alpha=self.alpha)]

            output_plot_path = os.path.join(output_plot_dir, f"twocolumns_scatter_{column_x}_VS_{column_y}.pdf")

            all_plds = [pld for pds in pds_by_group.values() for pld in pds]
            for pld in all_plds:
                pld.alpha = self.alpha
                pld.marker_size = self.marker_size
            global_x_min = min(min(pld.x_values) for pld in all_plds)
            global_x_max = max(max(pld.x_values) for pld in all_plds)
            global_y_min = min(min(pld.y_values) for pld in all_plds)
            global_y_max = max(max(pld.y_values) for pld in all_plds)

            pds_by_group_id = ray.put(pds_by_group)

            expected_returns.append(render_plds_by_group.remote(
                pds_by_group_name=pds_by_group_id,
                output_plot_path=ray.put(output_plot_path),
                column_properties=ray.put(column_to_properties[column_x] if column_x in column_to_properties else None),
                horizontal_margin=ray.put(0.05 * (global_x_max - global_x_min)),
                y_min=ray.put(global_y_min - 0.05 * (global_y_max - global_y_min)),
                y_max=ray.put(global_y_max + 0.05 * (global_y_max - global_y_min)),
                global_x_label=ray.put(x_label), global_y_label=ray.put(y_label),
                options=ray.put(options)))

        ray.wait(expected_returns)


def get_histogram_dicts(df, column):
    """Get a list of dicts, each one representing one histogram stored at row, column
    for al rows in df in the order given by the index.
    """
    parsed_dicts = [parse_dict_string(column_value) for column_value in df[column]]
    assert len(parsed_dicts) == len(df)
    return parsed_dicts


def column_name_to_labels(column_name):
    """Guess x_label and y_label from a name column.
    If _to_ is found once in the string, x_label will be obtained from the text to the left,
    and y_label from the text to the right.
    Otherwise, x_label is set using the complete column_name string, and y_label is None
    """
    parts = column_name.split("_to_")
    if len(parts) == 2:
        x_label, y_label = clean(parts[0]), clean(parts[1])
    else:
        x_label, y_label = clean(column_name), None
    return x_label, y_label


def clean_column_name(column_name):
    """Return a cleaned version of the column name, more indicated for display.
    """
    return column_name.replace("_", " ").strip()
