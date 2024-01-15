#!/usr/bin/env python3
"""Installable interface used for plugins and templates.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import builtins
import os
import sys
import glob
import importlib
import inspect
import shutil
import requests
import subprocess
import textwrap
import collections
import pandas as pd
import hashlib
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
            cls.extra_requirements_message = textwrap.dedent("""
            Neither source code nor binaries of this plugin can be distributed by enb. 
            It will be essentially useless unless you can provide the appropriate binaries.
            Typically, you will need to copy them directly into the plugin's installation folder.
            """).strip()
            try:
                cls.extra_requirements_message += (
                    "\nYou may want to visit " +
                    ", ".join(url for url in cls.contrib_reference_urls) +
                    " for additional information and/or the needed binaries.")
            except AttributeError:
                pass


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
    # Modules required by enb need not be added.
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
        """Install this Installable into `installation_dir`. By default, copy all contents
        of the Installable source dir and install the declared pip requirements.

        :param installation_dir: path where the installable is to be copied and, when necessary, built.
        :param overwrite_destination: if True, if the destination exists prior to this call,
            it is removed before installation.
        """
        installation_dir = os.path.abspath(installation_dir)

        enb.logger.message(f"Installing {repr(cls.name)} into {repr(installation_dir)}...")

        # Warn about any manual requirements reported by the Installable
        cls.warn_extra_requirements()

        # Create output dir if needed and copy Installable contents
        if overwrite_destination and os.path.exists(installation_dir):
            try:
                shutil.rmtree(installation_dir)
            except NotADirectoryError:
                os.remove(installation_dir)
        installation_dir_existed = os.path.exists(installation_dir)
        if not installation_dir_existed:
            os.makedirs(os.path.dirname(installation_dir), exist_ok=True)

        try:
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
            cache_dir = os.path.join(enb.user_config_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            for url, name in cls.contrib_download_url_name:
                output_path = os.path.join(installation_dir, name)
                cached_path = os.path.join(cache_dir, name)
                try:
                    if os.path.isfile(cached_path):
                        contrib_sha256_df = pd.read_csv(
                            os.path.join(enb.enb_installation_dir, "config", "contrib_sha256.csv"))
                        expected_sha256 = contrib_sha256_df[contrib_sha256_df["file"] == name]["sha256"].values[0]
                        hasher = hashlib.sha256()
                        with open(cached_path, "rb") as cached_file:
                            hasher.update(cached_file.read())
                        outdated_contrib = expected_sha256 != hasher.hexdigest()
                except (KeyError, IndexError):
                    outdated_contrib = False

                if not os.path.isfile(cached_path) or enb.config.options.force or outdated_contrib:
                    with enb.logger.verbose_context(f"Downloading {url} into cache"):
                        with open(cached_path, "wb") as output_file:
                            output_file.write(requests.get(url, allow_redirects=True).content)
                enb.logger.verbose(f"Copying {cached_path} into {output_path}"
                                   f"{' (run with -f to force download)' if enb.config.options.force else ''}")
                shutil.copyfile(cached_path, output_path)

            # Custom building of the Installable
            print(f"Building plugin {repr(cls.name)} into {repr(installation_dir)}...")
            cls.build(installation_dir=installation_dir)
            cls.report_successful_installation(installation_dir=installation_dir)
        except Exception as ex:
            if not installation_dir_existed:
                enb.logger.verbose(f"Removing incomplete installation dir {repr(installation_dir)}.")
                shutil.rmtree(installation_dir, ignore_errors=True)
            raise ex

    @classmethod
    def build(cls, installation_dir):
        """Method called after the main installation body, that allows further building customization
        by Installable subclasses. By default, nothing is done.

        Note that the installation dir is created before calling build.
        """
        pass

    @classmethod
    def report_successful_installation(cls, installation_dir):
        print(
            f"Successfully installed {repr(cls.name)} into {repr(os.path.abspath(installation_dir))}.")

    @classmethod
    def warn_extra_requirements(cls):
        if cls.extra_requirements_message:
            enb.logger.warn("This plugin contains the following message regarding additional requirements:\n")
            enb.logger.warn("\n".join(
                textwrap.indent(l, " " * 4)
                for line in textwrap.dedent(cls.extra_requirements_message).strip().splitlines()
                for l in textwrap.wrap(line, shutil.get_terminal_size()[0] - 10)))
            enb.logger.warn("")

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

    @classmethod
    def print_info(cls):
        """Print information about this installable.
        """
        indentation_string = " " * (7 + len(" :: "))
        if cls.authors:
            print(textwrap.indent
                  (f"* Plugin author{'s' if len(cls.authors) != 1 else ''}:",
                   indentation_string))
            for author in cls.authors:
                print(textwrap.indent(f"  - {author}", indentation_string))
        if cls.contrib_authors:
            print(textwrap.indent(
                f"* External software author{'s' if len(cls.contrib_authors) != 1 else ''}:",
                indentation_string))
            for author in cls.contrib_authors:
                print(textwrap.indent(f"  - {author}", indentation_string))
        if cls.contrib_reference_urls:
            print(textwrap.indent(
                f"* Reference URL{'s' if len(cls.contrib_reference_urls) != 1 else ''}:",
                indentation_string))
            for url in cls.contrib_reference_urls:
                print(textwrap.indent(f"  - {url}", indentation_string))
        if cls.contrib_download_url_name:
            print(textwrap.indent(
                f"* External software URL{'s' if len(cls.contrib_download_url_name) != 1 else ''}:",
                indentation_string))
            for url, name in cls.contrib_download_url_name:
                print(textwrap.indent(f"  - {url}", indentation_string))
                print(textwrap.indent(f"     -> <installation_dir>/{name}", indentation_string))
        if cls.required_pip_modules:
            print(textwrap.indent(f"* Automatically installed pip "
                                  f"{'libraries' if len(cls.required_pip_modules) > 1 else 'library'}:",
                                  indentation_string))
            for name in cls.required_pip_modules:
                print(textwrap.indent(f"  - {name}", indentation_string))
        if cls.extra_requirements_message:
            print(textwrap.indent(f"* WARNING: some requirements might need to be manually satisfied:",
                                  indentation_string))
            print(textwrap.indent(cls.extra_requirements_message.strip(),
                                  indentation_string + "    "))
        if cls.tags:
            print(textwrap.indent(f"* Tag{'s' if len(cls.tags) != 1 else ''}: "
                                  f"{', '.join(repr(t) for t in cls.tags)}",
                                  indentation_string))
        if cls.tested_on:
            print(textwrap.indent(f"* Tested on: {', '.join(sorted(cls.tested_on))}",
                                  indentation_string))
        print()


def install(name, target_dir=None, overwrite=False, automatic_import=True):
    """Install an Installable by name into target_dir.

    :param name: name of the installable (e.g., plugin) to be installed. Run `enb plugin list` in the CLI
      to get a list of all available installables.
    :param target_dir: If `target_dir` is None, it is set to `plugins/<plugin_name>` by default.
    :param overwrite: If overwrite is False and target_dir already exists, no action is taken.
    :param automatic_import: If True, the installable is imported as a module.
    """
    target_dir = os.path.join("plugins", name) if target_dir is None else target_dir
    if overwrite:
        shutil.rmtree(target_dir, ignore_errors=True)
    if not os.path.exists(target_dir):
        installable = get_installable_by_name(name=name)
        installable.install(installation_dir=target_dir, overwrite_destination=False)
    if automatic_import:
        importlib.import_module(".".join(target_dir.split(os.sep)))


def import_all_installables():
    """Import all public enb Installables.

    These are recognized by containing a __plugin__.py file in
    them and an installable definition.
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
tag_to_description["image"] = "Tools for image processing (including compression and analysis)"
tag_to_description["privative"] = "Plugins requiring additional privative software"
