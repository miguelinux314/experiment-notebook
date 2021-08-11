.. Using enb.aanalysis.Analyzer subclasses

Using Analyzer subclasses
-------------------------
This module defines several classes derived from :class:`enb.aanalysis.Analyzer`.


a minimal working example of :mod:`enb.aanalysis` is provided in :doc:`basic_workflow`
,
which produce their results by invoking the :meth:`enb.aanalysis.Analyzer.analyze_df` method.
The main inputs to these subclasses' methods are:

  * `full_df`: a :class:`pandas.DataFrame` instance, typically produced by :class:`enb.atable.ATable`.

  * `target_columns`: normally a list of column names (or pairs of column names) present in the DataFrame.
    These are the ones for which figures are produced. Syntax can vary between analyzer classes.


  * `column_to_properties`: although optional, this argument (a dict-like instance) provides information
    to the analyzer about how to display the results. Good news is, your :class:`enb.atable.ATable` instance
    automatically contains  this dict-like object in the `.column_to_properties`.

    For instance, the folowing column definition guarantees that
    the default plot range for this dimension starts in zero:

    .. code-block:: python

       @atable.column_function("bpppc", label="Compressed data rate (bpppc)", plot_min=0)
            def set_bpppc(self, index, row):
                # _column_name equals "bpppc", or whatever label is passed to @atable.column_function
                row[_column_name] = ...


    In addition, subclasses of :class:`enb.experiment.Experiment`
    also provide the `.joined_column_to_properties` property. This is convenient when cross-analyzing
    the properties of your dataset with the results you obtained (e.g., to measure relative efficiency).
    See :doc:`lossless_compression_example` for a full working example of data analysis using an experiment.

  * `group_by`: a column name is typically used by the analyzer to split all data in `full_df` into subgroups
    based on the value of one or more columns.