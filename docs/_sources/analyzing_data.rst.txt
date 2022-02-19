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
Here we will be using the Iris dataset, which we can load with:

.. code-block:: python

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

The following render modes are available for the ScalarNumericAnalyzer (they are all rendered by default):

.. program-output:: python -c 'import enb; print("- " + "\n- ".join(enb.aanalysis.ScalarNumericAnalyzer.valid_render_modes))' | tail -n+4
    :shell:

The `histogram` mode  renders a basic plot with information about the distribution, the average, and the standard deviation of the samples,
as shown in the next figure. The returned `analysis_df` dataframe contains the exact values for the mean, standard deviations,
etc., for each target column.

.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer_sepal_width_groupby-None_histogram.png
    :width: 100%

The `hbar` and `boxplot` modes are most useful when 
grouping -- examples are provided below in the first section about grouping below.

.. note:: The |ScalarNumericAnalyzer| and most |Analyzer| subclasses can store
  a CSV with data statistics (e.g., min, max, median, mean, standard deviation) of the 
  columns of interest. By default, they can saved in the `enb.config.options.analysis_dir`
  folder when `get_df` is called.
  


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

.. figure:: _static/analysis_gallery/TwoNumericAnalyzer_sepal_width__petal_length_groupby-None_scatter.png
    :width: 100%

The previous figure shows an example of the `scatter` plot mode. 
The following render modes are available for the TwoNumericAnalyzer (they are all rendered by default):

.. program-output:: python -c 'import enb; print("- " + "\n- ".join(enb.aanalysis.TwoNumericAnalyzer.valid_render_modes))' | tail -n+4
    :shell:

Examples are provided below in the first section about grouping data, where some of these modes are most useful. 

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
    
    import enb
    
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

.. _grouping_by_value:

Analysis numeric spatial (2D) data
----------------------------------

The |ScalarNumeric2DAnalyzer| class allows to plot data arranged arbitrarily in the x-y plane.

You will need:
    - a column with scalar data (integers or float entries), e.g., `column_data`
    - two more columns specifying the `x` and `y` coordinates of each datapoint, e.g., `column_x` and `column_y`.

You can then invoke the `get_df` method like any other |Analyzer| subclass, with the `target_columns` argument
being a list of 3-element tuples.

In the following example of the 'colormap' rendermode, 
the `value` column contains the data of interest, while `x` and `y` contain the spatial 
information.

.. code-block:: python

    import enb
    
    # Read data from CSV - could be obtained from an ATable instance
    df_2d = pd.read_csv(os.path.join("input_csv", "2d_data_example.csv"))
    
    # Perform analysis 
    sn2da = enb.aanalysis.ScalarNumeric2DAnalyzer()
    sn2da.bin_count = 10
    sn2da.get_df(full_df=df_2d,
                 target_columns=[("x", "y", "value")],
                 column_to_properties={
                                "value": enb.atable.ColumnProperties("value", label="Result of $f(x,y)$"),
                                "x": enb.atable.ColumnProperties("x", label="Offset in the $x$ axis"),
                                "y": enb.atable.ColumnProperties("y", label="Offset in the $y$ axis")})


The resulting figure is shown in the following figure:

.. figure:: _static/analysis_gallery/ScalarNumeric2DAnalyzer-columns_x__y__fx-colormap.png
    :width: 100%

.. note:: You can configure the employed colormap by modifying your |ScalarNumeric2DAnalyzer| instance attributes,
    e.g., you can set `color_map` to any color map name accepted by matplotlib, e.g.,

    .. code-block:: python

        sn2da = enb.aanalysis.ScalarNumeric2DAnalyzer()
        sn2da.color_map = "Oranges"


    See https://matplotlib.org/stable/gallery/color/colormap_reference.html for more information about available
    colormaps.


Grouping by a column's value
----------------------------

Grouping with ScalarNumericAnalysis
___________________________________

Often, we want to group the dataframe's rows based on the value of a given column, and then analyze others.

We achieve this by passing that the grouping column's name as the **group_by** keyword
when calling ScalarNumericAnalyzer's `get_df` method.

Continuing with the Iris experiment above, we can show results grouped by `class` (present in the original `.csv`)
as follows:

.. code-block:: python

    analyzer = enb.aanalysis.ScalarNumericAnalyzer()
    analysis_df = analyzer.get_df(
        full_df=iris_df,
        target_columns=["sepal_length", "sepal_width",
                         "petal_length", "petal_width"],
        group_by="class")

By default, all of the following render modes are used with |ScalarNumericAnalyzer|:

.. program-output:: python -c 'import enb; print("- " + "\n- ".join(enb.aanalysis.ScalarNumericAnalyzer.valid_render_modes))' | tail -n+4
    :shell:

The `histogram` render mode produces plots like the following:

.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer_petal_width_groupby-class_histogram.png
    :width: 100%


The `hbar` render mode produces horizontal bar plots with length equal to the average, as shown in the 
following image:

.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer-petal_width-hbar-groupby__class.png
    :width: 100%

The `boxplot` render mode produces standard box plots where lines span the entire input data range,
the vertical lines in the box plot indicates quartiles Q1, Q2 and Q3, and the mean value is also displayed,
as shown next:

.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer-petal_length-boxplot-groupby__class.png
    :width: 100%

Grouping with other Analyzer subclasses
_______________________________________

Grouping is not restricted to |ScalarNumericAnalyzer|. It can be used with other |Analyzer| classes such as
|TwoNumericAnalyzer|, as in the following code:

.. code-block:: python

    two_numeric_analyzer = enb.aanalysis.TwoNumericAnalyzer()
    analysis_df = two_numeric_analyzer.get_df(
        full_df=iris_df, target_columns=[("sepal_width", "petal_length")],
        group_by="class",
    )

By default, all of the following render modes are used with |TwoNumericAnalyzer|:

.. program-output:: python -c 'import enb; print("- " + "\n- ".join(enb.aanalysis.TwoNumericAnalyzer.valid_render_modes))' | tail -n+4
    :shell:

The resulting plot for the `scatter` mode is shown next:

.. figure:: _static/analysis_gallery/TwoNumericAnalyzer_sepal_width__petal_length_groupby-class_scatter.png

The resulting plot for the `line` mode is shown next:

.. figure:: _static/analysis_gallery/TwoNumericAnalyzer-sepal_width__vs__petal_length-line-groupby__class.png


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

.. figure:: _static/lossy_experiment/TwoNumericAnalyzer_bpppc__psnr_dr_groupby-family_label_line.png

Combining groups
----------------

The `combine_groups` argument can be passed to get_df or set in the |ScalarNumericAnalyzer| instance.
If selected, all groups are shown in the same subplot. In this case, the average and standard deviation
values are automatically removed for clarity. An example of this output can be found next:

.. code-block:: python

    enb.aanalysis.ScalarNumericAnalyzer().get_df(
        full_df=iris_df,
        target_columns=["sepal_length", "sepal_width",
                        "petal_length", "petal_width"],
        group_by="class",
        output_plot_dir=os.path.join(
            options.plot_dir, "scalar_combined_groups"),
        legend_column_count=3,
        combine_groups=True,
    )


.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer-petal_length-histogram-groupby__class__combine_groups.png

|

Groups are automatically combined for |TwoNumericAnalyzer|, but are optional for |DictNumericAnalyzer|.
An example is provided next:

.. figure:: _static/analysis_gallery/DictNumericAnalyzer-mode_count-line-groupby__block_size__combine_groups.png

Making baseline comparisons
---------------------------

When grouping is used, it is possible to select one of the groups as baseline and then perform
analysis and plotting on the differences against that baseline.

For the |Analyzer| subclasses and render modes that support it, it suffices to pass
`reference_group="group name"` when calling `get_df`. Here, `"group name"` is one
of the group labels derived from the `group_by` selection.

Example with |ScalarNumericAnalyzer|
____________________________________

The following snippet shows how to use the |ScalarNumericAnalyzer| to show differences against a group.

.. code-block:: python

    iris_df = pd.read_csv("./input_csv/iris_dataset.csv")
    scalar_analyzer = enb.aanalysis.ScalarNumericAnalyzer()
    analysis_df = scalar_analyzer.get_df(
        full_df=iris_df, target_columns=["sepal_length", "sepal_width", "petal_length", "petal_width"],
        group_by="class",
        reference_group="Iris-versicolor",
        output_plot_dir=os.path.join(options.plot_dir, "scalar_numeric_reference"))

The resulting plot is shown in the next figure.

.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer-sepal_width-histogram-groupby__class-referencegroup__Iris-versicolor.png

You can choose whether the group used as baseline is employed or not, by setting your
analyzer instance's `show_reference_group` attribute, i.e.,

.. code-block:: python

    scalar_analyzer.show_reference_group = False

before calling `get_df`.

Note that you can combine `reference_group` and `combine_groups` if you want. An example
where both options are used is shown next:

.. code-block:: python

    scalar_analyzer.show_reference_group = False
    scalar_analyzer.get_df(
        full_df=iris_df,
        target_columns=["sepal_length", "sepal_width", "petal_length", "petal_width"],
        group_by="class",
        output_plot_dir=os.path.join(options.plot_dir, "scalar_combined_reference"),
        combine_groups=True,
        legend_column_count=3,
        reference_group="Iris-versicolor",
    )

.. figure:: _static/analysis_gallery/ScalarNumericAnalyzer-petal_length-histogram-groupby__class-referencegroup__Iris-versicolor__combine_groups.png

Example with |TwoNumericAnalyzer|
_________________________________

The |TwoNumericAnalyzer| class has a similar sintax as |ScalarNumericAnalyzer|.
Both the `line` and `scatter` render modes are available. If none is selected,
both are employed.

.. code-block:: python

    two_numeric_analyzer = enb.aanalysis.TwoNumericAnalyzer()
    analysis_df = two_numeric_analyzer.get_df(
        full_df=iris_df, target_columns=[("sepal_width", "petal_length")],
        output_plot_dir=os.path.join(options.plot_dir, "two_numeric_reference"),
        group_by="class", reference_group="Iris-versicolor",
    )

The plots resulting from the above snippet are shown next.

.. figure:: _static/analysis_gallery/TwoNumericAnalyzer-sepal_width__vs__petal_length-scatter-groupby__class-referencegroup__Iris-versicolor.png

.. figure:: _static/analysis_gallery/TwoNumericAnalyzer-sepal_width__vs__petal_length-line-groupby__class-referencegroup__Iris-versicolor.png


Customizing plot appearance
---------------------------

If the default plot appearance does not suit you (axis limits, font size, color scheme, logarithmic scale, etc.),
`enb` offers several ways of customizing them, described in the following subsections.

Choosing a plot type
____________________

You can change the type of plot by selecting one of the available |Analyzer| classes.
See above for examples on all available classes.

Some analyzers provide several render modes. You can select one or more of them by
passing the `selected_render_modes` argument to your `get_df` calls. 
By default, all render modes in an |Analyzer| are used.

Modifying your Analyzers
________________________

The |Analyzer| classes themselves have several attributes that affect the way they
produce plots. Some examples common to all |Analyzer| instances are as follows.

.. code-block:: text

        # Main title to be displayed
        plot_title = None
        # Show the number of elements in each group?
        show_count = True
        # Show a group containing all elements?
        show_global = False
        # If a reference group is used as baseline, should it be shown in the analysis itself?
        show_reference_group = True
        # If applicable, show a horizontal +/- 1 standard deviation bar centered on the average
        show_x_std = False
        # If applicable, show a vertical +/- 1 standard deviation bar centered on the average
        show_y_std = False
        # Main marker size
        main_marker_size = 4
        # Secondary (e.g., individual data) marker size
        secondary_marker_size = 2
        # Main plot element alpha
        main_alpha = 0.5
        # Secondary plot element alpha (often overlaps with data using main_alpha)
        secondary_alpha = 0.5
        # If a semilog y axis is used, y_min will be at least this large to avoid math domain errors
        semilog_y_min_bound = 1e-5
        # Thickness of the main plot lines
        main_line_width = 2
        # Thickness of secondary plot lines
        secondary_line_width = 1
        # Margin between group rows (if there is more than one)
        group_row_margin = 0.2
        # If more than one group is displayed, when applicable, adjust plots to use the same scale in every subplot?
        common_group_scale = True
        # If more than one group is present, they are shown in the same subplot
        # instead of in different rows
        combine_groups = False
        # If True, display group legends when applicable
        show_legend = True



Default values for these attributes can be set by placing a file with `.ini` extension
in your project root (where your scripts are placed). This file should contain a subset
of the attributes defined in the 
`full enb.ini configuration file <https://github.com/miguelinux314/experiment-notebook/blob/dev/enb/config/enb.ini>`_.

.. note:: Attributes must be stored in sections with name given by the |Analyzer| class, e.g.,
    `'[enb.aanalysis.Analyzer]'` or `'[enb.aanalysis.ScalarNumericAnalyzer]'`.


You can install a copy of the full configuration file and then modify it as needed with:

    .. code-block:: bash

        enb plugin install enb.ini ./your_project_folder/

Once an |Analyzer| has been instantiated, its attributes can be modified like any other object.
Attribute values are independently read for each call to `get_df`.


.. _column_hints:

Setting column plotting hints
_____________________________
   
All columns defined in |ATable| subclasses (including |Experiment| subclasses) 
have a corresponding |ColumnProperties| instance. 

These instances contain rendering hints when plotting that column such as:

- axis labels (e.g., `label='Average duration (s)'`)
- plot limits (e.g., `plot_min=0`, `plot_max=60`, which can also be set to None for automatic limits) 
- axis type (e.g., `semilog_x=True`)

As detailed in :doc:`basic_workflow`, these hints can be set when defining custom columns, e.g.,

.. code-block:: python

    class MyTable(enb.atable.ATable):
        @enb.atable.column_function(enb.atable.ColumnProperties(
            name="average_duration_seconds",
            label="Average duration (s)",
            plot_min=0,
            plot_max=60))
        def set_average_duration_seconds(self, file_path, row):
            row[_column_name] = # ... your code here
    
One can then pass the `column_to_properties` argument to an Analyzer's `get_df` method, e.g.,

.. code-block:: python

    mt = MyTable()
    df = # ... e.g., mt.get_df(), see examples above  
    enb.aanalysis.ScalarNumericAnalyzer().get_df(
        full_df=df, 
        column_to_properties=mt.column_to_properties)
        
See :meth:`enb.atable.ColumnProperties.__init__` for full details on all available attributes.
        
.. note:: 

    * You can modify |ColumnProperties| instances after they have been associated to a column, e.g.,
      
      .. code-block:: python
         
         mt.column_properties["average_duration_seconds"].plot_max = 30
      
      
    * You can create your own dictionary indexed by column name, containing |ColumnProperties| instances,
      and then pass it to `get_df`, e.g.,:

      .. code-block:: python
         
         enb.aanalysis.ScalarNumericAnalyzer().get_df(
            full_df=df, 
            column_to_properties=dict(average_duration_seconds=enb.atable.ColumnProperties(
                plot_min=0, plot_max=30, label=r"$\Gamma$ routine execution time (seconds)")))
      
      

    * |Experiment| subclasses also offer the `joined_column_to_properties` property, which
       contains the columns defined in that experiment, and in the |ATable| subclass employed
       for the dataset (see :doc:`experiments` for more information about experiments), e.g.:

      .. code-block:: python
            
            # Initialize and run experiment 
            exp = MyExperimentClass()
            df = exp.get_df()
            
            # Analyze results
            scalar_columns = ["column_A", "column_B"]
            scalar_analyzer = enb.aanalysis.ScalarNumericAnalyzer()
            scalar_analyzer.get_df(
                full_df=df,  target_columns=scalar_columns,
                group_by="task_label",  selected_render_modes={"histogram"},
                
                # Experiments offer the `joined_column_to_properties` property
                column_to_properties=exp.joined_column_to_properties,
            )

.. _kwargs:

Setting `**render_kwargs` when calling `Analyzer.get_df`
________________________________________________________

The `get_df` method of all |Analyzer| subclasses accept a `**render_kwargs` parameter.

.. note:: Values passed in this parameter overwrite those defined in `column_properties`.

You can add one or more `key=value` arguments to the `get_df` call, as shown in the following example.

.. code-block:: python

    numeric_dict_analyzer = enb.aanalysis.DictNumericAnalyzer()
    hevc_df = pd.read_csv("./input_csv/hevc_frame_prediction.csv") 
    numeric_dict_analyzer.secondary_alpha = 0
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
        global_y_label_pos=-0.01)

Here, the labels of the x ticks are rotated 90 degrees, the figure dimensions are changed, and the global y
axis label is moved to account for very long y-axis labels.

Please refer to :meth:`enb.plotdata.render_plds_by_group` for a list of all available parameters.
Note that the `pds_by_group_name` parameter and others are automatically set by your choice of |Analyzer| subclass.

.. _styles:

Using styles
____________

The `enb` library employs `matplotlib` for plotting. 
Matplotlib's `styling features <https://matplotlib.org/stable/tutorials/introductory/customizing.html>`_
are available in two ways:

1. You can set the `style_list` attribute of your |Analyzer| subclass (default value or instance attribute).

2. You can pass the `style_list` argument to the call to `get_df` of your |Analyzer| subclass.

For instance, to set Matlplotlib's dark style, the following code can be used:

.. code-block:: python

    ## Option 1: modify analyzer instance
    scalar_analyzer = enb.aanalysis.ScalarNumericAnalyzer()
    scalar_analyzer.style_list = ["dark_background"]
    analysis_df = scalar_analyzer.get_df(
        full_df=iris_df, target_columns=["sepal_length", "sepal_width", "petal_length", "petal_width"],
        output_plot_dir=os.path.join(options.plot_dir, "scalar_numeric_dark", "instance"),
        group_by="class")
    
    ## Option 2: use get_df's **kwargs
    scalar_analyzer = enb.aanalysis.ScalarNumericAnalyzer()
    analysis_df = scalar_analyzer.get_df(
        full_df=iris_df, target_columns=["sepal_length", "sepal_width", "petal_length", "petal_width"],
        output_plot_dir=os.path.join(options.plot_dir, "scalar_numeric_dark", "kwargs"),
        group_by="class",
        style_list=["dark_background"])

Each element in `style_list` must be one of the following:

* One of Matplotlib's style names (e.g., `"dark_background", "bmh", etc) configured in your machine.
  You can check out the `gallery of matplotlib's default styles <https://matplotlib.org/stable/gallery/style_sheets/style_sheets_reference.html>`_.

* One of enb's predefined style names.

  .. note:: You can get a list of all available style names from the CLI with
        
      .. code-block:: bash 
            
            enb show styles

      or within python with 

      .. code-block:: python
        
            enb.plotdata.get_available_styles()
            
      An example output is as follows:

        .. program-output:: enb show styles | tail -n+3
            :shell:

* The path of a matplotlib rc style. 

  See `matplotlib's rc file documentation <https://matplotlib.org/stable/tutorials/introductory/customizing.html#the-matplotlibrc-file>`_
  for more information on how to create and modify this type of files.

  You can install an editable copy of Matplotlib's default rc file with:

    .. code-block:: bash

        enb plugin install matplotlibrc .

.. note:: You can select any number of styles for your plots.
    When a list of styles is used for a plot, its elements are processed from left to right.
    Therefore, you can compose themes just like one would in 
    Matplotlib `<https://matplotlib.org/stable/tutorials/introductory/customizing.html#composing-styles>`_.

.. warning:: Not all styles are necessarily intended for professional usage (-:

    .. figure:: _static/analysis_gallery/ScalarNumericAnalyzer-petal_length-histogram-groupby__class__xkcd.png