.. Experiment Notebook documentation master file, created by
   sphinx-quickstart on Wed Apr  1 11:33:35 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Experiment Notebook user manual
===============================

.. figure:: img/enb_logo.png
    :target: #
    :width: 25%
    :alt: |enb| logo
    :align: center

|

The Experiment Notebook (from now on, ``enb``) library is designed to help you obtain
and report computer-based experimental data. Focus on what is new in your
current experiment, and let ``enb`` deal with the repetitive stuff.

Some of the main features of ``enb`` are:

  * **Flexible**: With a few lines of code, you can easily
    create custom experiments and/or analyze the results you want.
    `enb` provides an easy Python interface and out-of-the-box templates and examples
    and this user manual to get you started in no time.
    By default, only standard packages need to be installed.

  * **Disseminable and reproducible**: ``enb`` offers simple and complex tools to create
    figures and tables to report your data.
    You can also distribute your project folder and let others
    verify and re-run your experiment.

  * **Persistent**: With `enb`, all intermediate results are periodically stored and kept after an
    experiement is completed. This way, you don't need to run all computations over and over again.
    This applies to others running your experiments on other computers.

  * **Extensible**: you can always add new samples, define new columns and produce new figures.
    You will only need to obtain results for the newly defined data columns or samples.

  * **Parallel in nature**: you can use all the CPUs / GPUs in your local machine, and even
    distribute the load across a cluster of computers (clusters only supported on Linux and MacOS).

Please visit `the enb github page <https://github.com/miguelinux314/experiment-notebook>`_ for
full access to the code.

.. note::
   ``enb`` is based on well-known python libraries such as ``pandas`` and ``matplotlib``.
   No prior knowledge of these libraries is required, although basic understanding of ``pandas``
   can be most useful.

.. note::
   Clustering support is provided only on Linux and MacOS systems. The `ray` library
   as well as the `ssh` and `sshfs` tools are employed for this purpose.
   If `ray` is not available, e.g., on Windows, the `pathos` library is employed for
   parallelization, and no clustering support is provided.
   See full details for multi-computer parallelization in :doc:`cluster_setup`.

The following help pages will tour you through the most important features of ``enb``,
and show minimal examples that you can use as starting point for your projects.
You can also take a look at the automatically generated :ref:`API<api>`.

.. warning::

   This project is in beta! Comments welcome.

.. toctree::
   :maxdepth: 1
   :caption: Documentation contents:

   installation
   basic_workflow
   experiments
   analyzing_data
   image_compression
   command_line_interface
   cluster_setup
   api
   thanks