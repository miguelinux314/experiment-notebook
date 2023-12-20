.. include:: tag_definition.rst

API
===

API highlights
--------------

Quick API reference

* Core modules:
    * |atable|: definition of the core ATable functionality
        * |ATable|: core class with automatic parallelization and persistence management.
        * :func:`enb.atable.ATable.get_df`: method to produce a |DataFrame| with the table contents.
        * See :doc:`basic_workflow` for extra information on |ATable|

    * :mod:`enb.sets`: Definition of ATable subclasses defining datasets
        * :class:`enb.sets.FilePropertiesTable`

    * :mod:`enb.isets`: Definition of image datasets based on :class:`enb.sets`
        * :func:`enb.isets.load_array_bsq`: load a raw image as a 3D numpy array indexed as [x,y,z]
        * :func:`enb.isets.dump_array_bsq`: dump a 3D numpy array indexed as [x,y,z] as a BSQ raw image.
        * :class:`enb.isets.ImagePropertiesTable`: ATable subclass for image datasets, including relevant image properties.

    * |experiment|: Experiments apply a set of tasks to each of the elements of a dataset (see `enb.sets` and `enb.isets`)
        * |Experiment|: subclass of ATable, base for experiment subclass definition.
          Run with :func:`enb.experiment.Experiment.get_df`
        * |ExperimentTask|: defines one task to be applied to each element of the dataset
        * See :doc:`experiments` for extra information on experiments.

    * :mod:`enb.icompression`: Tools for easy definition of lossless and lossy compression experiments.
        * |CompressionExperiment|
        * |LosslessCompressionExperiment|
        * |LossyCompressionExperiment|
        * See :doc:`image_compression` for extra information on image compression experiments.

    * :mod:`enb.aanalysis`: Tools for automatic analysis and plotting of the |DataFrame| instances obtained
       with :func:`enb.atable.ATable.get_df` or its subclass implementations, e.g., in |Experiment|.
        * |Analyzer|: subclasses implement different types of automatic analysis
            * |ScalarNumericAnalyzer| : for individual columns of numeric data
            * |TwoNumericAnalyzer| : for comparing pairs of columns with numeric data
            * |DictNumericAnalyzer| : for analyzing columns with cells containing dictionaries with numeric values
            * |ScalarNumeric2DAnalyzer| : for spatially analyzing numeric data whose x and y position is given in
              other columns
            * |ScalarNumericJointAnalyzer| : for splitting a data column into two categories, one giving multiple
              columns, the other givin multiple rows.
        * |TaskFamily|: class to group list of tasks under the same name.
        * See :doc:`analyzing_data` for extra documentation on data analysis and plotting.

* Utility modules
    * :mod:`enb.plotdata` and :mod:`enb.render`: module with the implementation of the low-level plotting routines.
        * :func:`enb.render.render_plds_by_group`: used to generate plots by all |Analyzer| subclasses.

    * :class:`enb.log`: Logging utilities for `enb`.

    * Parallelization
        * :mod:`enb.parallel`: Implementation of the multiprocess parallelization functionality using pathos (default)
        * :mod:`enb.parallel_ray`: Implementation of the multiprocess parallelization functionality using ray.

    * :mod:`enb.tarlite`: module with tools that implement a lightweight tar-like format (a concatenation of files).
        * :func:`enb.tarlite.tarlite_files`
        * :func:`enb.tarlite.untarlite_files`

    * :mod:`enb.pgm`, :mod:`enb.jpg`, :mod:`enb.png`: manipulation (load/save) of PGM, PPM, PNG, JPG images
       to and from 2D or 3D numpy arrays


Full API
--------

Full, automatically generated API is provided next.

.. toctree::
  api/modules
