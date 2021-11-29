.. Analyzing data (with aanalysis.py)

.. include:: ./tag_definition.rst

Data analysis and plotting with |enb|
=====================================

The :mod:`enb.aanalysis` module provides several classes to help you analyze
and plot your results:

* Classes in this module accept |DataFrame| instances, e.g., such as the ones
  produced by the `get_df` method of |ATable| and |Experiment|.

* You can easily import `*.csv` files into dataframes with the `pandas.read_csv` method,
  and use |enb| with externally produced data.

The analysis and plotting tools are presented in the following sections, each describing
a general use case.

If you have |enb| already installed, you can download all the test data and example code into the `ag` folder as with::

    enb install analysis-gallery ag


One numeric column
------------------

In this scenario, we want to analyze a column of scalar values, typically integers and floats.
Here we will be using the Iris dataset, which we can load with::

    import pandas as pd
    iris_df = pd.read_csv("./input_csv/iris_dataset.csv")

This particular dataframe has the `sepal_length`, `sepal_width`, `petal_length`, `petal_width` and `class` columns defined.
We can analyze the general petal and sepal dimensions using the **`get_df`** method of |ScalarNumericAnalyzer|


.. code-block:: python

    import enb
    analyzer = enb.aanalysis.ScalarNumericAnalyzer()
    analysis_df = analyzer.get_df(
        full_df=iris_df, target_columns=["sepal_length", "sepal_width",
                                         "petal_length", "petal_width"])

.. note::
    The target columns are selected with the **target_columns** parameter, which must be a list of
    column names present in the dataframe being analyzed.


This renders a basic plot with information about the distribution, the average, and the standard deviation of the samples,
as shown in the next figure. The returned `analysis_df` dataframe contains the exact values for the mean, standard deviations,
etc., for each target column.

.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer_sepal_width_histogram.png
    :width: 100%

Two numeric columns
-------------------

In this scenario, we want to compare two numeric columns, e.g., `sepal_width` and `petal_width`.
To do so, we need to use the |TwoNumericAnalyzer| class instead of the |ScalarNumericAnalyzer|
we employed in the previous examples.

These two, and all subclasses of |Analyzer| share a similar interface rotating around the `get_df`
method that analyzes and plots

.. code-block:: python

    two_numeric_analyzer = enb.aanalysis.TwoNumericAnalyzer()
    analysis_df = two_numeric_analyzer.get_df(
        full_df=iris_df, target_columns=[("sepal_width", "petal_length")],
        output_plot_dir=os.path.join(options.plot_dir, "scalar_numeric"),
    )

.. note::

    When using |TwoNumericAnalyzer|, the **target_columns** parameter must be a list of tuples, each
    containing two column names, e.g.: `("columnA", "columnB")`.


In addition to the `analysis_df` dataframe with numeric results, this will produce a scatter plot like the following,
which also shows +/- 1 horizontal and vertical standard deviations.

.. figure:: _static/analysis_gallery/TwoNumericAnalyzer_sepal_width,petal_length_scatter.png
    :width: 100%

Columns with dictionaries
-------------------------

The |enb| library allows storing dictionaries with scalar entries. For columns with numeric values (integer or float),
the |DictNumericAnalyzer| class can be used.

In the following example, the dataset
contains a column `mode_count` where keys are the set of possible modes and the values are the number of times
each mode has been employed. We can import the dataset with the following lines

.. code-block:: python

    hevc_df = pd.read_csv("./input_csv/hevc_frame_prediction.csv")
    ## These two lines are automatically applied
    ## by get_df of the appropriate experiment - they can be safely ignored
    hevc_df["mode_count"] = hevc_df["mode_count"].apply(
        ast.literal_eval)
    hevc_df["block_size"] = hevc_df["param_dict"].apply(
        lambda d: f"Block size {ast.literal_eval(d)['block_size']:02d}")

.. note::

    The two last lines transform the string representation of a dict stored in the `.csv` file into
    actual python dictionaries.

    When using a dataframe returned by `get_df` of |enb|, column values contain the actual dictionaries
    without needing to apply `ast` directly.

.. warning::

    If you obtained the dataframe being analyzed outside |enb|, you need to create a dictionary
    with |ColumnProperties| entries for each dictionary with something like this

    .. code-block:: python

        column_to_properties = dict(mode_count=enb.atable.ColumnProperties(
            name="mode_count",
            label="Mode index to selection count",
            has_dict_values=True))

    If you obtained it from within |enb|, your |ATable| or |Experiment| instances contain respectively
    the `column_to_properties` and `joined_column_to_properties` properties that can be used
    instead of the previous code. In this case, make sure that the `has_dict_values` is set to True in
    the corresponding column definition.


Now, we instantiate |DictNumericAnalyzer| and run its `get_df` method. The following code computes the average
count per mode for each of the selected groups (given in the `block_size` column)

.. code-block:: python

    # Create the analyzer and plot results
    numeric_dict_analyzer = enb.aanalysis.DictNumericAnalyzer()
    analysis_df = numeric_dict_analyzer.get_df(
        full_df=hevc_df,
        target_columns=["mode_count"],
        group_by="block_size",
        column_to_properties=column_to_properties,
        group_name_order=sorted(hevc_df["block_size"].unique()),

        # Rendering options
        x_tick_label_angle=90,
        fig_width=7.5,
        fig_height=5,
        secondary_alpha=0,
        global_y_label_pos=-0.1)

.. note::

    Some additional rendering options are included here to improve presentation.
    Rendering options are discussed in a later section.

The resulting figure is shown below

.. figure:: _static/analysis_gallery/DictNumericAnalyzer_mode_count_groupby-block_size_line.png
    :width: 100%


Grouping by a column's value
----------------------------

Often, we want to group the dataframe's rows based on the value of a given column, and then analyze others.

We achieve this by passing that the grouping column's name as the **group_by** keyword
when calling ScalarNumericAnalyzer's `get_df` method.

Continuing with the Iris experiment above, we can show results grouped by `class` (present in the original `.csv`)
as follows::

    analyzer = enb.aanalysis.ScalarNumericAnalyzer()
    analysis_df = analyzer.get_df(
        full_df=iris_df, target_columns=["sepal_length", "sepal_width",
                                         "petal_length", "petal_width"],
        group_by="class")

This would automatically produce an image like the following:

.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer_petal_width_groupby-class_histogram.png
    :width: 100%

Grouping is not restricted to |ScalarNumericAnalyzer|. It can be used with other |Analyzer| classes such as
|TwoNumericAnalyzer|, as in the following code


.. code-block:: python

    two_numeric_analyzer = enb.aanalysis.TwoNumericAnalyzer()
    analysis_df = two_numeric_analyzer.get_df(
        full_df=iris_df, target_columns=[("sepal_width", "petal_length")],
        group_by="class",
    )

The resulting scatter plot from this call is shown next:

.. figure:: _static/analysis_gallery/TwoNumericAnalyzer_sepal_width,petal_length_groupby-class_scatter.png


Grouping by task families
-------------------------

When |Experiment| is used to obtain dataframes of results, it is typical to have families
of tasks that were applied separately but are related. This can be used by defining a list
of |TaskFamily| instances and passing that argument to the `group_by` parameter of `get_df`.

For instance, for an input we might want to run algorithms A and B. Algorithm A is to be run with
two parameter configurations: A1 and A2, while algorithm B is to be run with configurations B1, B2, B3 and B4.
In this case, two families would be created, e.g., with labels "Algorithm A" and "Algorithm B",
with 2 and 4 tasks in them.

In the following figure, an example with 6 algorithms, each with different configurations
that affect their "Compressed data rate". Please see the :doc:`image_compression` page for a full
experiment that uses task families and produces plots like the one in the figure.

.. figure:: _static/analysis_gallery/TwoNumericAnalyzer_bpppc__psnr_dr_groupby-family_label_line.png