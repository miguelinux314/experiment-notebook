.. Description of the paradigm and general structure of enb

Basic workflow
==============

This page explains the basic workflow with ``enb`` with a `simple example <./_static/example_basic_workflow.zip>`_. 
You can find the lastest version of this example at the 
`templates/basic_workflow <https://github.com/miguelinux314/experiment-notebook/tree/master/templates/basic_workflow_example>`_ 
folder of the project.

.. figure:: img/general_structure.png
    :width: 100%
    :alt: Basic steps when using ``enb``
    :align: center

    Basic steps when using ``enb``.


The basic workflow when using ``enb`` can be summarized in three key steps:

**1 - Data curation**
---------------------

The first step is to gather and curate your data samples.
It should be possible to obtain individual results for each data sample.
For instance, if you work in image processing, each sample could be one
of your test images, if you work with genetic sequences, each file could
be one sequence, etc.

    .. note::
       It is best practice to separate data samples from
       test parameters (e.g., arguments to the algorithm(s) used to process
       each of your samples.


In this basic example, each sample is the source of a Wikipedia article::

    data/wiki/:
    a_turing.txt
    c_shannon.txt
    d_knuth.txt
    k_popper.txt
    m_curie.txt
    n_chomsky.txt
    r_franklin.txt
    s_beauvoir.txt
    scientific_method.txt

One can gather all such input samples with a single line:

.. code-block:: python

  sample_paths = glob.glob("./data/wiki/*.txt")


**2 - Result column definition**
--------------------------------

The second step consists in defining the function(s) that produce the desired results.
The easiest way is to extend the :class:`enb.atable.ATable` class, like for example

.. code-block:: python

       class WikiAnalysis(enb.atable.ATable):
        @enb.atable.column_function("line_count")
        def set_line_count(self, file_path, row):
            with open(file_path, "r") as input_file:
                row["line_count"] = sum(1 for line in input_file)

In general, this can be done in two simple steps:

  * Define a method ``f`` with interface ``f(self, file_path, row)``. The ``file_path``
    argument is the path to one test sample (e.g., ``./data/wiki/s_beauvoir.txt``.
    The ``row`` argument is a dict-like instance, into which the desired result (for this input sample)
    is to be stored.

  * Decorate the method with ``@enb.atable.column_function(column_name)``, where
    ``column_name`` is a unique name that identifies the result produced by the method.


Once data are available and our :class:`enb.atable.ATable` subclass is defined,
a :class:`pandas.DataFrame` instance containing results can be obtained as follows:

.. code-block:: python

   table = WikiAnalysis(csv_support_path="persistence_basic_workflow.csv")
   result_df = table.get_df(target_indices=sample_paths)

.. note::

 The ``csv_support_path`` argument is the file used to store the `raw results <_static/persistence_basic_workflow.csv>`_.
 This avoids re-running the ``@enb.atable.column_function``-decorated functions more than once.


**3 - Data reporting**
----------------------

Produced results are made available as :class:`pandas.DataFrame` instances.
The ``enb`` library provides a few automatic tools to analyze and report
one or more data columns. You can find gallery of plotting and analysis tools available in `enb`
in the :doc:`analyzer_gallery`.

The most basic automatic analyzer is :class:`enb.aanalysis.ScalarDistributionAnalyzer`.
It produces an histogram of the values of a given data column, and shows average and
standard deviation on top.
In our example, to see the distribution of line counts over the test samples,
the following code can be used:

.. code-block:: python

  scalar_analyzer = enb.aanalysis.ScalarDistributionAnalyzer()
  scalar_analyzer.analyze_df(
    full_df=result_df,
    target_columns=["line_count"],
    output_plot_dir="plots",
    output_csv_file="analysis/line_count_analysis.csv")

You can download here `the resulting figure <_static/distribution_line_count.pdf>`_.

.. note::

  * ``full_df`` is the :class:`pandas.DataFrame` instance produced by :class:`enb.atable.ATable`.
  * ``output_csv_file`` generates a CSV file with basic statistics (min, max, average, std) for the target columns.

**It's good to know...**
------------------------

* You can add as many columns as desired (even after running the experiments). Consider the second
  method for the ``WikiAnalysis`` class above:

  .. code-block:: python

        @enb.atable.column_function(
            enb.atable.ColumnProperties(name="word_count", label="Word count", plot_min=0))
        def set_line_count(self, file_path, row):
            with open(file_path, "r") as input_file:
                row[_column_name] = len(input_file.read().split())

  .. note::

    * The ``enb.atable.column_function`` decorator accepts ``enb.atable.ColumnProperties``
      instances. These column properties describe not only the unique name for the data
      column, but also other information useful for reporting the obtained results.

    * The `_column_name` global is defined whenever a ``column_function``-decorated method
      is called, containing the unique column name being computed. The use of this global
      is totally optional, but enables less error-prone column renaming.

|

* You can analyze the distribution of one column, while grouping based on another. For instance,
  if the ``status`` column is defined in the ``WikiAnalysis`` class of our example,

  .. code-block:: python

     @enb.atable.column_function(enb.atable.ColumnProperties("status"))
     def set_dead_person(self, file_path, row):
       with open(file_path, "r") as input_file:
          row[_column_name] = "dead" if "death_place" in input_file.read() else "alive"

  then one can make a grouped analysis with the following code snippet:

  .. code-block:: python

        scalar_analyzer.analyze_df(
                full_df=result_df,
                target_columns=["word_count"],
                group_by="status",
                output_plot_dir="plots",
                output_csv_file="analysis/word_count_analysis.csv")

  You can download the `resulting plot <_static/distribution_word_count.pdf>`_.