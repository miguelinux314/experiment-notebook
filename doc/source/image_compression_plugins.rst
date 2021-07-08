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

3. Import and use the defined codec classes. See `this script <https://github.com/miguelinux314/experiment-notebook/tree/master/plugins/test_all_codecs/test_all_codecs.py>`_ for a full example on how to do this.


.. note:: An automatization process is underway - expect this to become easier in the future.

.. warning:: For some of the codecs, only the `enb` wrapper is provided but not the compressor sources or binaries.
  This is due to IPR restrictions.

Image Codec availability
++++++++++++++++++++++++

The following tables summarize the compression capabilities of many image codec families available in `enb`.

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

.. note:: Generated data samples are not meant to be representative of any type of data source, they
  just exercise the nominal dynamic range.

For each codec/data type combination, the following aspects are considered:

- Whether the codec executes `compress()` and `decompress()` without raising any Exception.
  If it fails, it is labeled as 'Not Available'

- Whether the codec is able to reconstruct the original data without any loss.

Availability tables:

- `General availability <https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/plots/codec_availability_general_type_to_availability.pdf>`_
  (displayed below)
- `Unsigned integer availability <https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/plots/codec_availability_unsigned_type_to_availability.pdf>`_

- `Signed integer availability <https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/plots/codec_availability_signed_type_to_availability.pdf>`_

- `Floating point data availability <https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/plots/codec_availability_float_type_to_availability.pdf>`_


.. image:: https://github.com/miguelinux314/experiment-notebook/raw/dev/plugins/test_all_codecs/plots/codec_availability_general_type_to_availability.png
