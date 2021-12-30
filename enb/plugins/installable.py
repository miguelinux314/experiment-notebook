#!/usr/bin/env python3
"""Installable interface used for plugins and templates.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import builtins
import os
import sys
import glob
import collections
import importlib
import inspect
import shutil
import requests
import subprocess
import textwrap
import collections
import enb.misc


class InstallableMeta(type):
    """Installable classes are not meant to be instantiated, just to be defined to declare
    the presence of Installables. This metaclass is used to perform basic checks on the
    declared Installable subclasses.
    """
    installable_file_name = "__plugin__.py"
    valid_tested_on_strings = {"linux", "macos", "windows"}

    # Stores all defined Installables by name
    name_to_installable = dict()
    # Stores all defined Installables by tag
    tag_to_installable = collections.defaultdict(list)

    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cls.name = cls.name.lower().strip() if cls.name else None
        if cls.name is not None:
            if cls.name in InstallableMeta.name_to_installable:
                raise SyntaxError(f"Installable {repr(cls)} contains a non-unique name {repr(cls.name)}.")
            else:
                InstallableMeta.name_to_installable[cls.name] = cls
        cls.label = cls.label.strip() if cls.label else cls.label
        cls.label = None if not cls.label else cls.label
        cls.authors = [a.strip() for a in cls.authors] if cls.authors else cls.authors
        cls.authors = [] if cls.authors is None else cls.authors
        cls.tags = {t.lower().strip() for t in cls.tags}
        for t in cls.tags:
            InstallableMeta.tag_to_installable[t].append(cls)

        if not all(s in cls.valid_tested_on_strings for s in cls.tested_on):
            raise SyntaxError(f"Invalid definition of {cls}: "
                              f"tested_on={repr(cls.tested_on)} contains invalid elements "
                              f"not in {repr(cls.valid_tested_on_strings)}.")

        if cls.extra_requirements_message is None and "privative" in cls.tags:
            cls.extra_requirements_message = """
            Neither source code nor binaries of this plugin can be distributed by enb. 
            It will be essentially useless unless you can provide the appropriate binaries.
            """


class Installable(metaclass=InstallableMeta):
    """Common interface to all Installable types, e.g., Plugins and Templates.
    """
    # Human friendly, expectedly unique name for the Installable
    name = None
    # Human-friendly short phrase describing the Installable.
    label = None
    # Authors of the enb Installable - by default it's the main enb maintainer.
    # Subclasses may update this as necessary.
    authors = ["Miguel Hernández-Cabronero"]
    # List of string to provide soft categorization
    tags = {}

    # Information about external ("contrib") software used by the Installable
    # Author(s) of the external software
    contrib_authors = []
    # Reference URL(s) of the external software used by the Installable
    contrib_reference_urls = []
    # List of (url, name) tuples with contents needed for retrieving and building the external software.
    # Each url must be a valid downloadable link, and name is the name set to the downloaded file
    # inside the installation dir.
    contrib_download_url_name = []

    # List of pip-installable python module names required by this Installable.
    # Subclasses must overwrite this member as necessary.
    # Can be empty if needed.
    required_pip_modules = []

    # Message shown to users when installing the Installable. It can inform about any additional
    # external software needed for this Installable to work. Typically, Installables inform about
    # apt/pacman/... requirements for the Installables to work.
    # In general, if extra_requirements_message is not None, the installation process cannot be assumed
    # to be completed automatically without user intervention.
    #
    # NOTE: the equivalent to build-essential and cmake are expected by most make-based Installables,
    # e.g., PluginMake subclasses.
    extra_requirements_message = None

    # Indicates on what platforms this Installable is known to work.
    # Can contain zero, one, or more among "linux", "darwin", "windows".
    tested_on = set()

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False):
        """Install this Installable into installation_dir. By default, copy all contents
        of the Installable's source dir and install the declared pip requirements.

        :param overwrite_destination: if True, if the destination exists prior to this call,
          it is removed before installation
        """
        installation_dir = os.path.abspath(installation_dir)

        print(f"Installing {cls.name} into {installation_dir}...")

        # Warn about any manual requirements reported by the Installable
        if cls.extra_requirements_message:
            print("\tNote: This plugin contains the following message regarding additional requirements:\n")
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

        shutil.copytree(os.path.dirname(os.path.abspath(inspect.getfile(cls))), installation_dir)

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


def import_all_installables():
    """Import all public enb Installables.

    These are recognized by containing a __plugin__.py file in
    them and a installable definition.
    """

    for plugin_path in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "**",
                                              Installable.installable_file_name),
                                 recursive=True):
        # Compute the module import name
        plugin_path = os.path.abspath(plugin_path)
        module_name = "enb.plugins"
        module_name += ".".join(plugin_path.replace(os.path.dirname(os.path.abspath(__file__)), "").split(
            os.sep)).replace(f".{Installable.installable_file_name}", f".{Installable.installable_file_name[:-3]}")

        # Importing of the __plugin__.py (installable_file_name) module
        # will fail if there is an __init__.py present which attempts to import
        # any of the external dependencies. Therefore, a more lenient version of import is used for importing the module
        original_import = builtins.__import__

        def tolerant_import(*args, **kwargs):
            try:
                return original_import(*args, **kwargs)
            except ImportError:
                print(f"Ignoring import error in {os.path.basename(os.path.dirname(plugin_path))} "
                      f"for module {args[0]}. ")

        try:
            builtins.__import__ = tolerant_import
            importlib.import_module(module_name)
        finally:
            builtins.__import__ = original_import


def list_all_installables(base_class=Installable, ignored_classes=[]):
    """Get a list of all known enb installables, sorted by name.

    :param base_class: base class used for search, e.g. Installable to search for all defined installables.
    :param ignored_classes: classes to be excluded from the returned list. In addition to these, any
      installable with name set to None is also excluded
    """
    import_all_installables()
    return sorted([cls for cls in enb.misc.get_all_subclasses(base_class)
                   if cls not in ignored_classes
                   and cls.name is not None],
                  key=lambda c: c.name.lower())


def get_installable_by_name(name):
    """Search among all defined installables for one with exactly the name provided.
    :param name: name of the installable
    :raises KeyError: if name cannot be found
    """
    for installable in list_all_installables():
        if installable.name == name:
            return installable
    raise KeyError(f"Cannot find installable {repr(name)}")


# Lean description of the intention of each tag.
tag_to_description = collections.OrderedDict()
tag_to_description["documentation"] = "Documentation examples referenced in the user manual"
tag_to_description["codec"] = "Data compression/decompression class definitions"
tag_to_description["data compression"] = "Data compression tools"
tag_to_description["template"] = "Templates formatteable into the installation dir"
tag_to_description["project"] = "Project templates, including configuration files"
tag_to_description["test"] = "Plugins for testing purposes"
tag_to_description["privative"] = "Plugins requiring additional privative software"
