Analyzer gallery
----------------

All figures are produced by the code example in the
`templates/analysis_gallery_example/generate_gallery.py <https://github.com/miguelinux314/experiment-notebook/blob/master/templates/analysis_gallery_example/generate_gallery.py>`_ script.

Please refer to the :doc:`api` or the `source code <https://github.com/miguelinux314/experiment-notebook>`_
for full details on all Analyzer subclasses.

Scalar data analysis
********************

The :class:`enb.aanalysis.ScalarDistributionAnalyzer` class produces one or more histograms, stacked along the y axis.
Each histogram contains a marker for the average value, and a bar for +/- 1 standard deviation.

The following example shows the distribution of sepal lengths by Iris class:

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/master/templates/analysis_gallery_example/png_plots/groupby_class/ScalarDistributionAnalyzer/distribution_sepal_length.png

**Interesting parameters** to the `analyze_df()` method:

* `group_by`: useful to stack more than one histogram, by dividing the data frame based on the value of a column.
  `group_by="class"` was used to generate the image above.

* `show_global`: controls wether results for the whole dataset (not split by group_by) is to be shown along the
  subgroups.

* `adjust_height`: if True, the histograms are all scaled so that the maximum relative frequency reaches the top
  of its plot. If False, histograms are not scaled.


Two columns: 2D Scatter
***********************

A 2D scatter of plots can be used to analyze two columns jointly.

The :class:`enb.aanalysis.TwoColumnScatterAnalyzer` class produces a single scatter plot given two target
columns as an input.

The following example shows the distribution of two columns of the set.

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/master/templates/analysis_gallery_example/png_plots/groupby_class/TwoColumnScatterAnalyzer/twocolumns_scatter_sepal_length_VS_petal_width.png

**Interesting parameters** to the :meth:`enb.aanalysis.TwoColumnScatterAnalyzer.analyze_df()` method:

* `group_by`: It allows distinguishing data points based on the value of the given column.
  Different colors and markers are automatically and consistently used.

* `show_individual`: When True, all data points are shown. When False, only the average values
  of each class is shown.

Two columns and one parameter: line plot
****************************************

Often, we want to analyze the behavior of a method that accepts one or more parameters.
The goal is to jointly analyze two data columns, combining
together data for each parameter value.

For instance, the JPEG-LS compressor accepts the peak absolute error (PAE) as a parameter.
It is very natural to group JPEG-LS results for different PAE parameters, as in the figure below.

.. note:: For each family member (i.e., all compression results for one compressor configuration),
  multiple results will typically be present (one per element of the input dataset).
  This **analyzer obtains the average** within each column being considered **for that specific configuration**.

.. image:: https://raw.githubusercontent.com/miguelinux314/experiment-notebook/master/templates/analysis_gallery_example/png_plots/plot_line_bpppc_pae.png

**Interesting parameters** to the :meth:`enb.aanalysis.TwoColumnLineAnalyzer.analyze_df()` method:

* `group_by`: instead of column names, this argument must be a list of :class:`enb.aanalysis.TaskFamily` instances.
  The following example taken from `this lossy compression example<https://github.com/miguelinux314/experiment-notebook/blob/master/templates/lossy_compression_experiment/lossy_compression_experiment.py>`
  shows how to define a list of task families that can be used as the `group_by` argument:

  .. code-block:: python

    all_codecs = []
    all_families = []
    # A family is a set of related tasks
    jpeg_ls_family = enb.aanalysis.TaskFamily(label="JPEG-LS")
    for c in (plugin_jpeg.jpeg_codecs.JPEG_LS(max_error=m) for m in range(5)):
        all_codecs.append(c)
        jpeg_ls_family.add_task_name(c.name)
    all_families.append(jpeg_ls_family)


* `show_markers`: a boolean controlling whether data points are made explicit with a marker. If False,
  a plain line is typically shown.

* `show_v_range_bar`, `show_h_range_bar`: if True, vertical or horizontal bars will be added to each data point
  to signal the full span of your data

* `show_v_std_bar`, `show_h_std_bar`: if True, vertical or horizontal bars will be added to each data point
  to signal plus/minus 1 standard deviation
