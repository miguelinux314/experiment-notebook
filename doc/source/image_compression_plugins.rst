.. Using image compression plugins

Using image compression plugins
===============================

If you design compression experiments, you may want to compare you methods with
others publicly available.

The `plugins <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins>`_
folder of the library contains `enb`-compatible implementations of image compressors
(typically wrappers for binary compressors/decompressors).

.. note:: For some of the codecs, only the `enb` wrapper is provided but not the compressor binaries.
  This is due to IPR restrictions.

The following tables summarize the capabilities of the plugins released to date for different types of data
You can find example usage code in `this script <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins/test_all_codecs/test_all_codecs.py>`_
used to generate the table.

In these tables, the lossless range refers to any data type.

Unsigned 8 bit
--------------

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/codec_availability_u8be.png

Unsigned 16 bit
---------------

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/codec_availability_u16be.png

Signed 16 bit
-------------

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/codec_availability_s16be.png

