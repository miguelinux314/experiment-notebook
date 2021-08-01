#!/usr/bin/env python3
"""The core functionality of enb is extended by means of plugins.
Plugins are self-contained, python modules that may assume enb is installed.

They can be cloned into your projects via the enb CLI (e.g., with `enb plugin clone <name> <clone_dir>`),
and then imported like any other module. This performs any needed installation (it may require
some user interaction, depending on the plugin).

The list of plugins available off-the-box can be obtained using the enb CLI (e.g., with `enb plugin list`).
"""

import os
import sys
import glob
import inspect
import shutil
import requests
import platform
import subprocess
import textwrap
import enb.misc


class Plugin:
    """To create new plugins:

     - Create a folder with one file in it:__plugin__.py
     - In the __plugin__.py file, import enb and define a subclass of enb.plugin.pluginPlugin.
       Then overwrite existing class attributes as needed.
       You cna overwrite the build method if anything besides python packages is required.

    The Plugin class and subclasses are intended to help reuse your code,
    not to implement their functionality. Meaningful code should be added
    to regular .py scripts into the plugin folder, and are in no other
    way restricted insofar as enb is concerned.

    The __init__.py file is automatically generated and should not be present in the source plugin folder.
    """
    # Human friendly, unique name for the plugin
    name = None
    # Human-friendly short phrase describing this module.
    label = None

    # Author of the enb plugin - by default it's us. Subclasses may update this as necessary.
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
    required_pip_modules = []

    # Message shown to users when installing the plugin. It can inform about any additional
    # external software needed for this plugin to work. Typically, plugins inform about
    # apt/pacman/... requirements for the plugins to work.
    # NOTE: the equivalent to build-essential and cmake are expected by most make-based plugins.
    extra_requirements_message = None

    # Indicates on what platforms this plugin is known to work.
    # Can contain zero, one, or more among "linux", "darwin", "windows".
    tested_on = set()

    # List of string to provide soft categorization
    tags = []

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

        # Create output dir and copy plugin contents
        shutil.rmtree(installation_dir, ignore_errors=True)
        shutil.copytree(os.path.dirname(inspect.getfile(cls)), installation_dir)

        # Download any needed external packages before the build
        for url, name in cls.contrib_download_url_name:
            output_path = os.path.join(installation_dir, name)
            print(f"Downloading {url} into {output_path}...")
            with open(output_path, "wb") as output_file:
                output_file.write(requests.get(url, allow_redirects=True).content)

        print(f"Building {cls.name}...")
        cls.build(installation_dir=installation_dir)

    @classmethod
    def build(cls, installation_dir):
        """Perform any additional retrieval, compilation and setup necessary for this plugin
        to be importable and usable.
        By default:
            - The existence of installation_dir as a directory is performed.
            - Install any required apt modules
            - Any needed python modules are installed via pip
            - Cleanup any generic files that might not be needed at this point
            - The __init__.py file is generated automatically
        """
        # Existence assertion
        assert os.path.isdir(installation_dir), \
            f"{cls.__name__}.build(installation_dir={repr(installation_dir)}): installation_dir does not exist"

        # pip module installation - note that subprocess is the officially recommended way
        if cls.required_pip_modules:
            invocation = f"{sys.executable} -m pip install {' '.join(cls.required_pip_modules)}"
            print(f"Installing pip dependencies of {cls.name} with {repr(invocation)}...")
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Error installing {cls.name} dependencies ({cls.required_pip_modules}). "
                                f"Status = {status} != 0.\nInput=[{invocation}].\nOutput=[{output}]")

        # cleanup
        shutil.rmtree(os.path.join(installation_dir, "__pycache__"), ignore_errors=True)

        # add custom __init__
        with open(os.path.join(installation_dir, "__init__.py"), "w") as init_file:
            for py_path in [p for p in glob.glob(os.path.join(installation_dir, "*.py"))
                            if not os.path.basename(p).startswith("__")]:
                module_name = os.path.basename(py_path)[:-3]
                init_file.write(f"from . import {module_name}\n")
                init_file.write(f"from .{module_name} import *\n\n")

        if cls.extra_requirements_message:
            print("\tNote: The plugin contains the following message regarding additional requirements:\n")
            print(textwrap.indent(textwrap.dedent(cls.extra_requirements_message).strip(), '\t'))
            print()

    @classmethod
    def repr(cls):
        return f"{cls.__name__}(" + \
               ", ".join(f"{k}={v}" for k, v in sorted(cls.__dict__.items())
                         if not k.startswith("_")
                         and not callable(v)
                         and not inspect.ismethoddescriptor(v)) + \
               ")"

    @classmethod
    def get_help(cls):
        """By default, return the docstring of the selected class.
        """
        return cls.__doc__


class PluginMake(Plugin):
    """Plugin that assumes the existence of a valid Makefile in the installation folder,
    and uses it for building the plugin.
    """

    @classmethod
    def build(cls, installation_dir):
        super().build(installation_dir=installation_dir)
        platform_name = platform.system().lower()
        make_path = os.path.join(installation_dir, f"Makefile.{platform_name}")
        if not os.path.exists(make_path):
            make_path = os.path.join(installation_dir, f"Makefile")
        if os.path.exists(make_path):
            print(f"Building downloaded plugin {cls.name}...")
            invocation = f"cd {os.path.dirname(os.path.abspath(make_path))} && make -f {os.path.basename(make_path)}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Error bulding {repr(cls)} with {make_path}. "
                                f"Status = {status} != 0."
                                f"\nInput=[{invocation}].\nOutput=[{output}]")
        else:
            raise ValueError(f"Cannot build {repr(cls)}: no valid makefile "
                             f"in {installation_dir}.")


def import_all_plugins():
    """Import all public enb plugins.

    Note that this call needs to be deferred in a function so that
    the plugins themselves can use the classes defined here, e.g., Plugin.
    """
    from .plugin_ccsds122 import __plugin__
    from .plugin_fapec import __plugin__
    from .plugin_fpack import __plugin__
    from .plugin_flif import __plugin__
    from .plugin_fpc import __plugin__
    from .plugin_fpzip import __plugin__
    from .plugin_fse_huffman import __plugin__
    from .plugin_hevc import __plugin__
    from .plugin_hdf5 import __plugin__
    from .plugin_jpeg import __plugin__
    from .plugin_kakadu import __plugin__
    from .plugin_lcnl import __plugin__
    from .plugin_lz4 import __plugin__
    from .plugin_marlin import __plugin__
    from .plugin_mcalic import __plugin__
    from .plugin_ndzip import __plugin__
    from .plugin_spdp import __plugin__
    from .plugin_vvc import __plugin__
    from .plugin_zfp import __plugin__
    from .plugin_zip import __plugin__
    from .plugin_zstandard import __plugin__
    from .test_all_codecs import __plugin__


def list_all_plugins():
    """Get a list of all known enb plugins.
    """
    import_all_plugins()
    return sorted([cls for cls in enb.misc.get_all_subclasses(Plugin) if cls not in [PluginMake]],
                  key=lambda c: c.name.lower())
