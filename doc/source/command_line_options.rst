Command-line options
====================

When executing your experiments using enb, you can use the command-line interface (CLI)
features it includes.

A set of predefined parameters are available in `enb.config.options`, the single instance
of the :class:`enb.config.AllOptions` class.

Your code can then access and modify those global options programmatically with code like

.. code-block::python
    from enb.config import options


When running a script that import enb.config, "-h" can be passed as argument to show
a full help message.