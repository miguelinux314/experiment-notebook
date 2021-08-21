#!/usr/bin/env python3
"""Automatic analysis and report of of pandas :class:`pandas.DataFrames`
(e.g., produced by :class:`enb.experiment.Experiment` instances)
using pyplot.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/01/01"

import os
import itertools
import math
import collections
import sortedcontainers
import re
import glob

import pdf2image
import numpy as np
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



class Analyzer:
    def analyze_df(self, full_df, target_columns, output_plot_dir, output_csv_file=None, column_to_properties=None,
                   group_by=None, group_name_order=None, show_global=True, show_count=True, version_name=None,
                   adjust_height=False):
        """
        Analyze a :class:`pandas.DataFrame` instance, producing plots and/or analysis files.

        :param adjust_height:
        :param full_df: full DataFrame instance with data to be plotted and/or analyzed
        :param target_columns: list of columns to be analyzed. Typically a list of column names, although
          each subclass may redefine the accepted format (e.g., pairs of column names)
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
        :param show_global: this flags controls whether results for the full_df (without grouping) are
          to be included in the results. If no grouping is selected, this options is ignored.
        :param show_count: determines whether the number of element per group should be shown in the group label
        :param version_name: if not None, a string identifying the file version that produced full_df is displayed
          where relevant.
        """
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

    def analyze_df(self, full_df, target_columns, output_plot_dir=None, output_csv_file=None, column_to_properties=None,
                   group_by=None, group_name_order=None, show_global=True, show_count=True, version_name=None,
                   adjust_height=False, y_labels_by_group_name=None):
        """Perform an analysis of target_columns, grouping as specified.

        :param adjust_height: adjust height to the maximum height contained in the y_values
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

        # Fill analysis_df and gather pltdata.PlottableData instances
        label_column_to_pds = {}
        lengths_by_group_name = {}
        if group_by:
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

            histogram_bin_width = None
            if column_name in column_to_properties and column_to_properties[column_name].hist_bin_width is not None:
                histogram_bin_width = column_to_properties[column_name].hist_bin_width
            if histogram_bin_width is None:
                try:
                    histogram_bin_width = ((min_max_by_column[column_name][1] - min_max_by_column[column_name][0])
                                           / self.hist_bin_count)
                except TypeError:
                    histogram_bin_width = 1 / self.hist_bin_count
            y_min = 0 if not column_name in column_to_properties \
                         or not column_to_properties[column_name].semilog_y else self.semilog_hist_min

            if adjust_height:
                y_max = 0
                for pds in pds_by_group_name.values():
                    for pld in pds:
                        if not isinstance(pld, plotdata.BarData):
                            continue
                        y_max = max(y_max, max(pld.y_values))
                for pds in pds_by_group_name.values():
                    for pld in pds:
                        if isinstance(pld, plotdata.ErrorLines):
                            pld.y_values = [0.5 * (y_max - y_min)]
            else:
                y_max = 1

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
                    horizontal_margin=ray.put(histogram_bin_width),
                    global_x_label=ray.put(x_label),
                    y_labels_by_group_name=ray.put(y_labels_by_group_name),
                    x_min=ray.put(x_min), x_max=ray.put(x_max),
                    y_min=ray.put(y_min), y_max=ray.put(y_max),
                    semilog_hist_min=ray.put(self.semilog_hist_min),
                    group_name_order=ray.put(group_name_order)))

        ray.get(expected_return_ids)

        return analysis_df


def scalar_column_to_pds(column, properties, df, min_max_by_column, hist_bin_count, bar_width_fraction,
                         semilogy_min_y, bar_alpha=0.5, errorbar_alpha=0.75, ):
    """Add the pooled values and get a PlottableData instance with the
    relative distribution
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
            if options.verbose:
                print(f"[W]arning: not all samples included in the scalar distribution for {column} "
                      f"(used {100 * (sum(hist_y_values)):.1f}% of the samples)."
                      f"Note that infinite values are not accounted for, and the plot_min "
                      f"and plot_max column properties affect this range.")
        else:
            if options.verbose:
                print(f"[W]arning: not all samples included in the scalar distribution for {column} "
                      f"(used {100 * (sum(hist_y_values)):.1f}% of the samples)."
                      f"Note that plot_min and plot_max column properties might be affecting this range.")

    hist_y_values = hist_y_values / hist_y_values.sum() \
        if hist_y_values.sum() > 0 and len(hist_y_values) > 0 and np.isfinite(hist_y_values / hist_y_values.sum()).all() \
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
        alpha=errorbar_alpha,
        err_neg_values=[column_df.std()], err_pos_values=[column_df.std()],
        line_width=2,
        vertical=False)

    return [plot_data, error_lines]


def pool_scalar_into_analysis_df(analysis_df, analysis_label, data_df, pooler_suffix_tuples, columns):
    """Pull columns into analysis using the poolers in pooler_suffix_tuples, with the specified
    suffixes.
    """
    analysis_label = analysis_label if not isinstance(analysis_label, bool) else str(analysis_label)

    for column in columns:
        for pool_fun, suffix in pooler_suffix_tuples:
            analysis_df.at[analysis_label, f"{column}_{suffix}"] = pool_fun(data_df[column])


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

        if min_max_by_column[column][0] is None:
            min_max_by_column[column][0] = df[column].min()
            if math.isinf(min_max_by_column[column][0]) or math.isnan(min_max_by_column[column][0]):
                try:
                    min_max_by_column[column][0] = min(v for v in df[column]
                                                       if not math.isinf(v) and not math.isnan(v))
                except ValueError:
                    min_max_by_column[column][0] = 0

        if min_max_by_column[column][1] is None:
            min_max_by_column[column][1] = df[column].max()
            if math.isinf(min_max_by_column[column][1]) or math.isnan(min_max_by_column[column][1]):
                try:
                    min_max_by_column[column][1] = max(v for v in df[column]
                                                       if not math.isinf(v) and not math.isnan(v))
                except ValueError:
                    min_max_by_column[column][1] = 1

        if min_max_by_column[column][1] > 1:
            if column not in column_to_properties or column_to_properties[column].plot_min is None:
                min_max_by_column[column][0] = math.floor(min_max_by_column[column][0])
            if column not in column_to_properties or column_to_properties[column].plot_max is None:
                min_max_by_column[column][1] = math.ceil(min_max_by_column[column][1])

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

    # Default histogram bin width
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

    def analyze_df(self, full_df, target_columns, output_plot_dir=None, output_csv_file=None, column_to_properties=None,
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
        if options.verbose:
            print(f"[D]eprecated class {self.__class__.__name__}. "
                  f"Please use {ScalarDictAnalyzer.__class__.__name__} instead.")

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
                y_min = max(y_min, self.semilog_hist_min)
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

    def analyze_df(self, full_df, target_columns, output_plot_dir=None, output_csv_file=None, column_to_properties=None,
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
                y_min = max(y_min, self.semilog_hist_min)
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

        ray.get(result_ids)
        if options.verbose > 1:
            "TODO: fill csv and write to output_csv_file"


class TwoColumnScatterAnalyzer(Analyzer):
    marker_size = 5
    alpha = 0.5

    def analyze_df(self, full_df, target_columns, output_plot_dir=None, output_csv_file=None, column_to_properties=None,
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


class TwoColumnLineAnalyzer(Analyzer):
    alpha = 0.5

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
    """When called, bin a dictionary that represents a probability distribution or frequency count,
    and store the binned dict. The binning
    process consists in adding all values included in the dictionary.

    It can be used as parameter for combine_keys in ScalarDictAnalyzer.analyze_df.
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
        """Combine the keys of input_dict. See the class' docstring for rationale and usage.
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
            print(f"[W]arning: {self.__class__.__name__} ignorning {100 * ignored_sum / total_sum:.6f}% "
                  f"of the values, which lie outside {self.min_value, self.max_value}. This is OK if "
                  f"you specified x_min or x_max when using ScalarDictAnalyzer.get_df()")

        output_dict = collections.OrderedDict()
        for i, k in enumerate(self.binned_keys):
            output_dict[k] = index_to_sum[i] / (total_sum if self.normalize else 1)

        return output_dict

    def __repr__(self):
        return f"{self.__class__.__name__}({','.join(f'{k}={v}' for k, v in self.__dict__.items())})"


class ScalarDictAnalyzer(Analyzer):
    """Analyzer to plot columns that contain dictionary data with scalar entries.
    """
    #
    default_bin_count = 16

    def analyze_df(self, full_df, target_columns, output_plot_path=None, combine_keys=None,
                   x_min=None, x_max=None, mass_fraction=None, epsilon=0.0001, width_fraction=1,
                   key_to_x=None, key_list=None, output_plot_dir=None, output_csv_file=None, column_to_properties=None,
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


def column_name_to_labels(column_name):
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
    return column_name.replace("_", " ").strip()


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
