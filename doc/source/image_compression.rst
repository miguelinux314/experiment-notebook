.. Image compression (with icompression.py)

.. include:: ./tag_definition.rst

Image compression and manipulation
==================================

The `enb` library can be used to create many types of experiments.
Specific support is provided here for image compression experiments.

**Compression experiments**

This section describes how to quickly create and adapt lossless and lossy
compression experiments with existing and new codecs. Several |enb| plugins
are provided which serve as templates for your work.

The following plugins are available:

    * `lossless-compression`
    * `lossy-compression`

See:

    * :doc:`lossless_compression_example`
    * :doc:`lossy_compression_example`


**Custom codecs for compression and decompression**

You will learn how to use and extend these templates, including
the definition of new codecs, e.g., wrappers for compression tools
you want to evaluate.

The `test-codecs` plugin may be of interest to test all available codecs on your platform.

See:

    * :doc:`image_compression_plugins`
    * :doc:`defining_new_compressors`

**Image manipulation**

The section concludes with hints on how to manipulate images in `enb`. 
Special attention is given to raw (uncoded) images.

See:
    * :doc:`image_manipulation`

.. note:: `enb` uses `numpy` arrays, *e.g.*,  when loading images in memory.
          It1 is recommended that you get acquainted with `numpy` if you intend
          to manipulate images with `enb`.

**Contents**

.. toctree::
   :maxdepth: 1

   lossless_compression_example
   lossy_compression_example
   image_compression_plugins
   defining_new_compressors
   image_manipulation