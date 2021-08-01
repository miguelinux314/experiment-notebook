#!/usr/bin/env python3
"""The core functionality of enb is extended by means of plugins.
Plugins are self-contained, python modules that may assume enb is installed.

They can be cloned into your projects via the enb CLI (e.g., with `enb plugin clone <name> <clone_dir>`),
and then imported like any other module. This performs any needed installation (it may require
some user interaction, depending on the plugin).

The list of plugins available off-the-box can be obtained using the enb CLI (e.g., with `enb plugin list`).
"""

import os
import inspect
import shutil
import requests

from enb.config import options

class Plugin:
    """To create new plugins:

     - Create a folder with two files in it: __init__.py and __plugin__.py
     - In the __plugin__.py file, import enb and define a subclass of enb.plugin.pluginPlugin.
       Then overwrite existing class attributes as needed.
       You cna overwrite the build method if anything besides python packages is required.

    The Plugin class and subclasses are intended to help reuse your code,
    not to implement their functionality. Meaningful code should be added
    to regular .py scripts into the plugin folder, and are in no other
    way restricted insofar as enb is concerned.

    The __init__.py file may import those symbols (assuming any needed installation has already been performed)
    and define __all__ to allow a clean import *.
    """
    # Human friendly, unique name for the plugin
    name = None
    # Human-friendly short phrase describing this module.
    label = None

    # Author of the plugin. Subclasses may update this as necessary.
    plugin_author = "The enb team"

    # Information about external ("contrib") software used by the plugin
    # Author(s) of the external software
    contrib_authors = []
    # Reference URL(s) of the external software
    contrib_reference_urls = []
    # List of (url, name) tuples with contents needed for retrieving and building the external software.
    # Each url must be a valid downloadable link, and name is the name set to the downloaded file
    # inside the installation dir.
    contrib_download_url_name = []

    # List of pip-installable python module names required by this plugin.
    # Subclasses must overwrite this member as necessary.
    # Can be empty if needed.
    required_module_names = []

    @classmethod
    def install(cls, installation_dir):
        """Make a copy of this plugin into destination_dir, ready to be imported.
        By default, a verbatim copy of the source plugin's dir is made.
        Any previous contents in installation_dir are overwritten.
        Then any explicit requirements are met (external software may be downloaded
        and pip packages installed).
        """
        print(f"Installing {cls.name} into {installation_dir}...")

        assert cls is not Plugin, f"{cls} cannot be cloned, only its subclasses."
        shutil.rmtree(installation_dir, ignore_errors=True)
        shutil.copytree(os.path.dirname(inspect.getfile(cls)), installation_dir)
        cls.build(installation_dir=installation_dir)
        shutil.rmtree(os.path.join(installation_dir, "__pycache__"), ignore_errors=True)
        for url, name in cls.contrib_download_url_name:
            with open(os.path.join(installation_dir, name), "wb") as output_file:
                output_file.write(requests.get(url, allow_redirects=True).content)

    @classmethod
    def build(cls, installation_dir):
        """Perform any additional retrieval, compilation and setup necessary for this plugin
        to be importable and usable.
        By default:
            1. The existence of installation_dir as a directory is performed.
            2. Any needed python modules are installed via pip
        """
        assert os.path.isdir(installation_dir), \
            f"{cls.__name__}.build(installation_dir={repr(installation_dir)}): installation_dir does not exist"

    @classmethod
    def repr(cls):
        return f"{cls.__name__}(" + \
               ", ".join(f"{k}={v}" for k, v in sorted(cls.__dict__.items())
                         if not k.startswith("_")
                         and not callable(v)
                         and not inspect.ismethoddescriptor(v)) + \
               ")"


def import_all_plugins():
    # All plugins intended to be visible should be defined in modules imported here
    from .plugin_ccsds122 import __plugin__
    from . import plugin_fapec
    from . import plugin_fits
    from . import plugin_flif
    from . import plugin_fpack
    from . import plugin_fpc
    from . import plugin_fpzip
    from . import plugin_fse_huffman
    from . import plugin_hevc
    from . import plugin_hdf5
    from . import plugin_jpeg
    from . import plugin_jpeg_xl
    from . import plugin_kakadu
    from . import plugin_lcnl
    from . import plugin_lz4
    from . import plugin_marlin
    from . import plugin_mcalic
    from . import plugin_ndzip
    from . import plugin_spdp
    from . import plugin_vvc
    from . import plugin_zip
    from . import plugin_zstandard


def list_all_plugins():
    """Get a list of all known enb plugins.
    """
    import_all_plugins()
    return Plugin.__subclasses__()
