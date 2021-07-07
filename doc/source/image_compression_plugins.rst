.. Available image compression codecs

Available image compression codecs
==================================

Codecs are classes that can be easily integrated in `enb` experiments and allow you to compute all sorts of results.
If you design compression experiments, you may want to compare you methods with
others publicly available.

Using existing codecs
+++++++++++++++++++++

The `plugins <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins>`_
folder of the library contains `enb`-compatible implementations of image compressors
(typically wrappers for binary compressors/decompressors).

Two use any of the available plugins, you need to:

1. Download a copy of the latest published plugin into your enb experiment folder.
2. (Sometimes) run `make` to build the plugin binaries for your platform.
3. Import and use the defined codec classes.
  See `this script <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins/test_all_codecs/test_all_codecs.py>`_
  for a full example on how to do this.

.. warning:: For some of the codecs, only the `enb` wrapper is provided but not the compressor sources or binaries.
  This is due to IPR restrictions.

Image Codec availability
++++++++++++++++++++++++

The following tables summarize the compression capabilities of many image codec families available in `enb`.
The interested reader is referred to `this folder in the repository <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins>`_
for a full list of available codecs.

Evaluation process
~~~~~~~~~~~~~~~~~~

All codecs are tested for the following data types
(available `here <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins/test_all_codecs/data>`_:

- Integer data:
    - Signed and unsigned.
    - Big endian and little endian.
    - Stored in 1, 2 or 4 bytes per sample (`bytes_per_sample`)
    - Exercising dynamic ranges of B bits, for `B = 1, ..., 8*bytes_per_sample`.

- Floating point data:
    - Stored in numpy's f16, f32 and f64 format.
    - Exercising the whole range (excluding non finite values).

.. note:: Generated data samples are not meant to be representative of any type of data source.

For each codec/data type combination, the following aspects are considered:

- Whether the codec executes `compress()` and `decompress()` without raising any Exception.
  If it fails, it is labeled as 'Not Available'

- Whether the codec is able to reconstruct the original data without any loss.

- The minimum and maximum bitdepths (for either integer or float data) for which the codec is lossless (if any).

- The minimum and maximum compression ratios ($$ CR = \frac{original size}{compressed size}$$) for all samples *for which the
  codec is available*, if any. Recall that these CR values are in no way representative of actual performance
  in real scenarios, but may serve to coarsely compare similar compression paradigms.

The following tables are automatically updated as new plugins are made available.
The interested reader can check
`the code that produces <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins/test_all_codecs/generate_test_images.py>`_.

Integer data
************

Unsigned 8 bit integers
_______________________

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/codec_availability_u8be.png

Unsigned 16 bit integers
________________________

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/codec_availability_u16be.png

Unsigned 32 bit integers
________________________

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/codec_availability_u32be.png

Signed 16 bit integers
______________________

.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/codec_availability_s16be.png

Floating point data
*******************

