Installation
============

Linux
-----

The `enb` library and all its dependencies are available by default in most Linux distributions.

You may install it easily with pip,

.. code-block:: bash

   pip install enb

or, if you don't have root's privileges:

.. code-block:: bash

  pip install enb --user


Windows
-------

The `enb` library is also available via pip.

You will typically need to follow these steps to have `enb` working on your Windows box:

    1. `Install <https://docs.ray.io/en/master/installation.html>`_ the `ray` python library (a dependency of the library)
    2. Install `enb` via pip, e.g.,

.. code-block:: bash

    pip install enb --user

.. note:: Initialization of the `ray` library (used for parallelization) can take a few
  seconds on Windows machines. Actual execution of `enb` code typically takes about the
  same time on both Windows and Linux machines.
