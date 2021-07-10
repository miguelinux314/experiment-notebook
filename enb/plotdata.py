#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utils to plot data (thinking about pyplot)
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "10/09/2019"

import numpy as np
import collections
import matplotlib
from scipy.stats import norm

matplotlib.use('Agg')
from matplotlib import pyplot as plt


class PlottableData:
    alpha = 0.75
    legend_column_count = 1
    color = None

    def __init__(self, data=None, axis_labels=None, label=None,
                 extra_kwargs=None, alpha=None, legend_column_count=None):
        self.data = data
        self.axis_labels = axis_labels
        self.label = label
        self.extra_kwargs = extra_kwargs if extra_kwargs is not None else {}
        self.alpha = alpha if alpha is not None else self.alpha
        self.legend_column_count = legend_column_count if legend_column_count is not None else self.legend_column_count

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

    def __repr__(self):
        return f"{self.__class__.__name__}(color={repr(self.color)})"


class PlottableData2D(PlottableData):
    """Plot 2D data using plt.plot()
    """

    def __init__(self, x_values, y_values,
                 x_label=None, y_label=None,
                 label=None, extra_kwargs=None,
                 remove_duplicates=True,
                 alpha=None, legend_column_count=None):
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
                         legend_column_count=legend_column_count)
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

    def diff(self, other, ylabel_affix=" difference"):
        assert len(self.x_values) == len(other.x_values)
        assert len(self.y_values) == len(other.y_values)
        assert all(s == o for s, o in zip(self.x_values, other.x_values))
        return PlottableData2D(x_values=self.x_values,
                               y_values=[s - o for s, o in zip(self.y_values, other.y_values)],
                               x_label=self.x_label,
                               y_label=f"{self.y_label}{ylabel_affix}",
                               legend_column_count=self.legend_column_count)

    def shift_y(self, constant):
        self.y_values = [y + constant for y in self.y_values]

    def shift_x(self, constant):
        self.y_values = [y + constant for y in self.y_values]


class LineData(PlottableData2D):
    marker_size = 5

    def __init__(self, marker_size=None, **kwargs):
        self.marker_size = marker_size if marker_size is not None else self.marker_size
        super().__init__(**kwargs)

    def render(self, axes=None):
        """Plot 2D data using plt.plot()

        :param axes: if not None, those axes are used for plotting instead of plt
        """
        try:
            original_kwargs = self.extra_kwargs
            extra_kwargs = dict(self.extra_kwargs)

            try:
                marker = extra_kwargs["marker"]
                del extra_kwargs["marker"]
            except KeyError:
                marker = "o"

            try:
                ms = extra_kwargs["ms"]
                del extra_kwargs["ms"]
            except KeyError:
                ms = self.marker_size

            axes.plot(self.x_values, self.y_values, label=self.label, alpha=self.alpha,
                      marker=marker,
                      ms=ms,
                      **extra_kwargs)
            axes = plt if axes is None else axes
            self.render_axis_labels(axes=axes)
            if self.label is not None and self.legend_column_count != 0:
                plt.legend(loc="lower center", bbox_to_anchor=(0.5, 1),
                           ncol=self.legend_column_count)
        finally:
            self.extra_kwargs = original_kwargs


class ScatterData(PlottableData2D):
    alpha = 0.5
    marker_size = 3

    def render(self, axes=None):
        axes = plt if axes is None else axes
        self.extra_kwargs["s"] = self.marker_size
        axes.scatter(self.x_values, self.y_values, label=self.label, alpha=self.alpha,
                     **self.extra_kwargs)
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            axes.legend(loc="lower center", bbox_to_anchor=(0.5, 1),
                        ncol=self.legend_column_count)


class BarData(PlottableData2D):
    marker_size = 1

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.bar(self.x_values, self.y_values, label=self.label, alpha=self.alpha,
                 **self.extra_kwargs)
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            axes.legend(loc="lower center", bbox_to_anchor=(0.5, 1),
                        ncol=self.legend_column_count)

    def shift_y(self, constant):
        try:
            self.extra_kwargs["bottom"] += constant
        except KeyError:
            self.extra_kwargs["bottom"] = constant
        except AttributeError:
            self.extra_kwargs = dict(bottom=constant)


class StepData(PlottableData2D):
    where = "post"

    def render(self, axes=None):
        axes = plt if axes is None else axes
        axes.step(self.x_values, self.y_values, label=self.label, alpha=self.alpha,
                  where=self.where, **self.extra_kwargs)
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            plt.legend(loc="lower center", bbox_to_anchor=(0.5, 1),
                       ncol=self.legend_column_count)


class ErrorLines(PlottableData2D):
    """One or more error lines    
    """
    marker_size = 1
    cap_size = 3
    line_width = 1
    alpha = 0.5

    def __init__(self, x_values, y_values, err_neg_values, err_pos_values,
                 alpha=None, color=None,
                 marker_size=None, cap_size=None, vertical=False,
                 line_width=None, *args, **kwargs):
        """
        :param x_values, y_values: centers of the error lines
        :param err_neg_values: list of lengths for the negative part of the error
        :param err_pos_values: list of lengths for the positive part of the error
        :param vertical: determines whether the error bars are vertical or horizontal
        """
        super().__init__(x_values=x_values, y_values=y_values, remove_duplicates=False, *args, **kwargs)
        self.err_neg = err_neg_values
        self.err_pos = err_pos_values
        self.cap_size = cap_size if cap_size is not None else self.cap_size
        self.marker_size = marker_size if marker_size is not None else self.marker_size
        self.line_width = line_width if line_width is not None else self.line_width
        self.vertical = vertical
        self.color = color
        if alpha is not None:
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
        err_argument = err_argument[:, :len(self.x_values)]

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

        assert len(self.x_values) == len(self.y_values)


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
                for x, y, pos_height, neg_height in zip(band_x_values, band_y_values, pos_height_values, neg_height_values):
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
                       ncol=self.legend_column_count)
