#!/usr/bin/env python3
"""Render plots using matplotlib and enb.plotdata.PlottableData instances.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2023/03/09"

import os
import math
import natsort
import itertools
import numpy as np
import matplotlib
import matplotlib.patheffects
import matplotlib.patches
import matplotlib.ticker
from matplotlib import pyplot as plt
import enb
from enb.misc import CircularList
from enb.config import options

matplotlib.use("Agg")

marker_cycle = CircularList(
    ["o", "X", "s", "*", "p", "P", "d", "H", "d", "<", ">", "+"])
color_cycle = CircularList([f"C{i}" for i in [0, 1, 2, 3, 6, 7, 9, 8, 5, 10]])
pattern_cycle = CircularList(["//", "\\\\", "OO", "**"])


@enb.parallel.parallel()
def parallel_render_plds_by_group(
        pds_by_group_name, output_plot_path, column_properties,
        global_x_label, global_y_label,
        # General figure configuration
        combine_groups=False, color_by_group_name=None, group_name_order=None,
        fig_width=None, fig_height=None,
        legend_column_count=None,
        force_monochrome_group=True,
        # Axis configuration
        show_grid=None, show_subgrid=None,
        grid_alpha=0.6, subgrid_alpha=0.4,
        semilog_y=None, semilog_y_base=10, semilog_y_min_bound=1e-10,
        group_row_margin=None,
        # Axis limits
        x_min=None, x_max=None, y_min=None, y_max=None,
        horizontal_margin=None, vertical_margin=None,
        global_y_label_margin=None,
        # Optional axis labeling
        y_labels_by_group_name=None,
        # Ticks
        tick_direction="in",
        x_tick_list=None, x_tick_label_list=None, x_tick_label_angle=0,
        y_tick_list=None, y_tick_label_list=None,
        left_y_label=False,
        # Additional plottable data instances
        extra_plds=tuple(),
        # Plot title
        plot_title=None, title_y=None,
        # Legend
        show_legend=True, legend_position=None,
        # Matplotlib styles
        style_list=tuple()):
    """Ray wrapper for render_plds_by_group. See that method for parameter
    information.
    """
    # pylint: disable=too-many-arguments,too-many-locals
    try:
        if enb.parallel_ray.is_remote_node():
            os.chdir(os.path.expanduser(
                enb.parallel_ray.RemoteNode.remote_project_mount_path))
        else:
            os.chdir(options.project_root)

        return render_plds_by_group(pds_by_group_name=pds_by_group_name,
                                    output_plot_path=output_plot_path,
                                    column_properties=column_properties,
                                    global_x_label=global_x_label,
                                    horizontal_margin=horizontal_margin,
                                    vertical_margin=vertical_margin,
                                    y_min=y_min, y_max=y_max,
                                    force_monochrome_group=force_monochrome_group,
                                    x_min=x_min, x_max=x_max,
                                    y_labels_by_group_name=y_labels_by_group_name,
                                    color_by_group_name=color_by_group_name,
                                    global_y_label=global_y_label,
                                    global_y_label_margin=global_y_label_margin,
                                    combine_groups=combine_groups,
                                    semilog_y_min_bound=semilog_y_min_bound,
                                    group_row_margin=group_row_margin,
                                    group_name_order=group_name_order,
                                    fig_width=fig_width, fig_height=fig_height,
                                    legend_column_count=legend_column_count,
                                    show_grid=show_grid,
                                    show_subgrid=show_subgrid,
                                    grid_alpha=grid_alpha,
                                    subgrid_alpha=subgrid_alpha,
                                    tick_direction=tick_direction,
                                    x_tick_list=x_tick_list,
                                    x_tick_label_list=x_tick_label_list,
                                    x_tick_label_angle=x_tick_label_angle,
                                    y_tick_list=y_tick_list,
                                    y_tick_label_list=y_tick_label_list,
                                    semilog_y=semilog_y,
                                    semilog_y_base=semilog_y_base,
                                    left_y_label=left_y_label,
                                    extra_plds=extra_plds,
                                    plot_title=plot_title,
                                    title_y=title_y,
                                    show_legend=show_legend,
                                    legend_position=legend_position,
                                    style_list=style_list)
    except Exception as ex:
        enb.logger.error(f"Error rendering to {output_plot_path}:\n{repr(ex)}")
        raise ex


def render_plds_by_group(pds_by_group_name, output_plot_path, column_properties,
                         global_x_label, global_y_label,
                         # General figure configuration
                         combine_groups=False, color_by_group_name=None,
                         group_name_order=None,
                         fig_width=None, fig_height=None,
                         legend_column_count=None,
                         force_monochrome_group=True,
                         # Axis configuration
                         show_grid=None, show_subgrid=None,
                         grid_alpha=0.6, subgrid_alpha=0.5,
                         semilog_y=None, semilog_y_base=10,
                         semilog_y_min_bound=1e-10,
                         group_row_margin=None,
                         # Axis limits
                         x_min=None, x_max=None,
                         horizontal_margin=None, vertical_margin=None,
                         y_min=None, y_max=None,
                         global_y_label_margin=None,
                         # Optional axis labeling
                         y_labels_by_group_name=None,
                         # Ticks
                         tick_direction="in",
                         x_tick_list=None, x_tick_label_list=None,
                         x_tick_label_angle=0,
                         y_tick_list=None, y_tick_label_list=None,
                         left_y_label=False,
                         # Additional plottable data
                         extra_plds=tuple(),
                         # Plot title
                         plot_title=None, title_y=None,
                         # Legend
                         show_legend=True,
                         legend_position=None,
                         # Matplotlib styles
                         style_list=("default",),
                         ):
    """Render lists of plotdata.PlottableData instances indexed by group
    name. Each group is rendered in a row (subplot), with a shared X axis.
    Groups can also be combined into a single row (subplot), i.e., rending
    all plottable data into that single subplot.

    When applicable, None values are substituted by default values given
    enb.config.options (guaranteed to be updated thanks to the
    @enb.parallel.parallel decorator) and the current context.

    Mandatory parameters:

    :param pds_by_group_name: dictionary of lists of PlottableData instances
    :param output_plot_path: path to the file to be created with the plot
    :param column_properties: ColumnProperties instance for the column being plotted
    :param global_x_label: x-axis label shared by all subplots (there can be
       just one subplot)
    :param global_y_label: y-axis label shared by all subplots (there can be
      just one subplot)

    General figure configuration. If None, most of these values are retrieved
    from the [enb.aanalysis.Analyzer] section of `*.ini` files.

    :param combine_groups: if False, each group is plotted in a different
      row. If True, all groups share the same subplot (and no group name is
      displayed).
    :param color_by_group_name: if not None, a dictionary of pyplot colors
      for the groups, indexed with the same keys as `pds_by_group_name`.
    :param group_name_order: if not None, it contains the order in which
      groups are displayed. If None, alphabetical, case-insensitive order is
      applied.
    :param fig_width: figure width. The larger the figure size, the smaller
      the text will look.
    :param fig_height: figure height. The larger the figure size, the smaller
      the text will look.
    :param legend_column_count: when the legend is shown, use this many columns.
    :param force_monochrome_group: if True, all plottable data with non-None
      color in each group is set to the same color, defined by color_cycle.

    Axis configuration:

    :param show_grid: if True, or if None and options.show_grid, grid is
      displayed aligned with the major axes.
    :param show_subgrid: if True, or if None and options.show_subgrid, grid is
      displayed aligned with the minor axes.
    :param grid_alpha: transparency (between 0 and 1) of the main grid, if displayed.
    :param subgrid_alpha: transparency (between 0 and 1) of the subgrid, if displayed.
    :param semilog_y: if True, a logarithmic scale is used in the Y axis.
    :param semilog_y_base: if semilog_y is True, the logarithm base employed.
    :param semilog_y_min_bound: if semilog_y is True, make y_min the maximum
      of y_min and this value.
    :param group_row_margin: if provided, this margin is applied between rows
      of groups

    Axis limits:

    :param x_min: if not None, force plots to have this value as left end.
    :param x_max: if not None, force plots to have this value as right end.
    :param horizontal_margin: Horizontal margin to be added to the figures,
      expressed as a fraction of the horizontal dynamic range.
    :param vertical_margin: Vertical margin to be added to the figures,
      expressed as a fraction of the horizontal dynamic range.
    :param y_min: if not None, force plots to have this value as bottom end.
    :param y_max: if not None, force plots to have this value as top end.
    :param global_y_label_margin: if not None, the padding to be applied between
      the global_y_label and the y axis (if such label is enabled).

    Optional axis labeling:

    :param y_labels_by_group_name: if not None, a dictionary of labels for
      the groups, indexed with the same keys as pds_by_group_name.
    :param tick_direction: direction of the ticks in the plot. Can be "in", "out" or "inout".
    :param x_tick_list: if not None, these ticks will be displayed in the x
      axis.
    :param x_tick_label_list: if not None, these labels will be displayed in
      the x axis. Only used when x_tick_list is not None.
    :param x_tick_label_angle: when label ticks are specified, they will be
      rotated to this angle
    :param y_tick_list: if not None, these ticks will be displayed in the y
      axis.
    :param y_tick_label_list: if not None, these labels will be displayed in
      the y axis. Only used when y_tick_list is not None.
    :param left_y_label: if True, the group label is shown to the left
      instead of to the right

    Additional plottable data:

    :param extra_plds: an iterable of additional PlottableData instances to
      be rendered in all subplots.

    Global title:

    :param plot_title: title to be displayed.
    :param title_y: y position of the title, when displayed. An attempt is made to
      automatically situate it without overlapping with the axes or the legend.
    :param show_legend: if True, legends are added to the plot when one or more
      PlottableData instances contain a label
    :param legend_position: position of the legend (if shown). It can be
      "title" to display it above the plot, or any matplotlib-recognized
      argument to the loc argument of legend().

    Matplotlib styles:

    :param style_list: list of valid style arguments recognized by
      `matplotlib.use`. Each element can be any of matplotlib's default styles
      or a path to a valid matplotlibrc. Styles are applied from left to right,
      overwriting definitions without warning. By default, matplotlib's
      "default" mode is applied.
    """
    # pylint: disable=too-many-arguments,too-many-locals
    with (enb.logger.debug_context(
            f"Rendering {len(pds_by_group_name)} plottable data groups "
            f"to {output_plot_path}",
            sep="...\n", msg_after=f"Done rendering into {output_plot_path}")):
        if len(pds_by_group_name) < 1:
            enb.logger.warn(
                "Warning: trying to render an empty pds_by_group_name dict. "
                f"output_plot_path={output_plot_path}, "
                f"column_properties={column_properties}. "
                f"No analysis is performed.")
            return

        # Render all gathered data with the selected configuration
        with plt.style.context([]):
            _apply_styles(style_list=style_list)

            _update_legend_count(
                legend_column_count=legend_column_count,
                pds_by_group_name=pds_by_group_name)

            sorted_group_names = _get_sorted_group_names(
                group_name_order=group_name_order,
                pds_by_group_name=pds_by_group_name)

            groupname_axis_tuples = _get_groupname_axis_tuples(
                combine_groups=combine_groups,
                fig_height=fig_height,
                fig_width=fig_width,
                sorted_group_names=sorted_group_names)

            _combine_groups(
                combine_groups=combine_groups,
                legend_position=legend_position,
                pds_by_group_name=pds_by_group_name,
                show_legend=show_legend,
                sorted_group_names=[t[0] for t in groupname_axis_tuples],
                y_labels_by_group_name=y_labels_by_group_name)

            _render_plottable_data(
                color_by_group_name=color_by_group_name,
                combine_groups=combine_groups,
                extra_plds=extra_plds,
                force_monochrome_group=force_monochrome_group,
                groupname_axis_tuples=groupname_axis_tuples,
                output_plot_path=output_plot_path,
                pds_by_group_name=pds_by_group_name)

            _update_axes(
                column_properties=column_properties,
                combine_groups=combine_groups,
                global_x_label=global_x_label,
                global_y_label=global_y_label,
                global_y_label_margin=global_y_label_margin,
                groupname_axis_tuples=groupname_axis_tuples,
                horizontal_margin=horizontal_margin,
                left_y_label=left_y_label, semilog_y=semilog_y,
                semilog_y_base=semilog_y_base, show_grid=show_grid,
                show_subgrid=show_subgrid,
                sorted_group_names=[t[0] for t in groupname_axis_tuples],
                vertical_margin=vertical_margin, x_max=x_max, x_min=x_min,
                tick_direction=tick_direction,
                x_tick_label_angle=x_tick_label_angle,
                x_tick_label_list=x_tick_label_list, x_tick_list=x_tick_list,
                y_labels_by_group_name=y_labels_by_group_name, y_max=y_max, y_min=y_min,
                y_tick_label_list=y_tick_label_list, y_tick_list=y_tick_list,
                group_row_margin=group_row_margin, pds_by_group_name=pds_by_group_name,
                semilog_y_min_bound=semilog_y_min_bound,
                grid_alpha=grid_alpha, subgrid_alpha=subgrid_alpha)

            # Draw title at the right height of the first axis so that tight_layout works well
            # and the legend does not (typically) overlap.
            if title_y is None and show_legend and legend_position == "title" and any(
                    pd.label is not None for pd in itertools.chain(*pds_by_group_name.values())):
                title_y = 1.1
            _set_title(
                plot_title=plot_title,
                axis=groupname_axis_tuples[0][1],
                title_y=title_y)

            _save_figure(output_plot_path)

            plt.close()


def _get_color_by_group_name(color_by_group_name, sorted_group_names):
    """Private to render_plds_by_group.
    Return a dictionary of colors assiged to each group.
    """
    if color_by_group_name is None:
        color_by_group_name = {}
        for i, group_name in enumerate(sorted_group_names):
            color_by_group_name[group_name] = color_cycle[
                i % len(color_cycle)]
    return color_by_group_name


def _update_legend_count(legend_column_count, pds_by_group_name):
    """Private to render_plds_by_group.
    If None, update the legend_column_count using the ini
    configuration. Update the corresponding attribute
    of the PlottableData instances.
    """
    legend_column_count = legend_column_count \
        if legend_column_count is not None \
        else enb.config.ini.get_key("enb.aanalysis.Analyzer",
                                    "legend_column_count")
    if legend_column_count:
        for pds in pds_by_group_name.values():
            for pld in pds:
                pld.legend_column_count = legend_column_count
    return legend_column_count


def _get_y_lims(column_properties,
                semilog_y,
                semilog_y_min_bound,
                y_max,
                y_min):
    """Private to render_plds_by_group.
    :return: the y_max, y_min for the plot
    """
    y_min = column_properties.hist_min if y_min is None else y_min
    y_min = max(semilog_y_min_bound, y_min if y_min is not None else 0) \
        if ((column_properties is not None
             and column_properties.semilog_y)
            or semilog_y) \
        else y_min
    y_max = column_properties.hist_max if y_max is None else y_max
    return y_min, y_max


def _get_sorted_group_names(group_name_order, pds_by_group_name):
    """Private to render_plds_by_group.
    :return: a list of the plot's group names in the order to
      be displayed.
    """
    if group_name_order is None:
        # pylint: disable=no-member
        sorted_group_names = natsort.natsorted(pds_by_group_name.keys(),
                                               alg=natsort.IGNORECASE)
        if str(sorted_group_names[0]).lower() == enb.aanalysis.Analyzer.global_group_name.lower():
            sorted_group_names = \
                sorted_group_names[1:] \
                + [str(n) for n in sorted_group_names[:1]]
    else:
        sorted_group_names = []
        for group_name in group_name_order:
            if group_name not in pds_by_group_name:
                enb.logger.warn(
                    f"Warning: {repr(group_name)} was provided in "
                    "group_name_order but is not one of the "
                    f"produced groups: "
                    f"{sorted(list(pds_by_group_name.keys()))}. "
                    f"Ignoring.")
            else:
                sorted_group_names.append(group_name)
        for group_name in pds_by_group_name.keys():
            if group_name not in sorted_group_names:
                if enb.logger.level_active(enb.logger.level_debug.name):
                    enb.logger.warn(
                        f"Warning: {repr(group_name)} was not provided in "
                        f"group_name_order but is one of the "
                        f"produced groups: "
                        f"{sorted(list(pds_by_group_name.keys()))}. "
                        f"Appending automatically.")
                sorted_group_names.append(group_name)
    return sorted_group_names


def _combine_groups(combine_groups, legend_position, pds_by_group_name,
                    show_legend, sorted_group_names, y_labels_by_group_name):
    """Private to render_plds_by_group.
    If combine_groups is True, update the PlottableData instances
    so that they can be plotted in the same axes and the legend box
    is marked when requested.
    """
    # pylint: disable=too-many-arguments
    if combine_groups:
        for i, group_name in enumerate(sorted_group_names):
            if show_legend:
                if ((i == 0 and group_name.lower() != enb.aanalysis.Analyzer.global_group_name.lower())
                        or len(sorted_group_names) > 1):
                    try:
                        pds_by_group_name[group_name][0].label = \
                            y_labels_by_group_name[group_name] \
                                if y_labels_by_group_name \
                                   and group_name in y_labels_by_group_name \
                                else group_name
                        pds_by_group_name[group_name][0].legend_position = \
                            legend_position
                    except IndexError:
                        # Ignore empty groups
                        continue
            for pld in pds_by_group_name[group_name]:
                pld.marker = marker_cycle[i]


def _apply_styles(style_list):
    """Private to render_plds_by_group.
    Apply selected styles in the given order, based on a default
    context.
    """
    for style in (style_list if style_list is not None else []):
        if not style:
            enb.logger.debug(f"Ignoring empty style ({repr(style)}")
            continue
        if style.lower() == "default":
            continue
        if style in matplotlib.style.available or os.path.isfile(style):
            # Matplotlib style name or full path
            plt.style.use(style)
        elif os.path.isfile(
                os.path.join(enb.enb_installation_dir, "config",
                             "mpl_styles", os.path.basename(style))):
            # Path relative to enb's custom mpl_styles
            plt.style.use(
                os.path.join(enb.enb_installation_dir, "config",
                             "mpl_styles", os.path.basename(style)))
        elif style == "xkcd":
            _apply_xkcd_style()
        else:
            raise ValueError(f"Unrecognized style {repr(style)}.")


def _apply_xkcd_style():
    """Apply a xkcd-like style, based on that found in matplotlib, but with
    small modifications to improve visualzation.
    """
    plt.rcParams['font.family'] = ['Humor Sans', 'Comic Sans MS']
    plt.rcParams['font.size'] = 14.0
    plt.rcParams['path.sketch'] = (1, 100, 2)
    plt.rcParams['axes.linewidth'] = 1.5
    plt.rcParams['lines.linewidth'] = 2.0
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['grid.linewidth'] = 0.0
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['xtick.major.size'] = 6
    plt.rcParams['xtick.minor.size'] = 3
    plt.rcParams['xtick.major.width'] = 2
    plt.rcParams['ytick.major.size'] = 6
    plt.rcParams['xtick.minor.size'] = 3
    plt.rcParams['ytick.major.width'] = 2


def _get_groupname_axis_tuples(combine_groups, fig_height, fig_width,
                               sorted_group_names):
    """Private to render_plds_by_group.
    Return the list of axes in the order given by sorted_group_names. The
    axes are all part of the same figure, which has the specified dimensions.
    """
    # pylint: disable=too-many-arguments
    fig_width = enb.config.ini.get_key(
        section="enb.aanalysis.Analyzer", name="fig_width") \
        if fig_width is None else fig_width
    fig_height = enb.config.ini.get_key(
        section="enb.aanalysis.Analyzer", name="fig_height") \
        if fig_height is None else fig_height
    _, axis_list = plt.subplots(
        nrows=max(len(sorted_group_names),
                  1) if not combine_groups else 1,
        ncols=1, sharex=True, sharey=combine_groups,
        figsize=(fig_width,
                 max(3, 0.5 * len(sorted_group_names))
                 if fig_height is None else fig_height))
    if combine_groups:
        axis_list = [axis_list]
    elif len(sorted_group_names) == 1:
        axis_list = [axis_list]

    if combine_groups:
        assert len(axis_list) == 1
        groupname_axis_tuples = list(zip(
            sorted_group_names,
            axis_list * len(sorted_group_names)))
    else:
        groupname_axis_tuples = list(zip(
            sorted_group_names, axis_list))

    return groupname_axis_tuples


def _set_title(plot_title, axis, title_y=1):
    """Private to render_plds_by_group.

    Set the plot's title.

    :param axis: axis whose title is set.
    :param title_y: y position of the title.
    """
    plot_title = plot_title if plot_title is not None \
        else enb.config.ini.get_key("enb.aanalysis.Analyzer", "plot_title")
    if plot_title:
        axis.set_title(plot_title, y=title_y)


def _get_global_extrema(column_properties, pds_by_group_name):
    """Private to render_plds_by_group.
    Get the x and y extrema of the PlottableData2D instances in all groups.
    For numerical data, align to integer extrema if the maximum is above 1.
    """
    try:
        global_x_min = float("inf")
        global_x_max = float("-inf")
        global_y_min = float("inf")
        global_y_max = float("-inf")

        for pld in (plottable for pds in pds_by_group_name.values() for
                    plottable in pds):
            if not isinstance(pld, enb.plotdata.PlottableData2D):
                continue
            x_values = np.array(pld.x_values, copy=False)
            if len(x_values) > 0:
                x_values = x_values[~np.isnan(x_values)]
            global_x_min = min(global_x_min, x_values.min() if len(
                x_values) > 0 else global_x_min)
            global_x_max = max(global_x_min, x_values.max() if len(
                x_values) > 0 else global_x_min)
            y_values = np.array(pld.y_values, copy=False)
            if len(y_values) > 0:
                y_values = y_values[~np.isnan(y_values)]
            global_y_min = min(global_y_min, y_values.min() if len(
                y_values) > 0 else global_y_min)
            global_y_max = max(global_y_min, y_values.max() if len(
                y_values) > 0 else global_y_min)

        if global_x_max - global_x_min > 1:
            global_x_min = math.floor(global_x_min) if not math.isinf(
                global_x_min) else global_x_min
            global_x_max = math.ceil(global_x_max) if not math.isinf(
                global_x_max) else global_x_max

        if global_y_max - global_y_min > 1:
            global_y_min = math.floor(global_y_min) if not math.isinf(
                global_y_min) else global_y_min
            global_y_max = math.ceil(global_y_max) if not math.isinf(
                global_y_max) else global_y_max

        if column_properties:
            global_x_min = column_properties.plot_min \
                if column_properties.plot_min is not None else global_x_min
            global_x_max = column_properties.plot_max \
                if column_properties.plot_max is not None else global_x_max

        return global_x_max, global_x_min, global_y_max, global_y_min

    except TypeError:
        # Likely not numerical data - apply the min and max methods directly
        all_pds = tuple(itertools.chain(*itertools.chain(pds_by_group_name.values())))
        all_x_values = tuple(itertools.chain(pd.x_values for pd in all_pds))
        all_y_values = tuple(itertools.chain(pd.y_values for pd in all_pds))
        return max(all_x_values), min(all_x_values), max(all_y_values), min(all_y_values)


def _render_plottable_data(color_by_group_name, combine_groups, extra_plds,
                           force_monochrome_group, groupname_axis_tuples,
                           output_plot_path, pds_by_group_name):
    """Private to render_plds_by_group.
    Call the render method of all plottable data and extra_plds.
    """
    # pylint: disable=too-many-arguments
    color_by_group_name = _get_color_by_group_name(
        color_by_group_name,
        [t[0] for t in groupname_axis_tuples])

    for i, (group_name, group_axes) in enumerate(groupname_axis_tuples):
        group_color = color_by_group_name[group_name]
        for pld in pds_by_group_name[group_name]:
            pld.x_label = None
            pld.y_label = None
            extra_kwargs = {}
            if force_monochrome_group:
                pld.color = group_color if pld.color is None else pld.color
            extra_kwargs.update(color=pld.color)
            try:
                pld.extra_kwargs.update(extra_kwargs)
            except AttributeError:
                pld.extra_kwargs = extra_kwargs
            try:
                pld.render(axes=group_axes)
            except Exception as ex:
                raise Exception(
                    f"Error rendering {pld} -- {group_name} "
                    f"-- {output_plot_path}:\n{repr(ex)}") from ex
        if not combine_groups or i == 0:
            for pld in extra_plds:
                pld.render(axes=group_axes)


def _update_axes(column_properties, combine_groups, global_x_label,
                 global_y_label, global_y_label_margin, groupname_axis_tuples, horizontal_margin,
                 left_y_label, semilog_y, semilog_y_base, show_grid,
                 show_subgrid, sorted_group_names, vertical_margin, x_max, x_min,
                 tick_direction, x_tick_label_angle, x_tick_label_list, x_tick_list,
                 y_labels_by_group_name, y_max, y_min, y_tick_label_list,
                 y_tick_list, group_row_margin, pds_by_group_name,
                 semilog_y_min_bound,
                 grid_alpha, subgrid_alpha):
    """Private to render_plds_by_group.
    Update everything about the axes after rendering all PlottableData
    instances.
    """
    # pylint: disable=too-many-arguments,too-many-locals
    y_min, y_max = _get_y_lims(
        column_properties=column_properties,
        semilog_y=semilog_y,
        semilog_y_min_bound=semilog_y_min_bound,
        y_max=y_max,
        y_min=y_min)

    global_x_max, global_x_min, global_y_max, global_y_min = _get_global_extrema(
        column_properties=column_properties,
        pds_by_group_name=pds_by_group_name)

    show_grid = show_grid if show_grid is not None \
        else enb.config.ini.get_key("enb.aanalysis.Analyzer", "show_grid")
    show_subgrid = show_subgrid if show_subgrid is not None \
        else enb.config.ini.get_key("enb.aanalysis.Analyzer", "show_subgrid")

    y_labels_by_group_name = {g: g for g in sorted_group_names} \
        if y_labels_by_group_name is None else y_labels_by_group_name

    semilog_y = _update_ticks_and_grid(
        column_properties=column_properties,
        combine_groups=combine_groups,
        global_x_max=global_x_max,
        groupname_axis_tuples=groupname_axis_tuples,
        left_y_label=left_y_label,
        semilog_y=semilog_y,
        semilog_y_base=semilog_y_base,
        show_grid=show_grid,
        show_subgrid=show_subgrid,
        sorted_group_names=sorted_group_names,
        tick_direction=tick_direction,
        x_tick_label_angle=x_tick_label_angle,
        x_tick_label_list=x_tick_label_list,
        x_tick_list=x_tick_list,
        y_labels_by_group_name=y_labels_by_group_name,
        y_max=y_max,
        y_min=y_min,
        y_tick_label_list=y_tick_label_list,
        y_tick_list=y_tick_list,
        grid_alpha=grid_alpha,
        subgrid_alpha=subgrid_alpha)

    _update_axis_limits(
        global_x_max=global_x_max,
        global_x_min=global_x_min,
        global_y_max=global_y_max,
        global_y_min=global_y_min,
        groupname_axis_tuples=groupname_axis_tuples,
        horizontal_margin=horizontal_margin,
        semilog_y=semilog_y,
        vertical_margin=vertical_margin,
        x_max=x_max,
        x_min=x_min,
        y_max=y_max,
        y_min=y_min)

    _update_axis_labels(
        global_x_label=global_x_label,
        global_y_label=global_y_label,
        groupname_axis_tuples=groupname_axis_tuples,
        global_y_label_margin=global_y_label_margin)

    _adjust_subplot_position(
        group_row_margin=group_row_margin,
        pds_by_group_name=pds_by_group_name)


def _update_ticks_and_grid(column_properties, combine_groups, global_x_max,
                           groupname_axis_tuples, left_y_label, semilog_y,
                           semilog_y_base, show_grid, show_subgrid,
                           sorted_group_names,
                           tick_direction,
                           x_tick_label_angle, x_tick_label_list, x_tick_list,
                           y_labels_by_group_name, y_max, y_min,
                           y_tick_label_list, y_tick_list,
                           grid_alpha, subgrid_alpha):
    """Private to render_plds_by_group.
    Set the ticks, grid and subgrid of the plot.
    """
    # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
    for (group_name, group_axes) in groupname_axis_tuples:
        if y_min != y_max:
            group_axes.set_ylim(
                y_min if y_min is not None and not math.isinf(y_min)
                else None,
                y_max if y_max is not None and not math.isinf(y_max)
                else None)

        semilog_y = semilog_y or (
            column_properties.semilog_y
            if column_properties else False)

        if semilog_y:
            base_y = column_properties.semilog_y_base \
                if column_properties is not None else semilog_y_base
            group_axes.semilogy(base=base_y)
            if combine_groups or len(sorted_group_names) <= 2:
                numticks = 11
            elif len(sorted_group_names) <= 5 \
                    and not column_properties.semilog_y:
                numticks = 6
            elif len(sorted_group_names) <= 10:
                numticks = 4
            else:
                numticks = 3
            group_axes.get_yaxis().set_major_locator(
                matplotlib.ticker.LogLocator(
                    base=base_y, numticks=numticks))
            group_axes.grid(True, "major", axis="y", alpha=0.2)
        else:
            group_axes.get_yaxis().set_major_locator(
                matplotlib.ticker.MaxNLocator(nbins="auto",
                                              integer=False))
            group_axes.get_yaxis().set_minor_locator(
                matplotlib.ticker.AutoMinorLocator())
        if not combine_groups:
            if not left_y_label:
                group_axes.get_yaxis().set_label_position("right")
            group_axes.set_ylabel(
                y_labels_by_group_name[group_name]
                if group_name in y_labels_by_group_name
                else enb.atable.clean_column_name(group_name),
                rotation=0 if not left_y_label else 90,
                ha="left" if not left_y_label else "center",
                va="center" if not left_y_label else "bottom")

        if column_properties \
                and column_properties.hist_label_dict is not None:
            x_tick_values = sorted(column_properties.hist_label_dict.keys())
            x_tick_label_list = [column_properties.hist_label_dict[x] for x
                                 in x_tick_values]

        plt.sca(group_axes)
        plt.xticks(x_tick_list, x_tick_label_list,
                   rotation=x_tick_label_angle)
        plt.yticks(y_tick_list, y_tick_label_list)
        if x_tick_label_list is None and y_tick_label_list is None:
            plt.minorticks_on()
            subgrid_axis = "both"
        elif x_tick_label_list is None:
            plt.minorticks_on()
            plt.tick_params(which="minor", left=False)
            subgrid_axis = "x"
        elif y_tick_label_list is None:
            plt.minorticks_on()
            plt.tick_params(which="minor", bottom=False)
            subgrid_axis = "y"

        plt.tick_params(which="both", direction=tick_direction)

        try:
            if global_x_max < 1e-2:
                x_tick_label_angle = 90 if x_tick_label_angle is not None else x_tick_label_angle
        except TypeError:
            # Likely not numerical data - skip adjustments
            pass
        if show_grid:
            plt.grid(which="major", axis="both", alpha=grid_alpha)
        if show_subgrid:
            plt.grid(which="minor", axis=subgrid_axis, alpha=subgrid_alpha)

    return semilog_y


def _update_axis_limits(global_x_max, global_x_min, global_y_max, global_y_min,
                        groupname_axis_tuples, horizontal_margin, semilog_y,
                        vertical_margin, x_max, x_min, y_max, y_min):
    """Private to render_plds_by_group.
    Adjust the plot limits.
    """
    # pylint: disable=too-many-arguments,too-many-locals

    try:
        # Set the axis limits
        xlim = [global_x_min, global_x_max]
        ylim = [global_y_min, global_y_max]
        xlim[0] = xlim[0] if x_min is None else x_min
        xlim[1] = xlim[1] if x_max is None else x_max
        ylim[0] = ylim[0] if y_min is None else y_min
        ylim[1] = ylim[1] if y_max is None else y_max
        # Translate relative margin to absolute margin
        horizontal_margin = horizontal_margin \
            if horizontal_margin is not None \
            else enb.config.ini.get_key("enb.aanalysis.Analyzer", "horizontal_margin")
        vertical_margin = vertical_margin \
            if vertical_margin is not None \
            else enb.config.ini.get_key("enb.aanalysis.Analyzer", "vertical_margin")
        h_margin = horizontal_margin * (xlim[1] - xlim[0])
        v_margin = vertical_margin * (ylim[1] - ylim[0])
        xlim = [xlim[0] - h_margin, xlim[1] + h_margin]
        ylim = [ylim[0] - v_margin, ylim[1] + v_margin]
        # Apply changes to the figure
        if xlim[0] != xlim[1] and not math.isnan(
                xlim[0]) and not math.isnan(xlim[1]):
            plt.xlim(*xlim)
            current_axis = plt.gca()
            for group_axes in [t[1] for t in groupname_axis_tuples]:
                plt.sca(group_axes)
                plt.xlim(*xlim)
            plt.sca(current_axis)
        # pylint: disable=too-many-boolean-expressions
        if ylim[0] != ylim[1] \
                and not math.isnan(ylim[0]) \
                and not math.isnan(ylim[1]) \
                and (not semilog_y or (ylim[0] > 0 and ylim[1] > 0)):
            plt.ylim(*ylim)
            current_axis = plt.gca()
            for group_axes in [t[1] for t in groupname_axis_tuples]:
                plt.sca(group_axes)
                plt.ylim(*ylim)
            plt.sca(current_axis)
    except TypeError:
        # Likely not numerical data
        pass


def _update_axis_labels(global_x_label, global_y_label, groupname_axis_tuples, global_y_label_margin):
    """Private to render_plds_by_group.
    Update the axes labels.
    """
    if global_x_label or global_y_label:
        # The x axis needs to be placed on the last horizontal group
        # so that it can be correctly aligned
        current_axis = plt.gca()
        for group_axes in [t[1] for t in groupname_axis_tuples][-1:]:
            plt.sca(group_axes)
            plt.xlabel(global_x_label)
        plt.sca(current_axis)

        # Add an otherwise transparent subplot for global labels
        if global_y_label is not None:
            plt.gcf().add_subplot(111, frame_on=False)
            plt.tick_params(labelcolor="none", bottom=False, left=False)
            plt.grid(False)
            plt.minorticks_off()
            plt.ylabel(global_y_label, labelpad=global_y_label_margin)


def _adjust_subplot_position(group_row_margin, pds_by_group_name):
    """Private to render_plds_by_group.
    Adjust the subplot row separation (when multiple groups are shown).
    """
    group_row_margin = group_row_margin \
        if group_row_margin is not None \
        else enb.config.ini.get_key("enb.aanalysis.Analyzer",
                                    "group_row_margin")
    group_row_margin = float(group_row_margin) \
        if group_row_margin is not None else group_row_margin
    if group_row_margin is None and len(pds_by_group_name) > 5:
        if len(pds_by_group_name) <= 7:
            group_row_margin = 0.5
        elif len(pds_by_group_name) <= 12:
            group_row_margin = 0.6
        else:
            group_row_margin = 0.7
        enb.logger.debug(
            "The `group_row_margin` option was likely too small to display all "
            f"{len(pds_by_group_name)} groups: automatically adjusting to {group_row_margin}. "
            "You can set  your desired value at the [enb.aanalysis.Analyzer] "
            "section in your *.ini files, or passing e.g., `group_row_margin=0.9` "
            "to your Analyzer get_df() or adjusting the figure height with `fig_height`.")
    if group_row_margin is not None:
        plt.subplots_adjust(hspace=group_row_margin)


def _save_figure(output_plot_path):
    """Private to render_plds_by_group.
    Save the final figure into PDF and PNG formats.
    """
    if os.path.dirname(output_plot_path):
        os.makedirs(os.path.dirname(output_plot_path), exist_ok=True)
    if os.path.dirname(output_plot_path):
        os.makedirs(os.path.dirname(output_plot_path),
                    exist_ok=True)
    plt.savefig(output_plot_path, bbox_inches="tight")
    if output_plot_path.endswith(".pdf"):
        plt.savefig(output_plot_path[:-3] + "png",
                    bbox_inches="tight", dpi=300, transparent=True)
    enb.logger.debug(f"Saved plot to {output_plot_path}")
