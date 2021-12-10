.. Defining new codecs (using icompression.py)

.. include:: ./tag_definition.rst

Defining new codecs
===================

This page provides some detail on how to add new image compressors (codecs) to your experiments.

In general, to add new custom codecs to your lossless (or lossy) compression experiments,
you just need to add new instances of :class:`enb.icompression.AbstractCodec` subclasses.
Notwithstanding, several helper classes have been added to :mod:`enb.icompression` to speed up
the creation of new codecs

Lossless codecs
---------------
Lossless codecs are expected to be able to reconstruct a mathematically identical representation the original data.

You can define new Lossless codecs by subclassing the :class:`enb.icompression.LosslessCodec` class, like in the
following example:

.. code-block:: python

  class LZ77Huffman(icompression.LosslessCodec):
    MIN_COMPRESSION_LEVEL = 1
    MAX_COMPRESSION_LEVEL = 9
    DEFAULT_COMPRESSION_LEVEL = 5

    def __init__(self, compression_level=DEFAULT_COMPRESSION_LEVEL, param_dict=None):
        assert self.MIN_COMPRESSION_LEVEL <= compression_level <= self.MAX_COMPRESSION_LEVEL
        param_dict = dict() if param_dict is None else param_dict
        param_dict["compression_level"] = compression_level
        super().__init__(param_dict=param_dict)
        """Apply the LZ77 algorithm and Huffman coding to the file using zlib.
        """

    def compress(self, original_path, compressed_path, original_file_info):
        with open(original_path, "rb") as original_file, \
                open(compressed_path, "wb") as compressed_file:
            compressed_file.write(zlib.compress(original_file.read(),
                                  level=self.param_dict["compression_level"]))

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        with open(compressed_path, "rb") as compressed_file, \
                open(reconstructed_path, "wb") as reconstructed_file:
            reconstructed_file.write(zlib.decompress(compressed_file.read()))

    @property
    def label(self):
        return f"lz77huffman_lvl{self.param_dict['compression_level']}"


Further working examples are readily available in the
`plugin_zip <https://github.com/miguelinux314/experiment-notebook/blob/master/enb/plugins/plugin_zip/zip_codecs.py>`_
plugin.


Lossy and near lossless codecs
---------------------------------

Lossy and near-lossless codecs can be defined by subclassing :class:`enb.icompression.LossyCodec` and
:class:`enb.icompression.NearLosslessCodec`, respectively.

As in the previous example, the `compress(self, original_path, compressed_path, original_file_info)`
and `decompress(self, compressed_path, reconstructed_path, original_file_info=None)` functions
need to be specified.

Executable wrapper codecs
----------------------------

Very often, compressors are implemented as an external tools, and compression and decompression
consists in running those executables. To minimize the amount of lines of code (and bugs) that
you need to type, the :class:`enb.icompression.WrapperCodec` is provided.

This class is better explained with an example:

.. code-block:: python

  class TrivialCpWrapper(icompression.WrapperCodec, icompression.LosslessCodec):
    """Trivial codec wrapper for /bin/cp.
    """

    def __init__(self):
        super().__init__(compressor_path="cp", decompressor_path="cp")

    def get_compression_params(self, original_path, compressed_path, original_file_info):
        return f"'{original_path}' '{compressed_path}'"

    def get_decompression_params(self, compressed_path, reconstructed_path, original_file_info):
        return f"'{compressed_path}' '{reconstructed_path}'"



In this case, only `get_compression_params` and `get_decompression_params` need to be implemented

The return value of these is a string with the parameters one would type after the binary path, e.g., in a bash console.

.. note::
  The return value of `get_compression_params` and `get_decompression_params` should not include the executable
  path itself, only the parameters.

.. _creating_codec_plugins:

Packing your codec as a plugin
---------------------------------
Once you have tested your codec, you might want to release it as a plugin so that other `enb` users can benefit from
your development.


To create your plugin and share it with the community,

    - Create a folder with your code

    - Add a `__init__.py` file to that folder, with imports such as

      .. code-block:: python

          from . import my_module

      if `my_module.py` is one of the modules you want to make available .

    - Add a __plugin__.py file such as the one in
      `plugin_zip's __plugin__.py <https://github.com/miguelinux314/experiment-notebook/blob/master/enb/plugins/plugin_zip/__plugin__.py>`_,
      updating all needed fields. This contains basic metainformation for |enb| to be able to dynamically
      find and install your plugin.

    - Send a pull request to the `dev` `branch <https://github.com/miguelinux314/experiment-notebook/tree/dev>`_
      or get in touch with the maintainers so that it can be reviewed an published.
