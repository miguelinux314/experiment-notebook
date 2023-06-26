.. Experiments = data + tasks (with experiment.py)

.. include:: ./tag_definition.rst

Experiments = data + tasks
==========================

In the :doc:`basic_workflow` page, we saw the most basic usage of |ATable|,
e.g., a list of inputs, and a list of columns to obtain the results dataframe.
Here, we discuss the basics of the |Experiment| class, which provides a more
complete tool for realistic experiments.

Often, we want to calculate a set of columns (e.g., metrics) for each element
in the dataset **and** for each of the defined tasks. For example, we may need
to run different algorithms, or the same algorithm with different parameters,
for a fixed test corpus. For this purpose, |enb| provides the |Experiment|
and |ExperimentTask| classes.

For this example, we have a `data/urls/` folder containing `.txt` files, each one
with a single line that is an IP address in plain text. We want to check whether
certain ports are open in any of these IP addresses.

Let's see the steps to create this experiment.
You can look at the sources in that link, or install a self-contained version into a new `ee` folder with:

.. code-block:: bash

   enb plugin install port-experiment-example ee

The two |ATable| s of an Experiment
-----------------------------------

The |Experiment| class combines two |ATable| s:

    - One table contains information about your dataset.
      The `dataset_info_table` attribute is set to an |ATable| instance upon instantiation of
      the |Experiment|. The instance is typically an :class:`enb.sets.FilePropertiesTable`
      subclass, depending on the |Experiment| subclass itself. In other words, different
      experiments may retrieve different aspects from the test corpus files, as needed
      for the experiment.

    - **Experiment is a subclass of ATable**.
      This means that experiment results are retrieved with the instance's `get_df` method.
      Furthermore, it means you can define as many data columns as you require.
      Nothing prevents you from inheriting from other |Experiment| subclasses to complete
      the set of defined columns.

The number of rows of the dataframe returned by an |Experiment|'s `get_df` method
depends on the |ExperimentTask| s used in it. The following figure illustrates how experiments
are structured.

.. figure:: img/experiment_diagram.png
    :width: 100%
    :alt: Experiment diagram
    :align: center

For our experiment, we will use a set of `.txt` files, each containing an IP address.
We can start defining our experiment class

.. code-block::python

    class PortExperiment(enb.experiment.Experiment):
        dataset_files_extension = "txt"

Since all of our samples are in `data/ips`, we can simply tell |enb|
where our data folder is, and it will recursively find all files with
the specified extension:

.. code-block::python

    enb.config.options.base_dataset_dir = "./data/ips"


.. note::

    Remember: |Experiment| classes inherit from |ATable|. Check on the :doc:`basic_workflow` page
    if you need some help with the |ATable| class.

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

In our example, for each input IP address, we want to run the same procedure (checking whether something is open)
for a selection of parameters (ports). We can do this following these steps:

1. Inherit from |ExperimentTask|
2. Set up the `param_dict` attribute based on your needs.
3. Define any number of methods for that task.

The following code illustrates how to do this for our example:

.. code-block::python

    class CheckPort(enb.experiment.ExperimentTask):
    """Experiment task that can perform a check based on
    the selected port.
    """

    def __init__(self, port):
        assert 0 <= port <= 65353
        super().__init__(param_dict=dict(port=port))

    def check_one_port(self, url_file_path):
        """Check whether a given port for a given url in url_file_path is open.
        Return True if and only if a socket could be open to that url:port.
        """
        with open(url_file_path, "r") as url_file:
            url = url_file.readline().strip()
        a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        location = (url, self.param_dict['port'])
        result_of_check = a_socket.connect_ex(location)
        return result_of_check == 0

.. note::

    Don't worry if you don't know what an IP or a port is.
    You can use your own input datasets and tasks, or reuse
    others created by the community.

What rows are created? How are they indexed?
--------------------------------------------

The |ExperimentTask| instances defined for an experiment, along with the dataset
files used as input determine the rows to be computed.

For instance, if we have tasks with name properties `CheckPort__port=80` and
`CheckPort__port=443`, and input files `ip1.txt` and `ip2.txt`,
then enb will create 4 (2*2) rows, indexed as follows:

.. code-block:: text

    ('ip1.txt', 'CheckPort__port=80'),
    ('ip1.txt', 'CheckPort__port=443'),
    ('ip2.txt', 'CheckPort__port=80'),
    ('ip2.txt', 'CheckPort__port=443'),


What columns are created?
-------------------------

You can define as many columns in your |Experiment| class as you need.
To do so, we follow the same basic idea as in :doc:`basic_workflow`.

In our example, we can simply define a single column (`port_open`), whose value is
set to whatever is returned by our `CheckPort` tasks::

    class PortExperiment(enb.experiment.Experiment):
        """Example experiment that checks whether certain ports are open.
        """
        dataset_files_extension = "txt"

        def column_port_open(self, index, row):
            url_file_path, checkport_task = self.index_to_path_task(index)
            return checkport_task.check_one_port(url_file_path)


.. note::

    The :meth:`enb.experiment.Experiment.index_to_path_task` transforms the index
    of an experiment's row into a tuple `(path, task)`, where `path` is the file path
    of the row's dataset element, and `task` is the |ExperimentTask| instance
    corresponding to that row.

Final steps
-----------

We are all set up to retrieve and analyze the results. In the following snippet,
you can see the how to obtain the `result_df` dataframe and how to display
messages for those ports found to be open::

    if __name__ == '__main__':
        # This is the list of inputs. Each one contains one IP in a single line.
        enb.config.options.base_dataset_dir = "./data/ips"

        # This is the list of tasks to be run
        tasks = [CheckPort(port=p) for p in [53, 22, 80, 443, 8008]]

        # Obtain the full table of results
        exp = PortExperiment(tasks=tasks)
        result_df = exp.get_df()

        # Display a list of observed open ports
        open_port_df = result_df[result_df["port_open"]]
        for url_file_path, url_df in open_port_df.groupby("file_path"):
            print(f"Found open ports in {open(url_file_path, 'r').read().strip()}:\n - ", end="")
            print("\n - ".join(str(d['port']) for d in url_df["param_dict"]))

An example output could be as follows:

.. code-block:: text

    Found open ports in 192.168.1.1:
     - 443
     - 53
     - 80
    Found open ports in 192.168.1.2:
     - 80


What's next?
------------

In the next section, |enb| tools for analyzing and plotting are discussed.

In :doc:`image_compression`, you can
topics specifics to experiments related to lossless and lossy image compression.
