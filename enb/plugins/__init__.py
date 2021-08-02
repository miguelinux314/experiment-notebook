#!/usr/bin/env python3
"""The core functionality of enb is extended by means of plugins and templates. These derive from Installable,
a class that by default copies the Installable's source contents and runs the subclass' build() method.
Python libraries available via pip can be defined for Installables, which are attempted to be satisfied before invoking
the build method.

Plugins are conceived self-contained, python modules that can assume the enb library is installed.

- They can be installed into your projects via the enb CLI (e.g., with `enb plugin install <name> <clone_dir>`),
  and then imported like any other module.

- The list of plugins available off-the-box can be obtained using the enb CLI (e.g., with `enb plugin list`).

- Plugins may declare pip dependencies, which are attempted to be satisfied automatically when the plugins
  are installed. In addition, plugins may define their `extra_requirements_message` member to be not None,
  in which case it describes manual intervention required from the user either as a pre-installation
  or post-installation step. That message is shown when attempting to install the plugin with
  not-None `extra_requirements_message`.

- The __init__.py file is automatically generated and should not be present in the source plugin folder.

Templates are very similar to plugins, with a few key differences:

- Templates may require so-called fields in order to produce output.
  Templates without required fields are tagged as "snippet".

- One or more templates can be installed into an existing directory.

- Templates automatically interpret any *.enbt file as a template. The jinja library is used to
  process them, and the resulting files are renamed removing '.enbt' from their name.
"""
import importlib
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


class Installable:
    """Common interface to all Installable types, e.g., Plugins and Templates.
    """
    # Human friendly, expectedly unique name for the Installable
    name = None
    # Human-friendly short phrase describing the Installable.
    label = None
    # Author of the enb Installable - by default it's us, the enb team.
    # Subclasses may update this as necessary.
    author = "The enb team"
    # List of string to provide soft categorization
    tags = []

    # List of pip-installable python module names required by this Installable.
    # Subclasses must overwrite this member as necessary.
    # Can be empty if needed.
    required_pip_modules = []

    # Message shown to users when installing the Installable. It can inform about any additional
    # external software needed for this Installable to work. Typically, Installables inform about
    # apt/pacman/... requirements for the Installables to work.
    # NOTE: the equivalent to build-essential and cmake are expected by most make-based Installables.
    extra_requirements_message = None

    # Information about external ("contrib") software used by the Installable
    # Author(s) of the external software
    contrib_authors = []
    # Reference URL(s) of the external software used by the Installable
    contrib_reference_urls = []
    # List of (url, name) tuples with contents needed for retrieving and building the external software.
    # Each url must be a valid downloadable link, and name is the name set to the downloaded file
    # inside the installation dir.
    contrib_download_url_name = []

    # Indicates on what platforms this Installable is known to work.
    # Can contain zero, one, or more among "linux", "darwin", "windows".
    tested_on = set()

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False):
        """Install this Installable into installation_dir.

        :param overwrite_destination: if True, if the destination exists prior to this call,
          it is removed before installation
        """
        installation_dir = os.path.abspath(installation_dir)

        print(f"Installing {cls.name} into {installation_dir}...")

        # Warn about any manual requirements reported by the plugin
        if cls.extra_requirements_message:
            print("\tNote: The plugin contains the following message regarding additional requirements:\n")
            print(textwrap.indent(textwrap.dedent(cls.extra_requirements_message).strip(), '\t'))
            print()

        # Create output dir if needed and copy Installable contents
        if overwrite_destination and os.path.exists(installation_dir):
            try:
                shutil.rmtree(installation_dir)
            except NotADirectoryError:
                os.remove(installation_dir)
        if not os.path.exists(installation_dir):
            os.makedirs(os.path.dirname(installation_dir), exist_ok=True)

        shutil.copytree(os.path.dirname(os.path.abspath(inspect.getfile(cls))), installation_dir,
                        dirs_exist_ok=True)

        # Install any specified pip modules - subprocess is the officially recommended way
        if cls.required_pip_modules:
            invocation = f"{sys.executable} -m pip install {' '.join(cls.required_pip_modules)}"
            print(f"Installing pip dependencies of {cls.name} with {repr(invocation)}...")
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Error installing {cls.name} dependencies ({cls.required_pip_modules}). "
                                f"Status = {status} != 0.\nInput=[{invocation}].\nOutput=[{output}]")

        # Download any needed external packages before the build
        for url, name in cls.contrib_download_url_name:
            output_path = os.path.join(installation_dir, name)
            print(f"Downloading {url} into {output_path}...")
            with open(output_path, "wb") as output_file:
                output_file.write(requests.get(url, allow_redirects=True).content)

        # Custom building of the Installable
        print(f"Building {cls.name} into {installation_dir}...")
        cls.build(installation_dir=installation_dir)

    @classmethod
    def build(cls, installation_dir):
        """Method called after the main installation body, that allows further building customization
        by Installable subclasses. By default, nothing is done.

        Note that the installation dir is created before calling build.
        """
        pass

    @classmethod
    def repr(cls):
        """Get a terse representation of this Installable.
        """
        return f"{cls.__name__}(" + \
               ", ".join(f"{k}={v}" for k, v in sorted(cls.__dict__.items())
                         if not k.startswith("_")
                         and not callable(v)
                         and not inspect.ismethoddescriptor(v)) + \
               ")"

    @classmethod
    def get_help(cls):
        """Return help about this Installable.
        By default, the docstring of the selected class is returned.
        """
        return textwrap.dedent(cls.__doc__)


class Plugin(Installable):
    """Plugins are self-contained, python modules that may assume enb is installed.

    - They can be installed into your projects via the enb CLI (e.g., with `enb plugin install <name> <clone_dir>`),
      and then imported like any other module.

    - The list of plugins available off-the-box can be obtained using the enb CLI (e.g., with `enb plugin list`).

    - Plugins may declare pip dependencies, which are attempted to be satisfied automatically when the plugins
      are installed. In addition, plugins may define their `extra_requirements_message` member to be not None,
      in which case it describes manual intervention required from the user either as a pre-installation
      or post-installation step. That message is shown when attempting to install the plugin with
      not-None `extra_requirements_message`.

    - The __init__.py file is automatically generated and should not be present in the source plugin folder.
    """

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False):
        """Make a copy of this plugin into installation_dir, ready to be imported.
        By default, a verbatim copy of the source plugin's dir is made.
        Any previous contents in installation_dir are overwritten.
        Then any explicit requirements are met (external software may be downloaded
        and pip packages installed).

        :param overwrite_destination: if True, the destination path is deleted before
          installation. If False and installation_dir already exists, an error
          is raised (plugins are intended to be self-contained, isolated python modules).
        """
        if not overwrite_destination and os.path.exists(installation_dir):
            raise ValueError(f"Plugin {repr(cls)} cannot be installed into existing "
                             f"path {installation_dir} because "
                             f"overwrite_destination={overwrite_destination}.")
        super().install(installation_dir=installation_dir,
                        overwrite_destination=True)

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

        # cleanup
        shutil.rmtree(os.path.join(installation_dir, "__pycache__"), ignore_errors=True)

        # add custom __init__
        with open(os.path.join(installation_dir, "__init__.py"), "w") as init_file:
            for py_path in [p for p in glob.glob(os.path.join(installation_dir, "*.py"))
                            if not os.path.basename(p).startswith("__")]:
                module_name = os.path.basename(py_path)[:-3]
                init_file.write(f"from . import {module_name}\n")
                init_file.write(f"from .{module_name} import *\n\n")


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


def import_all_installables():
    """Import all public enb plugins. These are recognized by containing a __plugin__.py file in
    them and a installable definition.

    Note that this call needs to be deferred in a function so that
    the plugins themselves can use the classes defined here, e.g., Plugin.
    """
    for plugin_path in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "**", "__plugin__.py"),
                                 recursive=True):
        plugin_path = os.path.abspath(plugin_path)
        module_name = "enb.plugins"
        module_name += ".".join(plugin_path.replace(os.path.dirname(os.path.abspath(__file__)), "").split(
            os.sep)).replace(".__plugin__.py", ".__plugin__")
        importlib.import_module(module_name)


def list_all_installables(ignored_classes=[Plugin, PluginMake]):
    """Get a list of all known enb installables, sorted by name.
    """
    import_all_installables()
    return sorted([cls for cls in enb.misc.get_all_subclasses(Installable)
                   if cls not in ignored_classes],
                  key=lambda c: c.name.lower())
