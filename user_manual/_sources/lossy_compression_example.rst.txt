.. Description of a lossy image compression experiment example (using icompression.py)

Lossy Compression Experiment
============================
This page explains the general dynamics of using the :class:`enb.icompression.LossyCompressionExperiment` class,
and how easily report results. This class is a subclass of :class:`enb.experiment.Experiment`.

An example is used, and line plots with :class:`enb.aanalysis.TwoColumnLineAnalyzer` are introduced.
Note that line plots can be used with lossless compression experiments as well.
 
.. note:: This example assumes you have understood the :doc:`basic_workflow` example, and that you have successfully
  followed the installation instructions in :doc:`installation`.

.. note::

    The `compression_ratio_dr`. `bpppc` and `compression_time_seconds` columns
    are automatically created by the LosslyCompressionExperiment class. You can
    extend this class with new columns, as described in the :doc:`basic_workflow` example.

Lossy: experiment setup
***********************

You can find the example at `templates/lossless_compression_example <https://github.com/miguelinux314/experiment-notebook/tree/master/templates/lossy_compression_example>`_.
In Linux, you can clone the latest version with the following steps:

.. code-block:: bash

   wget https://github.com/miguelinux314/experiment-notebook/archive/master.zip
   unzip master.zip
   cp -r experiment-notebook-master/templates/lossless_compression_example/ .
   
This example makes uses of the `plugin_jpeg` and `pugin_mcalic` plugins.
You need to copy them to the same folder where you are running the experiment (.).
The following code will do the trick:

.. code-block:: bash

   cp -r experiment-notebook-master/plugins/{plugin_jpeg, plugin_mcalic} .

This completes the setup of the experiment

Lossy: data curation
********************

Data has been previously curated for you, and placed in the `data/` folder.
It contains the landsat images from the CCSDS Data Compression working group.

The same requirements are needes as in :doc:`lossless_compression_example`.

As usual, it is needed that:

    - Images are in RAW (uncompressed) format, preferably with '.raw' extension, 
      in BSQ in case more than one component is present.

    - Images contain a tag such as 'u8be-3x600x800' in their name.
      
        * *u* or *s* should be used for unsigned or signed data
        * *8*, *16* or *32* indicate the bitdepth in bits of each sample
        * the geometry part of the tag is ZxYxX, where X, Y and Z are, respectively,
          the images width, height and number of components (bands). 

    - Images can be organized in subfolders. This is not mandatory, and it is not used in the current 
      example.

Lossy: script execution
***********************

You just need to execute the following line:

.. code-block:: bash
    
    ./lossy_compression_experiment_example.py [-vv]

This should produce the `plots``, `analysis``folders.
Furthermore, a `persistence_lossy_compression_experiment_example.py` folder is created
with persistence information, so that images do not need to be analyzed again, and that
compression needs not be performed again unless you add any new codecs to your experiment.

Lossy: code
***********

The example code in `persistence_lossy_compression_experiment_example.py <https://github.com/miguelinux314/experiment-notebook/blob/master/templates/lossy_compression_example/lossy_compression_experiment_example.py>`_
is documented and (hopefully) self-explanatory.

Lossy: initialization
---------------------

The initialization is straightforward. Note how the plugin's main module needs to be imported.

.. code-block:: python

    import os
    from enb.config import get_options
    options = get_options(from_main=False)
    from enb import icompression
    from enb import aanalysis
    import plugin_jpeg.jpeg_codecs
    import plugin_mcalic.mcalic_codecs


Lossy: setup
------------

To maximize the quality of the output plots, some setup is needed to define the input data set
and the families of codecs we want to use.

During the experiment setup, a list of :class:`enb.aanalysis.TaskFamily` instances are produced,
which are passed to the `group_by` argument.

A plain list of all codecs to be tested needs also be produced, as in the :doc:`lossless_compression_example`.

.. note::
    The `codecs` list here can contain any number of :class:`enb.icompression.LossyCodec`
    instances. See :doc:`defining_new_compressors` for further information.

.. code-block:: python

    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "landsat")

    all_codecs = []
    all_families = []
    # A family is a set of related tasks
    jpeg_ls_family = enb.aanalysis.TaskFamily(label="JPEG-LS")
    for c in (plugin_jpeg.jpeg_codecs.JPEG_LS(max_error=m) for m in range(7)):
        all_codecs.append(c)
        jpeg_ls_family.add_task(c.name, f"{c.label} PAE {m}")
    all_families.append(jpeg_ls_family)

    # One can add as many families as lines should be depicted
    mcalic_family = enb.aanalysis.TaskFamily(label="M-CALIC")
    for c in (plugin_mcalic.mcalic_codecs.MCALIC_Magli(max_error=m) for m in range(10)):
        all_codecs.append(c)
        mcalic_family.add_task(c.name, f"{c.label} PAE {m}")
    all_families.append(mcalic_family)

    # One can easily define pretty plot labels for all codecs individually, even when
    # one or more parameter families are used
    label_by_group_name = dict()
    for family in all_families:
        label_by_group_name.update(family.names_to_labels)



Lossy: experiment running
-------------------------

The lossless compression experiment can now be created, and used to generate a 
:class:`pandas.DataFrame` instance with all defined columns.

Notice how `show_h_range_bar` and `show_h_std_bar` are employed to signal the range and +/- 1 std in the x axis.
They can be used in the y axis by replacing `h` with `v`.

.. code-block:: python
    
    # Run experiment and produce figures
    exp = enb.icompression.LossyCompressionExperiment(codecs=all_codecs)
    df = exp.get_df()

Lossy: data analysis
********************

One can perform automatic analysis of the dataframe with :class:`enb.aanalysis.ScalarDistributionAnalyzer`
and :class:`enb.aanalysis.TwoColumnLineAnalyzer`, as well as other classes in that module.

.. code-block:: python

    enb.aanalysis.ScalarDistributionAnalyzer().analyze_df(
        full_df=df,
        target_columns=["bpppc", "pae", "compression_efficiency_2byte_entropy", "psnr_dr"],
        output_csv_file="analysis.csv",
        column_to_properties=exp.joined_column_to_properties,
        group_by="task_name",
        y_labels_by_group_name=label_by_group_name,
    )
    enb.aanalysis.TwoColumnLineAnalyzer().analyze_df(
        full_df=df,
        target_columns=[("bpppc", "pae"), ("bpppc", "psnr_dr")],
        column_to_properties=exp.joined_column_to_properties,
        show_markers=True,
        show_h_range_bar=True,
        show_h_std_bar=True,
        group_by=all_families,
        legend_column_count=2)
   
The promised line plot with error range

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/master/templates/lossy_compression_experiment/png_plots/plot_line_bpppc_pae.png

Another plot showing the histogram of efficiencies (based on 2-byte zero-order entropy)
for the JPEG-LS and M-CALIC codecs is shown below as well:

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/master/templates/lossy_compression_experiment/png_plots/distribution_compression_efficiency_2byte_entropy.png


