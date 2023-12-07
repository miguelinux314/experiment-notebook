.. Dataset curation

.. include:: ./tag_definition.rst

Dataset curation and modification
=================================

Very often, datasets and test corpora need to be curated and/or modified before
conducting experimental analysis with them. Typical tasks include:

* cleaning and homogenization
* validation and filtering
* storage format change
* file renaming
* subset splitting

The `enb` library provides several tools to help do this in the |sets| and |isets| modules.

The |FileVersionTable| class
----------------------------

The |FileVersionTable| base class allows to transform an input folder into an output folder
in a simple way. You just need to:

1. Create a subclass of |FileVersionTable|,
2. Overwrite its `dataset_files_extension` attribute to filter out the file extensions
   that will be produced.
3. Redefine its :meth:`enb.sets.FileVersionTable.version` method, which transforms a single
   input into and output, and
4. Instantiate your subclass (specify the input and output dirs) and run its `get_df` method.

The following toy example shows how to normalize all text files in an input directory
converting them to lowercase and removing leading and trailing spaces from each line:

.. code-block:: python

    import enb

    # 1 - Definition of the FileVersionTable subclass
    class TextNormalizationTable(enb.sets.FileVersionTable):
        # 2 - Input file extension definition
        dataset_files_extension = "txt"

        # 3 - Redefinition of the version method
        def version(self, input_path, output_path, row):
            with open(input_path, "r") as input_file, open(output_path, "w") as output_file:
                contents = input_file.read()
                output_file.write("\n".join(l.lower().strip() for l in contents.splitlines()))


    if __name__ == '__main__':
        # 4 - Instantiation and execution
        tnt = TextNormalizationTable(
            original_base_dir="original_data",
            version_base_dir="versioned_data",
            csv_support_path="")
        tnt.get_df()

This code is made available as a plugin named `file_version_example`
(see :doc:`image_compression_plugins` for more information about installing
and using plugins), i.e.,

.. code-block:: bash

    enb plugin install file_version_example ./fve


.. note:: **Tip**: you can pass `check_generated_files=False` to the initializer of |FileVersionTable|
   so that :meth:`enb.sets.FileVersionTable.version` is not required to produce a file with the
   output path passed as argument. This is particularly useful when

   * renaming files
   * filtering out invalid samples.

.. note:: The subdirectory structure of the input set is preserved by default in the output (versioned) directory.

Predefined classes
------------------

|enb| includes some predefined subclasses of |FileVersionTable|:

* :class:`enb.aanalysis.PDFToPNG`: convert PDF files into high-resolution PNG files.
* :class:`enb.isets.QuantizedImageVersion`: apply uniform quantization to raw images.
* :class:`enb.isets.PNGCurationTable`: convert PNG files into raw files.
* :class:`enb.isets.FitsVersionTable`: extract image data from files in FITS format and save it to raw.

If you create your own subclasses, don't hesistate to submit it to us (e.g., via a pull request in github).
