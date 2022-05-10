.. Available image compression codecs

.. include:: ./tag_definition.rst

Using existing image compression codecs
=======================================

The |enb| library offers a set of codecs that can be installed 
    * via the `enb plugin install` command-line interface (CLI).
    * via the :meth:`enb.plugins.install` method within your scripts via 

Installation via enb plugin install
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In the CLI, you can list the available codecs by performing a search among all available plugins:

.. code-block:: bash

    enb plugin list codec

And then, for instance to install the `zip` plugin one can simply run:

.. code-block:: bash

    enb plugin install zip installation_folder

Installation via :meth:`enb.plugins.install`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can add a line like the following to your script so that it automatically
installs and imports a plugin

.. code-block:: python
    
    enb.plugins.install("huffman")
    
.. autofunction:: enb.plugins.install
    :noindex:


Codec availabily
~~~~~~~~~~~~~~~~

Different codecs are available for different data types and bit depths. If you want to test
all publicly available codecs, you can install the `test-codecs` plugin with:

.. code-block:: bash

    enb plugin install test-codecs tc

and then run the `test_all_codecs.py` script, e.g., with:

.. code-block:: bash

    python tc/test_all_codecs.py

It will produce a set of plots describing the codecs
and the data types for which they are available. A snapshot of this output is shown next

.. figure:: _static/test_codecs/DictNumericAnalyzer_type_to_availability_groupby-group_label_line.png