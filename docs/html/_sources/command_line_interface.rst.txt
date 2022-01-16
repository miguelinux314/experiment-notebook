.. include:: ./tag_definition.rst

The `enb` command-line tools
============================

|enb| is friendly with the command line interface (CLI). Two main ways of using the CLI
with enb:

- Using the `enb` program from the command line
- Setting the values of |options| from the command line when invoking your enb-using scripts.

Each way is explored in the following sections


The `enb` program
-----------------

If you installed `enb`, most likely you can run `enb` from your command line and access its main CLI.
An example output of running `enb help` (to display usage help) is shown next:

.. program-output:: enb help


Listing available plugins and templates
+++++++++++++++++++++++++++++++++++++++

The |enb| library comes packed with several plugins and templates. To access them, one can use `enb pluginp`.
In particular, `enb plugin -h` shows all available options.

Use `enb plugin list` to get a list of all available plugins and templates. You can add extra parameters for filtering
and/or `-v` for extra details.

.. program-output:: enb plugin list

Plugin and template installation
+++++++++++++++++++++++++++++++++++++++

To install a plugin or template, use the following syntax

.. code-block:: bash

    enb plugin install <plugin-name> <destination-folder>

For example, `enb plugin install zip ./codecs/zip_codecs` should produce something similar to:


.. code-block:: text

    ............... [ Powered by enb (Experiment NoteBook) v0.3.3 ] ................

    Installing zip into [...]/codecs/zip_codecs...
    Building zip into [...]/codecs/zip_codecs...
    Plugin 'zip' successfully installed into './codecs/zip_codecs'.


CLI with scripts using `enb`
----------------------------

If your script includes `import enb`, then you can pass `--option=value` arguments when invoking
it to set the values of |options|.

In addition, to get a list of all of all available options, you can run your script with the `-h`
options. An example option of this is shown next:

.. program-output:: python ../../enb/plugins/template_basic_workflow_example/basic_workflow.py -h

.. note:: `*.ini` files in the project root are searched for to look for default values for the
  attributes of |options|. You can copy and modify the default enb.ini template to your project
  if you would like to use file-based configuration.

.. note:: You can also modify |options| in your code as in `enb.config.options.verbose = 5`.
  If you do, this is applied after the CLI parameter recognition, and therefore overwrites
  any values set via `--option=value`.


A set of predefined parameters are available in `enb.config.options`, the single instance
of the :class:`enb.config.AllOptions` class.
When running a script that import enb.config, "-h" can be passed as argument to show
a help message with all available options.


All these options (whether provided via the CLI or not) can be read and/or changed with code like the following:

.. code-block:: python

    from enb.config import options
    print(f"Verbose level: {options.verbose}")

