.. Image compression (with icompression.py)

Image compression experiments
=============================

The `enb` library can be used to create many types of experiments.
Specific support is provided for image compression experiments.
This section deals with image compression experiments
and how to design and run them with minimal effort.

You will lear how to use and extend templates to quickly define effective experiments.
Examples and usage help are provided for both lossless and lossy compression regimes.

You will also learn how to employ codec plugins provided in `enb` to further extend your experiments.

Finally, some tips regarding the creation of new codecs is discussed.

.. toctree::
   :maxdepth: 1

   lossless_compression_example
   lossy_compression_example
   image_compression_plugins
   defining_new_compressors