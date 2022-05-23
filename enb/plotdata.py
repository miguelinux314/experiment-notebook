#!/usr/bin/env python3
"""Utils to plot data (thinking about pyplot)
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/09/10"

import os
import math
import itertools
import glob
import matplotlib
import matplotlib.patheffects
import matplotlib.patches
import natsort

import enb.atable

matplotlib.use("Agg")

import matplotlib.ticker
import numpy as np
import collections
from scipy.stats import norm
from matplotlib import pyplot as plt

import enb
from enb.config import options
from enb.misc import CircularList

marker_cycle = CircularList(["o", "X", "s", "*", "p", "P", "d", "H", "d", "<", ">", "+"])
color_cycle = CircularList([f"C{i}" for i in [0, 1, 2, 3, 6, 7, 9, 8, 5, 10]])
pattern_cycle = CircularList(["//", "\\\\", "OO", "**"])


class PlottableData:
    alpha = 0.75
    legend_column_count = 1
    color = None
    marker = None
    # If "title", it is shown outside the plot, above it and centered.
    # Otherwise, it must be a matplotlib-recognized string
    legend_position = "title"

    def __init__(self, data=None, axis_labels=None, label=None,
                 extra_kwargs=None, alpha=None, legend_column_count=None,
                 legend_position=None,
                 marker=None, color=None,
                 marker_size=None):
        self.data = data
        self.axis_labels = axis_labels
        self.label = label
        self.extra_kwargs = extra_kwargs if extra_kwargs is not None else {}
        self.alpha = alpha if alpha is not None else self.alpha
        self.legend_column_count = legend_column_count if legend_column_count is not None else self.legend_column_count
        self.legend_position = legend_position if legend_position is not None else self.legend_position
        self.marker = marker
        self.marker_size = marker_size
        self.color = color if color is not None else self.color

    def render(self, axes=None):
        """Render data in current figure.

        :param axes: if not None, those axes are used for plotting instead of plt
        """
        raise NotImplementedError()

    def render_axis_labels(self, axes=None):
        """Add axis labels in current figure - don't show or write the result

        :param axes: if not None, those axes are used for plotting instead of plt
        """
        raise NotImplementedError()

    def render_legend(self, axes=None):
        axes = plt if axes is None else axes
        if self.legend_position == "title":
            legend = axes.legend(loc="lower center", bbox_to_anchor=(0.5, 1),
                                 ncol=self.legend_column_count, edgecolor=(0, 0, 0, 0.2))
            facecolor = (1, 1, 1, 0)
        else:
            legend = axes.legend(loc=self.legend_position if self.legend_position is not None else "best",
                                 ncol=self.legend_column_count, edgecolor=(0, 0, 0, 0.2))
            facecolor = (1, 1, 1, 1)

        legend.get_frame().set_alpha(None)
        legend.get_frame().set_facecolor(facecolor)

    def __repr__(self):
        return f"{self.__class__.__name__}(color={repr(self.color)})"


class PlottableData2D(PlottableData):
    """Plot 2D data using plt.plot()
    """

    def __init__(self, x_values, y_values,
                 x_label=None, y_label=None,
                 label=None, extra_kwargs=None,
                 remove_duplicates=False,
                 alpha=None, legend_column_count=None,
                 marker=None,
                 marker_size=None):
        """
        :param x_values, y_values: values to be plotted (only a reference is kept)
        :param x_label, y_label: axis labels
        :param label: line legend label
        :param extra_kwargs: extra arguments to be passed to plt.plot
        """
        assert len(x_values) == len(y_values)
        if remove_duplicates:
            found_pairs = collections.OrderedDict()
            for x, y in zip(x_values, y_values):
                found_pairs[(x, y)] = (x, y)
            if found_pairs:
                x_values, y_values = zip(*found_pairs.values())
            else:
                x_values = []
                y_values = []

        super().__init__(data=(x_values, y_values), axis_labels=(x_label, y_label),
                         label=label, extra_kwargs=extra_kwargs, alpha=alpha,
                         legend_column_count=legend_column_count, marker_size=marker_size,
                         marker=marker)
        self.x_values = x_values
        self.y_values = y_values
        self.x_label = x_label
        self.y_label = y_label

    def render_axis_labels(self, axes=None):
        """Show the labels in label list (if not None) or in self.axis_label_list
        (if label_list None) in the current figure.

        :param axes: if not None, those axes are used for plotting instead of plt
        """
        axes = plt if axes is None else axes
        if self.x_label is not None:
            axes.set_xlabel(self.x_label)
        if self.y_label is not None:
            axes.set_ylabel(self.y_label)

    def diff(self, other, ylabel_suffix="_difference"):
        assert len(self.x_values) == len(other.x_values)
        assert len(self.y_values) == len(other.y_values)
        assert all(s == o for s, o in zip(self.x_values, other.x_values))
        return PlottableData2D(x_values=self.x_values,
                               y_values=[s - o for s, o in zip(self.y_values, other.y_values)],
                               x_label=self.x_label,
                               y_label=f"{self.y_label}{ylabel_suffix}",
                               legend_column_count=self.legend_column_count)

    def shift_y(self, constant):
        self.y_values = [y + constant for y in self.y_values]

    def shift_x(self, constant):
        self.y_values = [y + constant for y in self.y_values]


class LineData(PlottableData2D):
    def __init__(self, marker="o", marker_size=5, line_width=1.5, **kwargs):
        super().__init__(marker=marker, marker_size=marker_size, **kwargs)
        self.line_width = line_width

    def render(self, axes=None):
        """Plot 2D data using plt.plot()

        :param axes: if not None, those axes are used for plotting instead of plt
        """
        try:
            original_kwargs = self.extra_kwargs
            extra_kwargs = dict(self.extra_kwargs)

            try:
                ms = extra_kwargs["ms"]
                del extra_kwargs["ms"]
            except KeyError:
                ms = self.marker_size

            axes.plot(self.x_values, self.y_values, label=self.label, alpha=self.alpha,
                      marker=self.marker, ms=ms, linewidth=self.line_width,
                      **extra_kwargs)
            axes = plt if axes is None else axes
            self.render_axis_labels(axes=axes)
            if self.label is not None and self.legend_column_count != 0:
                self.render_legend(axes=axes)
        finally:
            self.extra_kwargs = original_kwargs


class ScatterData(PlottableData2D):
    def __init__(self, marker="o", alpha=0.5, marker_size=3, **kwargs):
        super().__init__(marker=marker, alpha=alpha, marker_size=marker_size, **kwargs)

    def render(self, axes=None):
        axes = plt if axes is None else axes
        self.extra_kwargs["s"] = self.marker_size

        axes.scatter(self.x_values, self.y_values, label=self.label, alpha=self.alpha,
                     marker=self.marker,
                     **self.extra_kwargs)
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            self.render_legend(axes=axes)


class BarData(PlottableData2D):
    pattern = None
    vertical = True

    def __init__(self, pattern=None, vertical=True, **kwargs):
        super().__init__(**kwargs)
        self.pattern = pattern
        self.vertical = vertical

    def render(self, axes=None):
        axes = plt if axes is None else axes
        plot_fun = axes.bar if self.vertical is True else axes.barh
        plot_fun(self.x_values, self.y_values, label=self.label,
                 alpha=self.alpha if not self.pattern else self.alpha * 0.75,
                 hatch=self.pattern,
                 edgecolor=matplotlib.colors.colorConverter.to_rgba(self.color, 0.9) if self.color else None,
                 **self.extra_kwargs)
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            self.render_legend(axes=axes)

    def shift_y(self, constant):
        coordinate = "bottom" if self.vertical else "left"
        try:
            self.extra_kwargs[coordinate] += constant
        except KeyError:
            self.extra_kwargs[coordinate] = constant
        except AttributeError:
            self.extra_kwargs = {coordinate: constant}


class StepData(PlottableData2D):
    where = "post"

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.step(self.x_values, self.y_values, label=self.label, alpha=self.alpha,
                  where=self.where, **self.extra_kwargs)
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            self.render_legend(axes=axes)


class ErrorLines(PlottableData2D):
    """One or more error lines    
    """

    def __init__(self, x_values, y_values, err_neg_values, err_pos_values, vertical=False,
                 alpha=0.5, color=None,
                 marker_size=1, cap_size=2,
                 line_width=1, **kwargs):
        """
        :param x_values, y_values: centers of the error lines
        :param err_neg_values: list of lengths for the negative part of the error
        :param err_pos_values: list of lengths for the positive part of the error
        :param vertical: determines whether the error bars are vertical or horizontal
        """
        super().__init__(x_values=x_values, y_values=y_values, remove_duplicates=False,
                         alpha=alpha, marker_size=marker_size, **kwargs)
        self.err_neg = [v if not np.isnan(v) else 0 for v in err_neg_values]
        self.err_pos = [v if not np.isnan(v) else 0 for v in err_pos_values]
        self.cap_size = cap_size if cap_size is not None else self.cap_size
        self.line_width = line_width if line_width is not None else self.line_width
        self.vertical = vertical
        self.color = color
        self.alpha = alpha
        assert len(self.x_values) == len(self.y_values)
        assert len(self.x_values) == len(self.err_pos), (
            len(self.x_values), len(self.err_pos), self.x_values, self.err_pos)

    def render(self, axes=None):
        axes = plt if axes is None else axes
        err_argument = np.concatenate((
            np.array(self.err_neg).reshape(1, len(self.err_neg)),
            np.array(self.err_pos).reshape(1, len(self.err_pos))),
            axis=0)
        # When std is computed for constant data, nan is returned. Replace those with 0 to avoid warnings.
        err_argument = err_argument[:, :len(self.x_values)]

        try:
            if self.vertical:
                axes.errorbar(self.x_values, self.y_values, yerr=err_argument,
                              fmt="-o", capsize=self.cap_size, capthick=0.5, lw=0, elinewidth=self.line_width,
                              ms=self.marker_size,
                              alpha=self.alpha,
                              **self.extra_kwargs)
            else:
                axes.errorbar(self.x_values, self.y_values, xerr=err_argument,
                              fmt="-o", capsize=self.cap_size, capthick=0.5, lw=0, elinewidth=self.line_width,
                              ms=self.marker_size,
                              alpha=self.alpha,
                              **self.extra_kwargs)
        except UserWarning as ex:
            raise ValueError(f"Error rendering {self}. x_values={repr(self.x_values)}, "
                             f"y_values={repr(self.y_values)}, self.extra_kwargs={self.extra_kwargs} "
                             f"self.err_neg={self.err_neg}, "
                             f"self.err_pos={self.err_pos},") from ex

        assert len(self.x_values) == len(self.y_values)


class Rectangle(PlottableData2D):
    """Render a rectangle (line only) in a given position.
    """
    alpha = 0.5

    def __init__(self, x_values, y_values, width, height, angle_degrees=0, fill=False,
                 line_width=1, **kwargs):
        """
        :param x_values: a list with a single element with the x position of the rectangle's center
        :param y_values: a list with a single element with the y position of the rectangle's center
        :param width: width of the rectangle
        :param height: height of the rectangle
        """
        super().__init__(x_values=x_values, y_values=y_values, **kwargs)
        assert width >= 0, width
        assert height >= 0, height
        assert line_width >= 0, line_width
        self.width = width
        self.height = height
        self.angle_degrees = angle_degrees
        self.fill = fill
        self.line_width = line_width

    def render(self, axes=None):
        assert len(self.x_values) == 1, self.x_values
        assert len(self.y_values) == 1, self.y_values
        axes = plt if axes is None else axes
        axes.add_patch(matplotlib.patches.Rectangle((
            self.x_values[0] - self.width / 2,
            self.y_values[0] - self.height / 2),
            width=self.width, height=self.height,
            angle=self.angle_degrees, fill=self.fill,
            color=self.color, alpha=self.alpha,
            linewidth=self.line_width))


class LineSegment(PlottableData2D):
    """Render a line segment centered at a given position.
    """
    alpha = 0.5

    def __init__(self, x_values, y_values, length, vertical=True, line_width=1, **kwargs):
        """
        :param x_values: a list with a single element with the x position of the rectangle's center
        :param y_values: a list with a single element with the y position of the rectangle's center
        :param length: length of the line
        """
        super().__init__(x_values=x_values, y_values=y_values, **kwargs)
        assert length >= 0, length
        assert line_width >= 0, line_width
        self.length = length
        self.line_width = line_width
        self.vertical = vertical

    @property
    def center(self):
        return self.x_values[0], self.y_values[0]

    def render(self, axes=None):
        assert len(self.x_values) == 1, self.x_values
        assert len(self.y_values) == 1, self.y_values
        axes = plt if axes is None else axes
        center = self.center
        if self.vertical:
            x = [center[0], center[0]]
            y = [center[1] - self.length / 2, center[1] + self.length / 2]
        else:
            x = [center[0] - self.length / 2, center[0] + self.length / 2]
            y = [center[1], center[1]]

        axes.plot(x, y, color=self.color, alpha=self.alpha, linewidth=self.line_width)


class HorizontalBand(PlottableData2D):
    """Plottable element that """
    alpha = 0.5
    degradation_band_count = 25
    show_bounding_lines = False

    def __init__(self, x_values, y_values, pos_height_values, neg_height_values,
                 show_bounding_lines=None,
                 degradation_band_count=None,
                 std_band_add_xmargin=False,
                 **kwargs):
        super().__init__(x_values=x_values, y_values=y_values, extra_kwargs=kwargs)
        self.extra_kwargs["lw"] = 0
        self.pos_height_values = np.array(pos_height_values)
        self.neg_height_values = np.array(neg_height_values)
        self.show_bounding_lines = show_bounding_lines if show_bounding_lines is not None else self.show_bounding_lines
        self.degradation_band_count = degradation_band_count if degradation_band_count is not None \
            else self.degradation_band_count
        self.std_band_add_xmargin = std_band_add_xmargin

    def render(self, axes=None):
        for i in range(self.degradation_band_count):
            band_fraction = i / self.degradation_band_count
            next_band_fraction = (i + 1) / self.degradation_band_count
            band_probability = 1 - (norm.cdf(band_fraction) - norm.cdf(-band_fraction))

            band_x_values = np.array(self.x_values)
            band_y_values = np.array(self.y_values)
            pos_height_values = np.array(self.pos_height_values)
            neg_height_values = np.array(self.neg_height_values)
            if self.std_band_add_xmargin:
                new_x_values = []
                new_y_values = []
                new_pos_heights = []
                new_neg_heights = []
                for x, y, pos_height, neg_height in zip(band_x_values, band_y_values, pos_height_values,
                                                        neg_height_values):
                    new_x_values.extend([x - 0.5, x + 0.5])
                    new_y_values.extend([y, y])
                    new_pos_heights.extend([pos_height, pos_height])
                    new_neg_heights.extend([neg_height, neg_height])
                band_x_values = np.array(new_x_values)
                band_y_values = np.array(new_y_values)
                pos_height_values = np.array(new_pos_heights)
                neg_height_values = np.array(new_neg_heights)

            # Fill top
            axes.fill_between(
                band_x_values,
                band_y_values + pos_height_values * band_fraction,
                band_y_values + pos_height_values * next_band_fraction,
                alpha=self.alpha * band_probability,
                color=self.color, edgecolor=None, facecolor=self.color, lw=0)
            # Fill bottom
            axes.fill_between(
                band_x_values,
                band_y_values - neg_height_values * next_band_fraction,
                band_y_values - neg_height_values * band_fraction,
                alpha=self.alpha * band_probability,
                color=self.color, edgecolor=None, facecolor=self.color, lw=0)

        if self.show_bounding_lines:
            axes.plot(self.x_values, self.y_values + pos_height_values,
                      linewidth=0.5, alpha=0.68 * self.alpha, color=self.color)
            axes.plot(self.x_values, self.y_values - neg_height_values,
                      linewidth=0.5, alpha=0.68 * self.alpha, color=self.color)

        axes = plt if axes is None else axes
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            plt.legend(loc="lower center", bbox_to_anchor=(0.5, 1),
                       ncol=self.legend_column_count, facecolor=(1, 1, 1, 0))


class HorizontalLine(PlottableData):
    """Draw a horizontal line across the whole subplot.
    """

    def __init__(self, y_position, line_width=1, line_style='-', **kwargs):
        super().__init__(**kwargs)
        self.y_position = y_position
        self.line_width = line_width
        self.line_style = line_style

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.axhline(y=self.y_position, color=self.color, linestyle=self.line_style,
                     lw=self.line_width, alpha=self.alpha)


class VerticalLine(PlottableData):
    """Draw a horizontal line across the whole subplot.
    """

    def __init__(self, x_position, line_width=1, line_style='-', **kwargs):
        super().__init__(**kwargs)
        self.x_position = x_position
        self.line_width = line_width
        self.line_style = line_style

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.axvline(x=self.x_position, color=self.color, linestyle=self.line_style,
                     lw=self.line_width, alpha=self.alpha)


class Histogram2D(PlottableData2D):
    """Represent the result of a 2D histogram.
    """
    # See https://matplotlib.org/stable/gallery/color/colormap_reference.html
    color_map = "Reds"
    interpolation = "none"
    origin = "lower"
    alpha = 1
    aspect = "equal"
    vmin = None
    vmax = None
    show_cmap_bar = True
    no_data_color = (1, 1, 1, 0)
    bad_data_color = "magenta"

    def __init__(self, x_edges, y_edges, matrix_values, color_map=None, colormap_label=None, vmin=None, vmax=None,
                 no_data_color=(1, 1, 1, 0), bad_data_color="magenta",
                 **kwargs):
        """
        :param x_edges: the edges of the histogram along the x axis.
        :param y_edges: the edges of the histogram along the y axis.
        :param matrix_values: values of the histogram (2d array of dimensions
          given by the length of x_edges and y_edges).
        :param no_data_color: color shown when no counts are found in a bin
        :param bad_data_color: color shown when nan is found in a bin
        :param vmin: minimum value considered in the histogram
        :param vmax: minimum value considered in the histogram
        :param kwargs: additional parameters passed to the parent class initializer
        """
        super().__init__(x_values=tuple(x - 0.5 for x in range(len(x_edges))),
                         y_values=tuple(y - 0.5 for y in range(len(y_edges))),
                         **kwargs)
        self.x_edges = x_edges
        self.y_edges = y_edges
        self.matrix_values = matrix_values
        self.colormap_label = colormap_label
        self.vmin = vmin
        self.vmax = vmax
        self.color_map = color_map if color_map is not None else self.color_map
        self.bad_data_color = bad_data_color
        self.no_data_color = no_data_color

    def render(self, axes=None):
        axes = plt if axes is None else axes

        cmap = matplotlib.cm.get_cmap(self.color_map).copy()
        cmap.set_under(color=self.no_data_color)
        cmap.set_over(color=self.bad_data_color)
        cmap.set_bad(color=self.bad_data_color)

        x = axes.imshow(self.matrix_values, cmap=cmap,
                        origin=self.origin, interpolation=self.interpolation,
                        alpha=self.alpha, aspect=self.aspect,
                        vmin=self.vmin, vmax=self.vmax)
        if self.show_cmap_bar:
            plt.colorbar(x, label=self.colormap_label,
                         ticks=list(np.linspace(self.vmin, self.vmax, 5))
                         if self.vmin is not None and self.vmax is not None else None,
                         fraction=0.1, ax=axes)
        if self.y_label:
            axes.set_ylabel(self.y_label)


def get_available_styles():
    """Get a list of all styles available for plotting.
    It includes installed matplotlib styles plus custom styles 
    """
    return sorted(itertools.chain(get_matlab_styles(), get_local_styles(), ["default"]))


def get_matlab_styles():
    """Return the list of installed matlab styles.
    """
    return sorted([str(s) for s in matplotlib.style.available if s[0] != "_"] + ["xkcd"])


def get_local_styles():
    """Get the list of basenames of all styles in the enb/config/mpl_styles folder.
    """
    return sorted(os.path.basename(p)
                  for p in glob.glob(os.path.join(enb.enb_installation_dir, "config", "mpl_styles", "*"))
                  if os.path.isfile(p) and os.path.basename(p) != "README.md")


def apply_xkcd_style():
    """Apply a xkcd-like style, based on that found in matplotlib, but 
    with small modifications to improve visualzation.
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


@enb.parallel.parallel()
def parallel_render_plds_by_group(
        pds_by_group_name, output_plot_path, column_properties,
        global_x_label, global_y_label,
        # General figure configuration
        combine_groups=False, color_by_group_name=None, group_name_order=None,
        fig_width=None, fig_height=None,
        global_y_label_pos=None, legend_column_count=None,
        force_monochrome_group=True,
        # Axis configuration
        show_grid=None, show_subgrid=None,
        semilog_y=None, semilog_y_base=10, semilog_y_min_bound=1e-10,
        group_row_margin=None,
        # Axis limits
        x_min=None, x_max=None, y_min=None, y_max=None,
        horizontal_margin=None, vertical_margin=None,
        # Optional axis labeling
        y_labels_by_group_name=None,
        x_tick_list=None, x_tick_label_list=None, x_tick_label_angle=0,
        y_tick_list=None, y_tick_label_list=None,
        left_y_label=False,
        # Additional plottable data instances
        extra_plds=tuple(),
        # Plot title
        plot_title=None, show_legend=True, legend_position=None,
        # Matplotlib styles
        style_list=tuple()):
    """Ray wrapper for render_plds_by_group. See that method for parameter information.
    """
    try:
        if enb.parallel_ray.is_remote_node():
            os.chdir(os.path.expanduser(enb.parallel_ray.RemoteNode.remote_project_mount_path))
        else:
            os.chdir(options.project_root)

        return render_plds_by_group(pds_by_group_name=pds_by_group_name, output_plot_path=output_plot_path,
                                    column_properties=column_properties, global_x_label=global_x_label,
                                    horizontal_margin=horizontal_margin, vertical_margin=vertical_margin,
                                    y_min=y_min, y_max=y_max,
                                    force_monochrome_group=force_monochrome_group,
                                    x_min=x_min, x_max=x_max,
                                    y_labels_by_group_name=y_labels_by_group_name,
                                    color_by_group_name=color_by_group_name, global_y_label=global_y_label,
                                    combine_groups=combine_groups, semilog_y_min_bound=semilog_y_min_bound,
                                    group_row_margin=group_row_margin,
                                    group_name_order=group_name_order,
                                    fig_width=fig_width, fig_height=fig_height,
                                    global_y_label_pos=global_y_label_pos, legend_column_count=legend_column_count,
                                    show_grid=show_grid,
                                    show_subgrid=show_subgrid,
                                    x_tick_list=x_tick_list,
                                    x_tick_label_list=x_tick_label_list,
                                    x_tick_label_angle=x_tick_label_angle,
                                    y_tick_list=y_tick_list,
                                    y_tick_label_list=y_tick_label_list,
                                    semilog_y=semilog_y, semilog_y_base=semilog_y_base,
                                    left_y_label=left_y_label,
                                    extra_plds=extra_plds,
                                    plot_title=plot_title,
                                    show_legend=show_legend,
                                    legend_position=legend_position,
                                    style_list=style_list)
    except Exception as ex:
        enb.logger.error(f"Error rendering to {output_plot_path}:\n{repr(ex)}")
        raise ex


def render_plds_by_group(pds_by_group_name, output_plot_path, column_properties,
                         global_x_label, global_y_label,
                         # General figure configuration
                         combine_groups=False, color_by_group_name=None, group_name_order=None,
                         fig_width=None, fig_height=None,
                         global_y_label_pos=None, legend_column_count=None,
                         force_monochrome_group=True,
                         # Axis configuration
                         show_grid=None, show_subgrid=None,
                         semilog_y=None, semilog_y_base=10, semilog_y_min_bound=1e-10,
                         group_row_margin=None,
                         # Axis limits
                         x_min=None, x_max=None,
                         horizontal_margin=None, vertical_margin=None,
                         y_min=None, y_max=None,
                         # Optional axis labeling
                         y_labels_by_group_name=None,
                         x_tick_list=None, x_tick_label_list=None, x_tick_label_angle=0,
                         y_tick_list=None, y_tick_label_list=None,
                         left_y_label=False,
                         # Additional plottable data
                         extra_plds=tuple(),
                         # Plot title
                         plot_title=None, show_legend=True, legend_position=None,
                         # Matplotlib styles
                         style_list=("default",),
                         ):
    """Render lists of plotdata.PlottableData instances indexed by group name.
    Each group is rendered in a row (subplot), with a shared X axis.
    Groups can also be combined into a single row (subplot), i.e., rending all plottable data into that single subplot.
    
    When applicable, None values are substituted by
    default values given enb.config.options (guaranteed to be updated thanks to the
    @enb.parallel.parallel decorator) and the current context.
    
    Mandatory parameters:
    
    :param pds_by_group_name: dictionary of lists of PlottableData instances
    :param output_plot_path: path to the file to be created with the plot
    :param column_properties: ColumnProperties instance for the column being plotted
    :param global_x_label: x-axis label shared by all subplots (there can be just one subplot)
    :param global_y_label: y-axis label shared by all subplots (there can be just one subplot)
    
    General figure configuration. If None, most of these values are retrieved from
    the [enb.aanalysis.Analyzer] section of `*.ini` files.
    
    :param combine_groups: if False, each group is plotted in a different row. If True,
        all groups share the same subplot (and no group name is displayed).
    :param color_by_group_name: if not None, a dictionary of pyplot colors for the groups,
        indexed with the same keys as `pds_by_group_name`.
    :param group_name_order: if not None, it contains the order in which groups are
        displayed. If None, alphabetical, case-insensitive order is applied.
    :param fig_width: figure width. The larger the figure size, the smaller the text will look.
    :param fig_height: figure height. The larger the figure size, the smaller the text will look.
    :param legend_column_count: when the legend is shown, use this many columns.
    :param force_monochrome_group: if True, all plottable data with non-None color in each group
      is set to the same color, defined by color_cycle.
    
    Axis configuration:
    
    :param show_grid: if True, or if None and options.show_grid, grid is displayed
         aligned with the major axes.
    :param show_grid: if True, or if None and options.show_subgrid, grid is displayed
        aligned with the minor axes.
    :param semilog_y: if True, a logarithmic scale is used in the Y axis.
    :param semilog_y_base: if semilog_y is True, the logarithm base employed.
    :param semilog_y_min_bound: if semilog_y is True, make y_min the maximum of y_min and this value.
    :param group_row_margin: if provided, this margin is applied between rows of groups
    
    Axis limits:
    
    :param x_min: if not None, force plots to have this value as left end.
    :param x_max: if not None, force plots to have this value as right end.
    :param horizontal_margin: Horizontal margin to be added to the figures,
      expressed as a fraction of the horizontal dynamic range.
    :param vertical_margin: Vertical margin to be added to the figures,
      expressed as a fraction of the horizontal dynamic range.
    :param y_min: if not None, force plots to have this value as bottom end.
    :param y_max: if not None, force plots to have this value as top end.
    
    Optional axis labeling:
    
    :param y_labels_by_group_name: if not None, a dictionary of labels for the groups,
      indexed with the same keys as pds_by_group_name.
    :param x_tick_list: if not None, these ticks will be displayed in the x axis.
    :param x_tick_label_list: if not None, these labels will be displayed in the x axis.
      Only used when x_tick_list is not None.
    :param x_tick_label_angle: when label ticks are specified, they will be rotated to this angle
    :param y_tick_list: if not None, these ticks will be displayed in the y axis.
    :param y_tick_label_list: if not None, these labels will be displayed in the y axis.
      Only used when y_tick_list is not None.
    :param left_y_label: if True, the group label is shown to the left instead of to the right
      
    Additional plottable data:
    :param extra_plds: an iterable of additional PlottableData instances to be rendered in all subplots. 
    
    Global title:
    
    :param plot_title: title to be displayed.
    :param show_legend: if True, legends are added to the plot.
    :param legend_position: position of the legend (if shown). It can be "title" to display
      it above the plot, or any matplotlib-recognized argument to the loc argument of legend().
    
    Matplotlib styles:
    
    :param style_list: list of valid style arguments recognized by `matplotlib.use`. Each element can be any
      of matplotlib's default styles or a path to a valid matplotlibrc. Styles are applied from left to right, 
      overwriting definitions without warning. By default, matplotlib's "default" mode is applied. 
    """
    with enb.logger.info_context(f"Rendering {len(pds_by_group_name)} plottable data groups to {output_plot_path}",
                                 sep="...\n", msg_after=f"Done rendering into {output_plot_path}"):
        if len(pds_by_group_name) < 1:
            enb.logger.info("Warning: trying to render an empty pds_by_group_name dict. "
                            f"output_plot_path={output_plot_path}, column_properties={column_properties}. "
                            f"No analysis is performed.")
            return

        legend_column_count = legend_column_count if legend_column_count is not None \
            else enb.config.ini.get_key("enb.aanalysis.Analyzer", "legend_column_count")
        if legend_column_count:
            for name, pds in pds_by_group_name.items():
                for pld in pds:
                    pld.legend_column_count = legend_column_count

        y_min = column_properties.hist_min if y_min is None else y_min
        y_min = max(semilog_y_min_bound, y_min if y_min is not None else 0) \
            if ((column_properties is not None and column_properties.semilog_y) or semilog_y) else y_min
        y_max = column_properties.hist_max if y_max is None else y_max

        if group_name_order is None:
            sorted_group_names = natsort.natsorted(pds_by_group_name.keys(), alg=natsort.IGNORECASE)
            if str(sorted_group_names[0]).lower() == "all":
                sorted_group_names = sorted_group_names[1:] + [str(n) for n in sorted_group_names[:1]]
        else:
            sorted_group_names = []
            for group_name in group_name_order:
                if group_name not in pds_by_group_name:
                    enb.logger.warn(
                        f"Warning: {repr(group_name)} was provided in group_name_order but is not one of the "
                        f"produced groups: {sorted(list(pds_by_group_name.keys()))}. Ignoring.")
                else:
                    sorted_group_names.append(group_name)
            for g in pds_by_group_name.keys():
                if g not in sorted_group_names:
                    if options.verbose > 2:
                        enb.logger.warn(f"Warning: {repr(g)} was not provided in group_name_order but is one of the "
                                        f"produced groups: {sorted(list(pds_by_group_name.keys()))}. Appending automatically.")
                    sorted_group_names.append(g)

        if combine_groups:
            for i, g in enumerate(sorted_group_names):
                if show_legend:
                    if (i == 0 and g.lower() != "all") or len(sorted_group_names) > 1:
                        try:
                            pds_by_group_name[g][0].label = \
                                y_labels_by_group_name[
                                    g] if y_labels_by_group_name and g in y_labels_by_group_name else g
                            pds_by_group_name[g][0].legend_position = legend_position
                        except IndexError:
                            # Ignore empty groups
                            continue
                for pld in pds_by_group_name[g]:
                    pld.marker = marker_cycle[i]

        y_labels_by_group_name = {g: g for g in sorted_group_names} \
            if y_labels_by_group_name is None else y_labels_by_group_name

        if color_by_group_name is None:
            color_by_group_name = {}
            for i, group_name in enumerate(sorted_group_names):
                color_by_group_name[group_name] = color_cycle[i % len(color_cycle)]
        if os.path.dirname(output_plot_path):
            os.makedirs(os.path.dirname(output_plot_path), exist_ok=True)

        # Render all gathered data with the selected configuration
        with plt.style.context([]):
            # Apply selected styles in the given order, based on a default context
            for style in (style_list if style_list is not None else []):
                if not style:
                    enb.logger.info(f"Ignoring empty style ({repr(style)}")
                    continue
                elif style.lower() == "default":
                    continue
                if style in matplotlib.style.available or os.path.isfile(style):
                    # Matplotlib style name or full path
                    plt.style.use(style)
                elif os.path.isfile(
                        os.path.join(enb.enb_installation_dir, "config", "mpl_styles", os.path.basename(style))):
                    # Path relative to enb's custom mpl_styles
                    plt.style.use(
                        os.path.join(enb.enb_installation_dir, "config", "mpl_styles", os.path.basename(style)))
                elif style == "xkcd":
                    apply_xkcd_style()
                else:
                    raise ValueError(f"Unrecognized style {repr(style)}.")

            fig_width = enb.config.ini.get_key(section="enb.aanalysis.Analyzer", name="fig_width") \
                if fig_width is None else fig_width
            fig_height = enb.config.ini.get_key(section="enb.aanalysis.Analyzer", name="fig_height") \
                if fig_height is None else fig_height

            fig, group_axis_list = plt.subplots(
                nrows=max(len(sorted_group_names), 1) if not combine_groups else 1,
                ncols=1, sharex=True, sharey=combine_groups,
                figsize=(fig_width, max(3, 0.5 * len(sorted_group_names) if fig_height is None else fig_height)))

            if combine_groups:
                group_axis_list = [group_axis_list]
            elif len(sorted_group_names) == 1:
                group_axis_list = [group_axis_list]

            plot_title = plot_title if plot_title is not None \
                else enb.config.ini.get_key("enb.aanalysis.Analyzer", "plot_title")
            if plot_title:
                plt.suptitle(plot_title)

            semilog_x, semilog_y = False, semilog_y if semilog_y is not None else semilog_y

            if combine_groups:
                assert len(group_axis_list) == 1
                group_name_axes = zip(sorted_group_names, group_axis_list * len(sorted_group_names))
            else:
                group_name_axes = zip(sorted_group_names, group_axis_list)

            # Compute global extrema
            global_x_min = float("inf")
            global_x_max = float("-inf")
            global_y_min = float("inf")
            global_y_max = float("-inf")
            for pld in (plottable for pds in pds_by_group_name.values() for plottable in pds):
                if not isinstance(pld, PlottableData2D):
                    continue
                x_values = np.array(pld.x_values, copy=False)
                if len(x_values) > 0:
                    x_values = x_values[~np.isnan(x_values)]
                global_x_min = min(global_x_min, x_values.min() if len(x_values) > 0 else global_x_min)
                global_x_max = max(global_x_min, x_values.max() if len(x_values) > 0 else global_x_min)
                y_values = np.array(pld.y_values, copy=False)
                if len(y_values) > 0:
                    y_values = y_values[~np.isnan(y_values)]
                global_y_min = min(global_y_min, y_values.min() if len(y_values) > 0 else global_y_min)
                global_y_max = max(global_y_min, y_values.max() if len(y_values) > 0 else global_y_min)
            if global_x_max - global_x_min > 1:
                global_x_min = math.floor(global_x_min) if not math.isinf(global_x_min) else global_x_min
                global_x_max = math.ceil(global_x_max) if not math.isinf(global_x_max) else global_x_max
            if global_y_max - global_y_min > 1:
                global_y_min = math.floor(global_y_min) if not math.isinf(global_y_min) else global_y_min
                global_y_max = math.ceil(global_y_max) if not math.isinf(global_y_max) else global_y_max
            if column_properties:
                global_x_min = column_properties.plot_min if column_properties.plot_min is not None else global_x_min
                global_x_max = column_properties.plot_max if column_properties.plot_max is not None else global_x_max

            for i, (group_name, group_axes) in enumerate(group_name_axes):
                group_color = color_by_group_name[group_name]
                for pld in pds_by_group_name[group_name]:
                    pld.x_label = None
                    pld.y_label = None
                    d = dict()
                    if force_monochrome_group:
                        pld.color = group_color if pld.color is None else pld.color
                    d.update(color=pld.color)
                    try:
                        pld.extra_kwargs.update(d)
                    except AttributeError:
                        pld.extra_kwargs = d
                    try:
                        pld.render(axes=group_axes)
                    except Exception as ex:
                        raise Exception(
                            f"Error rendering {pld} -- {group_name} -- {output_plot_path}:\n{repr(ex)}") from ex
                    semilog_x = semilog_x or (column_properties.semilog_x if column_properties else False)
                    semilog_y = semilog_y or (column_properties.semilog_y if column_properties else False) or semilog_y

                if not combine_groups or i == 0:
                    for pld in extra_plds:
                        pld.render(axes=group_axes)

            for (group_name, group_axes) in zip(sorted_group_names, group_axis_list):
                if y_min != y_max:
                    group_axes.set_ylim(y_min, y_max)

                if semilog_x:
                    x_base = column_properties.semilog_x_base if column_properties is not None else 10
                    group_axes.semilogx(base=x_base)
                    group_axes.get_xaxis().set_major_locator(matplotlib.ticker.LogLocator(base=x_base))
                else:
                    group_axes.get_xaxis().set_major_locator(
                        matplotlib.ticker.MaxNLocator(nbins="auto", integer=True, min_n_ticks=5))
                    group_axes.get_xaxis().set_minor_locator(matplotlib.ticker.AutoMinorLocator())

                if semilog_y:
                    base_y = column_properties.semilog_y_base if column_properties is not None else semilog_y_base
                    group_axes.semilogy(base=base_y)
                    if combine_groups or len(sorted_group_names) <= 2:
                        numticks = 11
                    elif len(sorted_group_names) <= 5 and not column_properties.semilog_y:
                        numticks = 6
                    elif len(sorted_group_names) <= 10:
                        numticks = 4
                    else:
                        numticks = 3
                    group_axes.get_yaxis().set_major_locator(
                        matplotlib.ticker.LogLocator(base=base_y, numticks=numticks))
                    group_axes.grid(True, "major", axis="y", alpha=0.2)
                else:
                    group_axes.get_yaxis().set_major_locator(matplotlib.ticker.MaxNLocator(nbins="auto", integer=False))
                    group_axes.get_yaxis().set_minor_locator(matplotlib.ticker.AutoMinorLocator())
                if not combine_groups:
                    if not left_y_label:
                        group_axes.get_yaxis().set_label_position("right")
                    group_axes.set_ylabel(y_labels_by_group_name[group_name]
                                          if group_name in y_labels_by_group_name
                                          else enb.atable.clean_column_name(group_name),
                                          rotation=0 if not left_y_label else 90,
                                          ha="left" if not left_y_label else "center",
                                          va="center" if not left_y_label else "bottom")

            if column_properties and column_properties.hist_label_dict is not None:
                x_tick_values = sorted(column_properties.hist_label_dict.keys())
                x_tick_label_list = [column_properties.hist_label_dict[x] for x in x_tick_values]

            group_row_margin = group_row_margin if group_row_margin is not None \
                else enb.config.ini.get_key("enb.aanalysis.Analyzer", "group_row_margin")
            group_row_margin = float(group_row_margin) if group_row_margin is not None else group_row_margin
            if group_row_margin is None and len(pds_by_group_name) > 5:
                if len(pds_by_group_name) <= 7:
                    group_row_margin = 0.5
                elif len(pds_by_group_name) <= 12:
                    group_row_margin = 0.6
                else:
                    group_row_margin = 0.7
                enb.logger.info("The `group_row_margin` option "
                                f"was likely too small to display all {len(pds_by_group_name)} groups: "
                                f"automatically adjusting to {group_row_margin}. You can set "
                                f"your desired value at the [enb.aanalysis.Analyzer] section in your *.ini files,"
                                f"or passing e.g., `group_row_margin=0.9` to your Analyzer get_df() "
                                f"or adjusting the figure height with `fig_height`.")
                
            if group_row_margin is not None:
                plt.subplots_adjust(hspace=group_row_margin)

            # Set the axis limits
            xlim = [global_x_min, global_x_max]
            ylim = [global_y_min, global_y_max]
            xlim[0] = xlim[0] if x_min is None else x_min
            xlim[1] = xlim[1] if x_max is None else x_max
            ylim[0] = ylim[0] if y_min is None else y_min
            ylim[1] = ylim[1] if y_max is None else y_max
            # Translate relative margin to absolute margin
            horizontal_margin = horizontal_margin if horizontal_margin is not None \
                else enb.config.ini.get_key("enb.aanalysis.Analyzer", "horizontal_margin")
            vertical_margin = vertical_margin if vertical_margin is not None \
                else enb.config.ini.get_key("enb.aanalysis.Analyzer", "vertical_margin")

            h_margin = horizontal_margin * (xlim[1] - xlim[0])
            v_margin = vertical_margin * (ylim[1] - ylim[0])
            xlim = [xlim[0] - h_margin, xlim[1] + h_margin]
            ylim = [ylim[0] - v_margin, ylim[1] + v_margin]
            # Apply changes to the figure
            if xlim[0] != xlim[1] and not math.isnan(xlim[0]) and not math.isnan(xlim[1]):
                plt.xlim(*xlim)
                ca = plt.gca()
                for group_axes in group_axis_list:
                    plt.sca(group_axes)
                    plt.xlim(*xlim)
                plt.sca(ca)
            if ylim[0] != ylim[1] and not math.isnan(ylim[0]) and not math.isnan(ylim[1]) \
                    and (not semilog_y or (ylim[0] > 0 and ylim[1] > 0)):
                plt.ylim(*ylim)
                ca = plt.gca()
                for group_axes in group_axis_list:
                    plt.sca(group_axes)
                    plt.ylim(*ylim)
                plt.sca(ca)

            if xlim[1] < 1e-2:
                x_tick_label_angle = 90 if x_tick_label_angle is not None else x_tick_label_angle
            show_grid = show_grid if show_grid is not None \
                else enb.config.ini.get_key("enb.aanalysis.Analyzer", "show_grid")
            show_subgrid = show_subgrid if show_subgrid is not None \
                else enb.config.ini.get_key("enb.aanalysis.Analyzer", "show_subgrid")
            ca = plt.gca()

            for group_axes in group_axis_list:
                plt.sca(group_axes)
                plt.xticks(x_tick_list, x_tick_label_list, rotation=x_tick_label_angle)
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

                if show_grid:
                    plt.grid(which="major", axis="both", alpha=0.5)
                if show_subgrid:
                    plt.grid(which="minor", axis=subgrid_axis, alpha=0.4)

            plt.sca(ca)

            if global_x_label or global_y_label:
                # The x axis needs to be placed on the last horizontal group
                # so that it can be correctly aligned
                ca = plt.gca()
                for group_axes in group_axis_list[-1:]:
                    plt.sca(group_axes)
                    plt.xlabel(global_x_label)
                plt.sca(ca)

                # Add an otherwise transparent subplot for global labels
                if global_y_label is not None:
                    plt.gcf().add_subplot(111, frame_on=False)
                    plt.tick_params(labelcolor="none", bottom=False, left=False)
                    plt.grid(False)
                    plt.minorticks_off()
                    plt.ylabel(global_y_label, labelpad=15)

            with enb.logger.info_context(f"Saving plot to {output_plot_path} "):
                if os.path.dirname(output_plot_path):
                    os.makedirs(os.path.dirname(output_plot_path), exist_ok=True)
                plt.savefig(output_plot_path, bbox_inches="tight")
                if output_plot_path.endswith(".pdf"):
                    plt.savefig(output_plot_path[:-3] + "png", bbox_inches="tight", dpi=300,
                                transparent=True)

            plt.close()
