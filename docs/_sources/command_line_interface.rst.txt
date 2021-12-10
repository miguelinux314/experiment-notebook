.. include:: ./tag_definition.rst

Command-line interface
======================

|enb| is friendly with the command line interface (CLI). Two main ways of using the CLI
with enb:

The `enb` program
-----------------

If you installed `enb`, most likely you can run `enb` from your command line and access its main CLI.
An example output of running `enb -h` (to display usage help) is shown next::

    usage: enb [-h] {plugin,help} ...

    CLI to the electronic notebook (enb) framework
    (see https://github.com/miguelinux314/experiment-notebook).

    Several subcommands are available; use `enb <subcommand> -h`
    to show help about any specific command.

    optional arguments:
      -h, --help     show this help message and exit

    subcommands:
      Available enb CLI commands.

      {plugin,help}
        plugin       Install and manage plugins.
        help         Show this help and exit.


Plugin and template installation
--------------------------------

The |enb| library comes packed with several plugins and templates. To access them, one can use `enb pluginp`.
In particular, `enb plugin -h` shows all available options:

.. code-block:: text

    usage: enb plugin [-h] {install,list} ...

    optional arguments:
      -h, --help      show this help message and exit

    subcommands:
      Plugin subcommands

      {install,list}
        install       Install an available plugin.
        list          List available plugins.

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
* Passing a valid `--option=value` argument to a script using `enb`.


When executing a script that uses `enb`, you can use the CLI to set different configuration options.
For instance, to show additional information when running your script, you can pass the additional
parameter flag:

.. code-block:: text

    --verbose=2

To make it more verbose (more v's: more verbosity).

A set of predefined parameters are available in `enb.config.options`, the single instance
of the :class:`enb.config.AllOptions` class.
When running a script that import enb.config, "-h" can be passed as argument to show
a help message with all available options.


All these options (whether provided via the CLI or not) can be read and/or changed with code like the following:

.. code-block:: python

    from enb.config import options
    print(f"Verbose level: {enb.config.verbose}")

