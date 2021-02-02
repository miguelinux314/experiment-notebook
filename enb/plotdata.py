#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utils to plot data (thinking about pyplot)
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "10/09/2019"

import numpy as np
import collections
import matplotlib

matplotlib.use('Agg')
from matplotlib import pyplot as plt


class PlottableData:
    alpha = 0.75
    legend_column_count = 1

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
            x_values, y_values = zip(*found_pairs.values())

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
    def render(self, axes=None):
        """Plot 2D data using plt.plot()

        :param axes: if not None, those axes are used for plotting instead of plt
        """
        axes.plot(self.x_values, self.y_values, label=self.label, alpha=self.alpha,
                  **self.extra_kwargs)
        axes = plt if axes is None else axes
        self.render_axis_labels(axes=axes)
        if self.label is not None and self.legend_column_count != 0:
            plt.legend(loc="lower center", bbox_to_anchor=(0.5, 1),
                       ncol=self.legend_column_count)


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
                 alpha=None,
                 marker_size=None, cap_size=None, vertical=False,
                 line_width=None, *args, **kwargs):
        """
        :param x_values, y_values: centers of the error lines
        :param err_neg_values: list of lengths for the negative part of the error
        :param err_pos_values: list of lengths for the positive part of the error
        :param vertical: determines whether the error bars are vertical or horizontal
        """
        super().__init__(x_values=x_values, y_values=y_values, *args, **kwargs)
        self.err_neg = err_neg_values
        self.err_pos = err_pos_values
        self.cap_size = cap_size if cap_size is not None else self.cap_size
        self.marker_size = marker_size if marker_size is not None else self.marker_size
        self.line_width = line_width if line_width is not None else self.line_width
        self.vertical = vertical
        if alpha is not None:
            self.alpha = alpha
        assert len(self.x_values) == len(self.y_values)
        assert len(self.x_values) == len(self.err_pos)

    def render(self, axes=None):
        axes = plt if axes is None else axes
        err_argument = np.concatenate((
            np.array(self.err_neg).reshape(1, len(self.err_neg)),
            np.array(self.err_pos).reshape(1, len(self.err_pos))),
            axis=0)
        err_argument = err_argument[:, :len(self.x_values)]
        if self.vertical:
            axes.errorbar(self.x_values, self.y_values, yerr=err_argument,
                          fmt="-o", capsize=self.cap_size, capthick=0.5, lw=0, elinewidth=self.line_width, ms=self.marker_size,
                          alpha=self.alpha,
                          **self.extra_kwargs)
        else:
            axes.errorbar(self.x_values, self.y_values, xerr=err_argument,
                          fmt="-o", capsize=self.cap_size, capthick=0.5, lw=0, elinewidth=self.line_width, ms=self.marker_size,
                          alpha=self.alpha,
                          **self.extra_kwargs)

        assert len(self.x_values) == len(self.y_values)
