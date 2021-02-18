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

The following table summarizes the capabilities of the plugins released to date.
You can find example usage code in `this script <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins/test_all_codecs/test_all_codecs.png>`_
used to generate the table.

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/codec_availability.png