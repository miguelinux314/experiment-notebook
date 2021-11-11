.. Experiments = data + tasks (with experiment.py)

.. include:: ./tag_definition.rst

Experiments = data + tasks
==========================

In the :doc:`basic_workflow` page, we saw the most basic usage of |ATable|,
e.g., a list of inputs, and a list of columns to obtain the results dataframe.

Often, we want to calculate a set of columns (e.g., metrics) for each element
in the dataset **and** for each of the defined tasks. For example, we may need
to run different algorithms, or the same algorithm with different parameters,
for a fixed test corpus. For this purpose, |enb| provides the |Experiment|
and |ExperimentTask| classes.

The two |ATable| s of an Experiment
-----------------------------------

The |Experiment| class combines two |ATable| s:

    - The `dataset_info_table` attribute is set to an |ATable| instance upon instantiation of
      the |Experiment|. The instance is typically an :class:`enb.sets.FilePropertiesTable`
      subclass, depending on the |Experiment| subclass itself. In other words, different
      experiments may retrieve different aspects from the test corpus files, as needed
      for the experiment.

    -  The |Experiment| is a subclass of |ATable| itself.
       This means that experiment results are retrieved with the instance's `get_df` method.
       Furthermore, it means you can define as many data columns as you require.
       Nothing prevents you from inheriting from other |Experiment| subclasses to complete
       the set of defined columns.

The number of rows of the dataframe returned by an |Experiment|'s `get_df` method
depends on the |ExperimentTask| s used in it.

Experiment tasks
----------------

The |ExperimentTask| class can be extended or used directly to define the tasks
that need to be performed for each input sample.

- The `enb.experiment.ExperimentTask.param_dict` attribute can be used to store
  as many parameters as needed.

- You can create subclasses of |ExperimentTask|, e.g., with a common method `f`.
  Then, in the definition of your |Experiment| columns, you can call that method
  `f` automatically for each input and each parameter combination, and obtain
  a clean table of results.

What rows are created? How are they indexed?
--------------------------------------------

The |ExperimentTask| instances defined for an experiment, along with the dataset
files used as input determine the rows to be computed.

For instance, if we have tasks `t1` and `t2` and input `data1.txt` and `data2.txt`,
then enb will create 4 (2*2) rows, indexed as follows::

    ('data1.txt', t1),
    ('data1.txt', t2),
    ('data2.txt', t1),
    ('data2.txt', t2),


What columns are created?
-------------------------

You can define as many columns in your |Experiment| class as you need.
To do so, we follow the same basic idea as in :doc:`basic_workflow`.

The only difference this time is that the `index` parameter passed to
the column-computing functions is now a tuple with two elements:
the index in the `dataset_info_table` of the |Experiment|
and the `name` property of the |ExperimentTask|.










- basic experiment
- automatic sample recognition (extension?)
- experimenttask for parameter grouping
- TaskFamily for analysis