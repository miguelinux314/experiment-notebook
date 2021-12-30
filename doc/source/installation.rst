.. installation

Installation
============

This page provides help on how to install `enb` in a single computer.

Instructions are provided for Linux, Windows and Mac.

If you want to set up a cluster of multiple computers for distributed
execution of your experiments, see :doc:`cluster_setup`.

Linux
-----

The `enb` library and all its dependencies are available by default in most Linux distributions.

You may install it easily with pip,

.. code-block:: bash

   pip install enb

or, if you don't have root's privileges:

.. code-block:: bash

  pip install enb --user

Windows and MacOS
-----------------

The `enb` library is also available on Windows and MacOS via pip.

You will typically need to follow these steps to have `enb` working on your box:

    1. `Download <https://docs.ray.io/en/master/installation.html>`_ the `ray` python library
       *for the python version you want to use* (a `.whl` file).
       (a dependency of the library).

    2. Install the ray library, e.g.,

        .. code-block:: bash

            pìp install -U ray-2.0.0.dev0-cp38-cp38-macosx_10_13_x86_64.whl

    3. Install `enb` via pip, e.g.,

        .. code-block:: bash

            pip install enb --user

The pip command must correspond to the python version for which ray was installed.


.. note ::

  If you are developing for enb, it is highly recommended to used a virtual environment.
  To do so, for instance for python3.8, the complete setup would be:

        .. code-block:: bash

            /usr/bin/python3.8 -m venv venv # run only once
            source venv/bin/active          # run once per session
            pip install -U ray-2.0.0.whl    # run once
            pip install enb                 # run once. Applies to this venv

  You can change python3.8 to 3.6 or newer, according to the version installed in your system.


.. note:: Initialization of the `ray` library (used for parallelization) can take a few
  seconds on Windows machines.

Sources and development version
-------------------------------

.. note:: You may safely skip this section unless you intend to study or develop `enb`.

To get the latest version of enb, you can clone the enb with

.. code-block:: bash

    git clone https://github.com/miguelinux314/experiment-notebook.git
    cd experiment-notebook.git

You can access the development version with

.. code-block:: bash

    git clone https://github.com/miguelinux314/experiment-notebook.git
    cd experiment-notebook.git
    git checkout dev

You can install a symbolic link to your local copy of the code (for whichever
branch is checked out) with

.. code-block:: bash

    git clone https://github.com/miguelinux314/experiment-notebook.git
    cd experiment-notebook.git
    pip install -e .

Feel free to submit pull_requests for your desired contributions.
