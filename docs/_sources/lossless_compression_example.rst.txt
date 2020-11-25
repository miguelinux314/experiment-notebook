.. Description of an image compression experiment example (using icompression.py) 

Lossless Compression Experiment
===============================

This page explains the general dynamics of using the :class:`enb.icompression.LosslessCompressionExperiment` class.
This class is a subclass of :class:`enb.experiment.Experiment`.
 
.. note:: This example assumes you have understood the :doc:`basic_workflow` example, and that you have successfully
  followed the installation instructions in :doc:`installation`.

1 - Example setup
*****************

You can find the example at `templates/lossless_compression_example <https://github.com/miguelinux314/experiment-notebook/tree/master/templates/lossless_compression_example>`_.
In Linux, you can clone the latest version with the following steps:

.. code-block:: bash

   wget https://github.com/miguelinux314/experiment-notebook/archive/master.zip
   unzip master.zip
   cp -r experiment-notebook-master/templates/lossless_compression_example/ .
   
This example makes uses of the ``plugin_jpeg`` plugin. You need to copy it to the same folder
where you are running the experiment (.). The following code will do the trick:

.. code-block:: bash

   cp -r experiment-notebook-master/plugins/plugin_jpeg .

This completes the setup of the experiment

2 - Data curation
*****************

Data has been previously curated for you, and placed in the ``data/`` folder.

For image compression experiments, it is needed that:  

    - Images are in RAW (uncompressed) format, preferably with '.raw' extension, 
      in BSQ in case more than one component is present.

    - Images contain a tag such as 'u8be-3x600x800' in their name.
      
        * *u* or *s* should be used for unsigned or signed data
        * *8*, *16* or *32* indicate the bitdepth in bits of each sample
        * the geometry part of the tag is ZxYxX, where X, Y and Z are, respectively,
          the images width, height and number of components (bands). 

    - Images can be organized in subfolders. This is not mandatory, and it is not used in the current 
      example.

3 - Experiment execution
************************

You just need to execute the following line:

.. code-block:: bash
    
    ./lossless_compression_experiment_example.py

This should produce the ``plots``, ``analysis`` folders. 
Furthermore, a ``persistence_lossless_compression_experiment_example.py`` folder is created
with persistence information, so that images do not need to be analyzed again, and that
compression needs not be performed again unless you add any new codecs to your experiment.

4 - Code explanation
********************

The example code in ``persistence_lossless_compression_experiment_example.py`` 
is documented and (hopefully) self-explanatory. 

Initialization
--------------

The initialization is straightforward. Note how the plugin's main module needs to be imported.

.. code-block:: python

    import os
    from enb.config import get_options
    options = get_options(from_main=False)
    from enb import icompression
    from enb import aanalysis
    import plugin_jpeg.jpeg_codecs
    
    

Setup
--------------

A minimal setup is needed so that the experiment can be created and can locate the data of interest.

.. note::
    The ``codecs`` list here can contain any number of :class:`enb.icompression.LosslessCodec`
    instances. 

.. code-block:: python

    # Setup global options
    options.base_dataset_dir = "./data"

    # Define list of codecs
    codecs = []
    codecs.append(plugin_jpeg.jpeg_codecs.JPEG_LS(max_error=0))


Experiment execution
--------------------

The lossless compression experiment can now be created, and used to generate a 
:class:`pandas.DataFrame` instance with all defined columns.

.. code-block:: python
    
    # Create experiment
    exp = icompression.LosslessCompressionExperiment(codecs=codecs)

    # Generate pandas dataframe with results
    df = exp.get_df(
        parallel_row_processing=not options.sequential,
        overwrite=options.force > 0)

Data analysis
-------------

One can perform automatic analysis of the dataframe with :class:`enb.aanalysis.ScalarDistributionAnalyzer`
and any of the other classes in that module. 

.. code-block:: python

    # Plot some results
    analyzer = aanalysis.ScalarDistributionAnalyzer()
    target_columns = ["compression_ratio_dr", "bpppc", "compression_time_seconds"]
    analyzer.analyze_df(
        # Mandatory params
        full_df=df,                           # the dataframe produced by exp
        target_columns=target_columns,        # the list of ATable column names 
        # Optional params
        output_csv_file=os.path.join(         # save some statistics 
            options.analysis_dir, "lossless_compression_analysis.csv"),
        column_to_properties=exp.joined_column_to_properties, # contains plotting hints
        group_by="task_label",                # one can group by any column name                    
    )
   

.. note:: 
   The ``compression_ratio_dr``. ``bpppc`` and ``compression_time_seconds`` columns
   are automatically created by the LosslessCompressionExperiment class. You can 
   extend this class with new columns, as described in the :doc:`basic_workflow` example.

.. note:: Of course, custom analysis of the dataframe is possible for maximum control.

5 - Defining new codecs
***********************

In order to add new custom codecs to your lossless (or lossy) compression experiments,
you just need to add new instances of :class:`enb.icompression.AbstractCodec` subclasses.

When creating these subclasses, you just need to implement the
:class:`enb.icompression.AbstractCodec.compress` and 
:class:`enb.icompression.AbstractCodec.decompress` methods.

.. note::
   The ``original_file_info`` parameter passed to the two previous methods is a dict-like
   instance that contains the 'width', 'height' and 'component_count' keys, among others.
   See the source of the :class:`enb.isets.ImageGeometryTable` class for a list of all keys that 
   are available in this dict-like object.