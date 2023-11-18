.. installation

Installation
============

This page provides help on how to install `enb` in a single computer.

Instructions are provided for:

* Linux
* Mac OS, Windows
* RaspberryOS (Raspberry Pi)

If you want to set up a cluster of multiple computers for distributed
execution of your experiments, see :doc:`cluster_setup`.

Linux
-----

Basic installation
^^^^^^^^^^^^^^^^^^

The `enb` library and all its dependencies are available by default in most Linux distributions.

You may install it easily with pip,

.. code-block:: bash

   pip install enb

.. note::

    You might need to call the following instead if you are not using a virtual environment or
    and you don't have root privileges:

    .. code-block:: bash

          pip install enb --user

Plugin installation
^^^^^^^^^^^^^^^^^^^

The `enb` library comes with many installable plugins and project templates.
After you complete the basic installation of `enb`, you can use its command line interface
to install them (see :doc:`command_line_interface` for more details).

In several cases, plugins consist of source code that needs to be compiled before using the plugin.
Therefore, you might need to install tools such as `make`, `cmake`, `gcc`, `g++`, etc.
In Debian-based systems like Ubuntu, you might want to install `build-essential` and `cmake`, which allow
the compilation of most plugins:

.. code-block:: bash

    sudo apt install build-essential cmake

Additional information on plugins specific for image compression is provided in :doc:`image_compression_codecs`.

Cluster installation
^^^^^^^^^^^^^^^^^^^^

If you would like multi-computer parallelization, please install the `ray` python library as well
as the `ssh` (server and client), `sshfs` and `vde2` (for the `dpipe` command) packages.

On Debian, Ubuntu and derivatives this can be achieved by:

.. code-block:: bash

    pip install ray[default]
    sudo apt install openssh-client openssh-server sshfs vde2

The `enb` library will show a warning and proceed locally if any of these tools are not available.
Please see :doc:`cluster_setup` for full information on how to set up a cluster.


Windows and MacOS
-----------------

Installation of `enb` for Windows and MacOS can be performed via pip:

.. code-block:: python

    pip install enb

You might need to install `python` and the `pip` system manually. The following related (external) resources
might be of help:

* `Python installer download <https://www.python.org/downloads/>`_
* `Creation of virtual environments on Windows <https://docs.python.org/3/library/venv.html>`_
* `Python installation and virtual environment setup on MacOS <https://sourabhbajaj.com/mac-setup/Python/virtualenv.html>`_

To install some of the plugins available in `enb`, you may need additional tools such as `make`, `cmake`, `gcc`, etc:
In MacOS, you might want to use Homebrew (`https://brew.sh/`) and/or `xcode-select --install`.


Raspberry Pi
------------
Installation on RaspberryOS is identical to that of other Linux distributions, but requires manual installation
of some packages.

It is recommended to install the system versions of the following packages:

.. code-block:: bash

   sudo apt install python3-{matplotlib,scipy,numpy,pandas}

And then configure a virtual environment with the `--system-site-packages` flag, e.g.,

.. code-block:: bash

    python -m venv --system-site-packages ~/venv

.. note::

    You might need to install specific versions of some packages. For instance, if you get the following error:

    .. code-block:: text

        ImportError: Pandas requires version '3.0.0' or newer of 'jinja2' (version '2.11.3' currently installed).

    Then you may need to run

    .. code-block:: bash

        pip install --force jinja2==3.0.0


Sources and development version
-------------------------------

.. note:: You may safely skip this section unless you intend to study or develop `enb`.

To get the latest version of enb, you can clone `enb` with

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

To update your repository, simply go into your `experiment-notebook.git` folder and type

.. code-block:: bash

    git pull

Feel free to `submit pull_requests <https://github.com/miguelinux314/experiment-notebook/pulls>`_
for your desired contributions.

.. warning::

    The development version is discouraged for inexperienced users.
    These are advised to employ the latest stable version.
    Don't forget to report in github any bugs you would like removed.
