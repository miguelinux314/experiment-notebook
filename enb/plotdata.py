#!/usr/bin/env python3
"""Utils to plot data (thinking about pyplot).
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/09/10"

import os
import itertools
import glob
import collections
import matplotlib
from matplotlib import pyplot as plt
import numpy as np
from scipy.stats import norm
import enb



class PlottableData:
    """Base class for plottable data elements. Subclasses are instantiated
    by the analyzers to define sequences of plotting actions (with pyplot)
    that result in the desired figure.
    """
    # pylint: disable=too-many-instance-attributes

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
        # pylint: disable=too-many-arguments
        self.data = data
        self.axis_labels = axis_labels
        self.label = label
        self.extra_kwargs = extra_kwargs if extra_kwargs is not None else {}
        self.alpha = alpha if alpha is not None else self.alpha
        self.legend_column_count = legend_column_count \
            if legend_column_count is not None else self.legend_column_count
        self.legend_position = legend_position \
            if legend_position is not None else self.legend_position
        self.marker = marker
        self.marker_size = marker_size
        self.color = color if color is not None else self.color

    def render(self, axes=None):
        """Render data in current figure.

        :param axes: if not None, those axes are used for plotting instead of
          plt
        """
        raise NotImplementedError

    def render_axis_labels(self, axes=None):
        """Add axis labels in current figure - don't show or write the result

        :param axes: if not None, those axes are used for plotting instead of
          plt
        """
        raise NotImplementedError

    def render_legend(self, axes=None):
        """Tell numpy to render the legend based on self.legend_position.
        In addition to numpy's legend positions, 'title' is available for
        top center outside the grid.
        """
        axes = plt if axes is None else axes
        if self.legend_position == "title":
            legend = axes.legend(loc="lower center", bbox_to_anchor=(0.5, 1),
                                 ncol=self.legend_column_count,
                                 edgecolor=(0, 0, 0, 0.2))
            facecolor = (1, 1, 1, 0)
        else:
            legend = axes.legend(
                loc=self.legend_position
                if self.legend_position is not None else "best",
                ncol=self.legend_column_count, edgecolor=(0, 0, 0, 0.2))
            facecolor = (1, 1, 1, 1)

        legend.get_frame().set_alpha(None)
        legend.get_frame().set_facecolor(facecolor)

    def __repr__(self):
        return f"{self.__class__.__name__}(color={repr(self.color)})"


class PlottableData2D(PlottableData):
    """Base class for 2D plottable data.
    """

    # pylint: disable=abstract-method

    def __init__(self, x_values, y_values,
                 x_label=None, y_label=None,
                 label=None, extra_kwargs=None,
                 remove_duplicates=False,
                 alpha=None, legend_column_count=None,
                 marker=None, color=None,
                 marker_size=None):
        """
        :param x_values, y_values: values to be plotted (only a reference is
          kept)
        :param x_label, y_label: axis labels
        :param label: line legend label
        :param extra_kwargs: extra arguments to be passed to plt.plot
        """
        # pylint: disable=too-many-arguments,too-many-locals
        assert len(x_values) == len(y_values), \
            f"Invalid lengths of x_values and y_values ({len(x_values), len(y_values)}"
        if remove_duplicates:
            found_pairs = collections.OrderedDict()
            for x_val, y_val in zip(x_values, y_values):
                found_pairs[(x_val, y_val)] = (x_val, y_val)
            if found_pairs:
                x_values, y_values = zip(*found_pairs.values())
            else:
                x_values = []
                y_values = []

        super().__init__(data=(x_values, y_values),
                         axis_labels=(x_label, y_label),
                         label=label, extra_kwargs=extra_kwargs, alpha=alpha,
                         legend_column_count=legend_column_count,
                         marker_size=marker_size, color=color,
                         marker=marker)
        self.x_values = x_values
        self.y_values = y_values
        self.x_label = x_label
        self.y_label = y_label

    def render_axis_labels(self, axes=None):
        """Show the labels in label list (if not None) or in
        self.axis_label_list (if label_list None) in the current figure.

        :param axes: if not None, those axes are used for plotting instead of
          plt
        """
        axes = plt if axes is None else axes
        if self.x_label is not None:
            axes.set_xlabel(self.x_label)
        if self.y_label is not None:
            axes.set_ylabel(self.y_label)

    def diff(self, other, ylabel_suffix="_difference"):
        """Calculate the difference with another PlattableData2D instance.
        The x values are maintained and other's y values are subtracted
        from self's.
        """
        assert len(self.x_values) == len(other.x_values)
        assert len(self.y_values) == len(other.y_values)
        assert all(s == o for s, o in zip(self.x_values, other.x_values))
        return PlottableData2D(
            x_values=self.x_values,
            y_values=[s - o for s, o in zip(self.y_values, other.y_values)],
            x_label=self.x_label,
            y_label=f"{self.y_label}{ylabel_suffix}",
            legend_column_count=self.legend_column_count)

    def shift_x(self, constant):
        """Add a constant to all x values.
        """
        self.y_values = [y + constant for y in self.y_values]

    def shift_y(self, constant):
        """Add a constant to all y values.
        """
        self.y_values = [y + constant for y in self.y_values]


class LineData(PlottableData2D):
    """Straight lines linking the defined x,y pairs.
    """

    def __init__(self, marker="o", marker_size=5, line_width=1.5, **kwargs):
        super().__init__(marker=marker, marker_size=marker_size, **kwargs)
        self.line_width = line_width

    def render(self, axes=None):
        try:
            original_kwargs = self.extra_kwargs
            extra_kwargs = dict(self.extra_kwargs)

            try:
                marker_size = extra_kwargs["ms"]
                del extra_kwargs["ms"]
            except KeyError:
                marker_size = self.marker_size

            axes.plot(self.x_values, self.y_values, label=self.label,
                      alpha=self.alpha,
                      marker=self.marker, ms=marker_size,
                      linewidth=self.line_width,
                      **extra_kwargs)
            axes = plt if axes is None else axes
            self.render_axis_labels(axes=axes)
            if self.label is not None and self.legend_column_count != 0:
                self.render_legend(axes=axes)
        finally:
            self.extra_kwargs = original_kwargs


class ScatterData(PlottableData2D):
    """Individual markers at the specified x,y positions.
    """

    def __init__(self, marker="o", alpha=0.5, marker_size=3, **kwargs):
        super().__init__(marker=marker, alpha=alpha, marker_size=marker_size,
                         **kwargs)

    def render(self, axes=None):
        axes = plt if axes is None else axes
        self.extra_kwargs["s"] = self.marker_size

        axes.scatter(self.x_values, self.y_values, label=self.label,
                     alpha=self.alpha,
                     marker=self.marker,
                     **self.extra_kwargs)
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            self.render_legend(axes=axes)


class BarData(PlottableData2D):
    """Vertical (horizonal) bars at x (y) positions of height (width) y (x).
    """
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
                 edgecolor=matplotlib.colors.colorConverter.to_rgba(
                     self.color, 0.9) if self.color else None,
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
    """Horizontal segments at the defined x,y positions.
    """
    where = "post"

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.step(self.x_values, self.y_values, label=self.label,
                  alpha=self.alpha,
                  where=self.where, **self.extra_kwargs)
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            self.render_legend(axes=axes)


class ErrorLines(PlottableData2D):
    """One or more error lines
    """

    def __init__(self, x_values, y_values, err_neg_values, err_pos_values,
                 vertical=False,
                 alpha=0.5, color=None,
                 marker_size=1, cap_size=2,
                 line_width=1, **kwargs):
        """
        :param x_values, y_values: centers of the error lines
        :param err_neg_values: list of lengths for the negative part of the error
        :param err_pos_values: list of lengths for the positive part of the error
        :param vertical: determines whether the error bars are vertical or horizontal
        """
        # pylint: disable=too-many-arguments
        super().__init__(x_values=x_values, y_values=y_values,
                         remove_duplicates=False,
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
        # When std is computed for constant data, nan is returned. Replace
        # those with 0 to avoid warnings.
        err_argument = err_argument[:, :len(self.x_values)]

        try:
            if self.vertical:
                axes.errorbar(self.x_values, self.y_values, yerr=err_argument,
                              fmt="-o", capsize=self.cap_size, capthick=0.5,
                              lw=0, elinewidth=self.line_width,
                              ms=self.marker_size,
                              alpha=self.alpha,
                              **self.extra_kwargs)
            else:
                axes.errorbar(self.x_values, self.y_values, xerr=err_argument,
                              fmt="-o", capsize=self.cap_size, capthick=0.5,
                              lw=0, elinewidth=self.line_width,
                              ms=self.marker_size,
                              alpha=self.alpha,
                              **self.extra_kwargs)
        except UserWarning as ex:
            raise ValueError(
                f"Error rendering {self}. x_values={repr(self.x_values)}, "
                f"y_values={repr(self.y_values)}, "
                f"self.extra_kwargs={self.extra_kwargs} "
                f"self.err_neg={self.err_neg}, "
                f"self.err_pos={self.err_pos},") from ex

        assert len(self.x_values) == len(self.y_values)


class Rectangle(PlottableData2D):
    """Render a rectangle (line only) in a given position.
    """
    alpha = 0.5

    def __init__(self, x_values, y_values, width, height, angle_degrees=0,
                 fill=False,
                 line_width=1, **kwargs):
        """
        :param x_values: a list with a single element with the x position of
          the rectangle's center
        :param y_values: a list with a single element with the y position of
          the rectangle's center
        :param width: width of the rectangle
        :param height: height of the rectangle
        """
        # pylint: disable=too-many-arguments
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
    """Render a horizontal or vertical line segment centered at a given
    position.
    """
    alpha = 0.5

    def __init__(self, x_values, y_values, length, vertical=True, line_width=1,
                 **kwargs):
        """
        :param x_values: a list with a single element with the x position of
          the rectangle's center
        :param y_values: a list with a single element with the y position of
          the rectangle's center
        :param length: length of the line
        """
        # pylint: disable=too-many-arguments
        super().__init__(x_values=x_values, y_values=y_values, **kwargs)
        assert length >= 0, length
        assert line_width >= 0, line_width
        self.length = length
        self.line_width = line_width
        self.vertical = vertical

    @property
    def center(self):
        """Line center (the line crosses this point).
        """
        return self.x_values[0], self.y_values[0]

    def render(self, axes=None):
        assert len(self.x_values) == 1, self.x_values
        assert len(self.y_values) == 1, self.y_values
        axes = plt if axes is None else axes
        center = self.center
        if self.vertical:
            x_values = [center[0], center[0]]
            y_values = [center[1] - self.length / 2,
                        center[1] + self.length / 2]
        else:
            x_values = [center[0] - self.length / 2,
                        center[0] + self.length / 2]
            y_values = [center[1], center[1]]

        axes.plot(x_values, y_values, color=self.color, alpha=self.alpha,
                  linewidth=self.line_width)


class HorizontalBand(PlottableData2D):
    """Colored band surrounding a line function given by the provided x,
    y positions, with positive (up) and negative (down) widths.
    """
    alpha = 0.5
    degradation_band_count = 25
    show_bounding_lines = False

    def __init__(self, x_values, y_values, pos_height_values, neg_height_values,
                 show_bounding_lines=None,
                 degradation_band_count=None,
                 std_band_add_xmargin=False,
                 **kwargs):
        # pylint: disable=too-many-arguments
        super().__init__(x_values=x_values, y_values=y_values,
                         extra_kwargs=kwargs)
        self.extra_kwargs["lw"] = 0
        self.pos_height_values = np.array(pos_height_values)
        self.neg_height_values = np.array(neg_height_values)
        self.show_bounding_lines = show_bounding_lines \
            if show_bounding_lines is not None else self.show_bounding_lines
        self.degradation_band_count = degradation_band_count \
            if degradation_band_count is not None \
            else self.degradation_band_count
        self.std_band_add_xmargin = std_band_add_xmargin

    def render(self, axes=None):
        # pylint: disable=too-many-locals
        for i in range(self.degradation_band_count):
            band_fraction = i / self.degradation_band_count
            next_band_fraction = (i + 1) / self.degradation_band_count
            band_probability = \
                1 - (norm.cdf(band_fraction) - norm.cdf(-band_fraction))
            band_x_values = np.array(self.x_values)
            band_y_values = np.array(self.y_values)
            pos_height_values = np.array(self.pos_height_values)
            neg_height_values = np.array(self.neg_height_values)
            if self.std_band_add_xmargin:
                new_x_values = []
                new_y_values = []
                new_pos_heights = []
                new_neg_heights = []
                for x_value, y_value, pos_height, neg_height in zip(
                        band_x_values, band_y_values,
                        pos_height_values, neg_height_values):
                    new_x_values.extend([x_value - 0.5, x_value + 0.5])
                    new_y_values.extend([y_value, y_value])
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


class HorizontalLine(PlottableData2D):
    """Draw a horizontal line across the whole subplot.
    """

    def __init__(self, y_position, line_width=1, line_style='-', **kwargs):
        super().__init__(**kwargs, x_values=[0], y_values=[y_position])
        self.y_position = y_position
        self.line_width = line_width
        self.line_style = line_style

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.axhline(y=self.y_position, color=self.color,
                     linestyle=self.line_style,
                     lw=self.line_width, alpha=self.alpha)


class VerticalLine(PlottableData2D):
    """Draw a horizontal line across the whole subplot.
    """

    def __init__(self, x_position, line_width=1, line_style='-', **kwargs):
        super().__init__(**kwargs, x_values=[x_position], y_values=[0])
        self.x_position = x_position
        self.line_width = line_width
        self.line_style = line_style

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.axvline(x=self.x_position, color=self.color,
                     linestyle=self.line_style,
                     lw=self.line_width, alpha=self.alpha)


class Histogram2D(PlottableData2D):
    """Represent the result of a 2D histogram.
    See https://matplotlib.org/stable/gallery/color/colormap_reference.html
    """
    # pylint: disable=too-many-instance-attributes

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

    def __init__(self, x_edges, y_edges, matrix_values, color_map=None,
                 colormap_label=None, vmin=None, vmax=None,
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
        :param kwargs: additional parameters passed to the parent class
          initializer
        """
        # pylint: disable=too-many-arguments
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

        axes_image = axes.imshow(self.matrix_values.swapaxes(0,1), cmap=cmap,
                                 origin=self.origin,
                                 interpolation=self.interpolation,
                                 alpha=self.alpha, aspect=self.aspect,
                                 vmin=self.vmin, vmax=self.vmax)
        if self.show_cmap_bar:
            plt.colorbar(axes_image, label=self.colormap_label,
                         ticks=list(np.linspace(self.vmin, self.vmax, 5))
                         if self.vmin is not None and self.vmax is not None else None,
                         fraction=0.1, ax=axes)
        if self.y_label:
            axes.set_ylabel(self.y_label)

class Table(PlottableData2D):
    """Display a 2D table of data.
    """
    def __init__(self, x_values, y_values, cell_text, x_label=None, y_label=None,
                 cell_alignment="center",
                 col_header_aligment="center",
                 row_header_alignment="left",
                 edges="open",
                 highlight_best_row=None,
                 highlight_best_column=None):
        """
        :param x_values: list of column headers
        :param y_values: list of row headers
        :param cell_text: list of lists containing the cell text to display
        :param cell_alignment: text alignment for the data cells
        :param col_header_alignment: text alignment for the column headers
        :param row_header_alignment: text alignment for the row headers
        :param edges: argument passed to plt.table
          (substring of 'BRTL' or {'open', 'closed', 'horizontal', 'vertical'})
        :param highlight_best_row: if not None, it must be either "low" or "high". In those cases, the
          best (lowest or highest) value of each column is highlighted.
        :param highlight_best_column: if not None, it must be either "low" or "high". In those cases, the
          best (lowest or highest) value of each row is highlighted.
        """
        super().__init__(x_values=[None], y_values=[None], x_label=x_label, y_label=y_label)
        self.x_values = x_values
        self.y_values = y_values
        self.cell_text = cell_text
        self.cell_alignment = cell_alignment
        self.col_header_alignment = col_header_aligment
        self.row_header_alignment = row_header_alignment
        self.edges = edges
        self.highlight_best_row = highlight_best_row
        self.highlight_best_column = highlight_best_column

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.axis('tight')
        axes.axis('off')

        table = axes.table(cellText=self.cell_text,colLabels=self.x_values,rowLabels=self.y_values,
                   loc="center", cellLoc=self.cell_alignment,
                   rowLoc=self.row_header_alignment, colLoc=self.col_header_alignment,
                   bbox=[0,0,1,1], edges=self.edges)

        # Make headers bold and the background transparent
        for (row, col), cell in table.get_celld().items():
            if (row == 0) or (col == -1):
                cell.set_text_props(
                    fontproperties=matplotlib.font_manager.FontProperties(weight='bold'))
            cell.set_facecolor((1,1,0,0))

        # Highlight the best column in each row
        if self.highlight_best_column is not None:
            for row_index, row in enumerate(self.cell_text):
                row_values = [float(c) for c in row]
                if self.highlight_best_column.lower() == "low":
                    best_value = min(row_values)
                else:
                    assert self.highlight_best_column.lower() == "high", f"Invalid {self.highlight_best_column=}"
                    best_value = max(row_values)
                for col_index, col_value in enumerate(row_values):
                    if col_value == best_value:
                        table.get_celld()[(row_index+1, col_index)].set_text_props(
                            fontproperties=matplotlib.font_manager.FontProperties(weight='bold'))

        # Highlight the best row in each column
        if self.highlight_best_row is not None:
            column_count = len(self.cell_text[0])
            for col_index in range(column_count):
                col_values = [float(r[col_index]) for r in self.cell_text]
                if self.highlight_best_row == "low":
                    best_value = min(col_values)
                else:
                    assert self.highlight_best_row == "high", f"Invalid {self.highlight_best_row=}"
                    best_value = max(col_values)
                for row_index, row in enumerate(self.cell_text):
                    if float(row[col_index]) == best_value:
                        table.get_celld()[(row_index+1, col_index)].set_text_props(
                            fontproperties=matplotlib.font_manager.FontProperties(weight='bold'))


def get_available_styles():
    """Get a list of all styles available for plotting. It includes installed
    matplotlib styles plus custom styles
    """
    return sorted(
        itertools.chain(get_matlab_styles(), get_local_styles(), ["default"]))


def get_matlab_styles():
    """Return the list of installed matlab styles.
    """
    return sorted(
        [str(s) for s in matplotlib.style.available if s[0] != "_"] + ["xkcd"])


def get_local_styles():
    """Get the list of basenames of all styles in the enb/config/mpl_styles
    folder.
    """
    return sorted(os.path.basename(p)
                  for p in glob.glob(
        os.path.join(enb.enb_installation_dir, "config", "mpl_styles", "*"))
                  if os.path.isfile(p) and os.path.basename(p) != "README.md")
