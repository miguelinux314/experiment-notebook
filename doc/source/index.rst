.. Experiment Notebook documentation master file, created by
   sphinx-quickstart on Wed Apr  1 11:33:35 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to the Experiment Notebook
===============================================

.. figure:: img/enb_logo.png
    :width: 15%
    :alt: |enb| logo
    :align: center

The Experiment Notebook (from now on, ``enb``) library is designed to help you obtain
and report computer-based experimental data. Focus on what is new in your
current experiment, and let ``enb`` deal with the repetitive stuff.

Some of the main features of ``enb`` are:

  * **Flexible**: you can easily adapt the provided examples to suit your needs.
  * **Persistent**: no need to re-run your experiments: results are automatically saved.
  * **Disseminable**: ``enb`` helps you create figures and tables to report your data.
  * **Extensible**: you can always add new samples, define new columns and produce new figures.

.. note::
   ``enb`` is based on well-known python libraries such as ``pandas``, ``matplotlib`` and ``ray``.
   No prior knowledge of these libraries is required, although basic understanding of ``pandas``
   can be most useful.

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
   api
   thanks