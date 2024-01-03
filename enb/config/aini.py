#!/usr/bin/env python3
"""
Automatic file-based configuration login based on the INI format.

The enb framework supports configuration files with `.ini` extension and format
compatible with python's configparser (https://docs.python.org/3/library/configparser.html#module-configparser),
e.g., similar to Window's INI files.

File-based configuration is used to determine the default value of enb.config.options and its CLI.
Furthermore, users may easily extend file-based configuration to their own needs.

When enb is imported, the following configuration files are read, in the given order.
Order is important because read properties overwrite any previously set values.

1. The `enb.ini` file provided with the enb library installation.

2. The `enb.ini` at the user's enb configuration dir. This path will be determined using the appdirs library,
   and will depend on the OS. In many linux boxes, this dir is `~/.config/enb`.

3. All `*.ini` files defined in the same folder as the called script, in lexicographical,
   case ignorant, order. No recursive folder search is performed.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/09/18"

import argparse
import os
import sys
import itertools
import glob
import ast
import configparser
import textwrap

from .. import calling_script_dir, is_enb_cli, enb_installation_dir, user_config_dir
from ..misc import Singleton as _Singleton, class_to_fqn, BootstrapLogger


class AdditionalIniParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(add_help=False)
        self.add_argument("--extra_ini_paths", "--ini", nargs="+", required=False, default=[])

    def get_extra_ini_paths(self):
        extra_ini_paths = []
        parsed_options, remaining_options = self.parse_known_args()

        if is_enb_cli:
            # The --ini option is not documented in the main enb CLI for simplicity. Remove it once
            # it has been used to avoid any parsing error
            sys.argv = sys.argv[0:1] + remaining_options

        for path in parsed_options.extra_ini_paths:
            if not os.path.exists(path):
                raise SyntaxError("Input ini path {path} does not exist. Run with -h for help.")
            extra_ini_paths.append(os.path.abspath(path))
        return extra_ini_paths


class Ini(metaclass=_Singleton):
    """Class of the enb.config.ini object, that exposes file-defined configurations.
    """
    global_ini_path = os.path.join(enb_installation_dir, "config", "enb.ini")
    user_ini_path = os.path.join(user_config_dir, "enb.ini")
    local_ini_paths = sorted(glob.glob(os.path.join(calling_script_dir, "*.ini")),
                             key=lambda s: os.path.basename(s).lower())
    extra_ini_paths = AdditionalIniParser().get_extra_ini_paths()

    def __init__(self):
        super().__init__()
        # Keep track of what config files have been used to get the final result
        self.used_config_paths = []
        self.extra_ini_paths = self.extra_ini_paths if self.extra_ini_paths is not None else []

        # Parse configuration files with the specified prioritization
        self.config_parser = configparser.ConfigParser()
        self.update_from_path(self.global_ini_path)
        if os.path.exists(self.user_ini_path):
            self.update_from_path(self.user_ini_path)
        for ini_path in self.all_ini_paths:
            self.update_from_path(ini_path)

    @property
    def all_ini_paths(self):
        """Get a list of all used ini paths.
        """
        return tuple(itertools.chain(self.local_ini_paths, self.extra_ini_paths))

    def update_from_path(self, ini_path):
        """Update the current configuration by reading the contents of ini_path.
        """
        try:
            self.config_parser.read(ini_path)
            self.used_config_paths.append(ini_path)
        except configparser.ParsingError as ex:
            print(f"Found invalid ini path {ini_path} ({repr(ex).strip()}). "
                  f"Any configuration in this file will be ignored.")

    def get_key(self, section, name):
        """Return a read key value in the given section (if existing),
        after applying ast.literal_eval on the value to recognize any
        valid python literals (essentially numbers, lists, dicts, tuples, booleans and None).
        """
        try:
            # Attempt to interpret the string as a literal
            return ast.literal_eval(self.config_parser[section][name])
        except (SyntaxError, ValueError):
            # The key could not be parsed as a literal, it is returned as a string
            # (this is configparser's default)
            return self.config_parser[section][name]

    @property
    def sections_by_name(self):
        """Get a list of all configparser.Section instances, including the default section.
        """
        return dict(self.config_parser.items())

    def __repr__(self):
        s = "File-based configuration for enb, originally read in this order:\n  - "
        s += "\n  - ".join(self.used_config_paths)
        s = textwrap.indent(s, "# ")
        for section_name, section in sorted(ini.sections_by_name.items()):
            if not section:
                continue
            s += "\n\n"
            s += f"[{section_name}]\n\n"
            for k, v in sorted(section.items()):
                s += f"{k} = {v}\n"
        return s


# Export the ini object
ini = Ini()
assert ini is Ini(), "Singleton not working for enb.config.ini"


def managed_attributes(cls):
    """Decorator for classes so that their (class) attributes are set
    based on the `.ini` files found. Attributes starting with `_` are not considered.

    Values are read from the section titled as the classes fully qualified name
    (e.g., using the `[enb.aanalysis.ScalarValueAnalyzer]` header in one of the .ini files).

    Note that adding keys to that section corresponding to attributes not present
    in the definition of cls are ignored, i.e., new attributes are not added to cls.
    """
    try:
        # This import will work once the config submodule is finished loading
        from ..log import logger
    except ImportError:
        # Allow displaying messages conditionally while the config submodule is loading
        logger = BootstrapLogger()

    cls_fqn = class_to_fqn(cls)

    for attribute, old_value in ((k, v) for k, v in cls.__dict__.items()
                                 if not k.startswith("_")
                                    and not k == "column_to_properties"
                                    and not callable(v)
                                    and not isinstance(v, classmethod)
                                    and not isinstance(v, property)):
        try:
            setattr(cls, attribute, ini.get_key(cls_fqn, attribute))
            if getattr(cls, attribute) != old_value \
                    and str(getattr(cls, attribute)) != str(old_value):
                logger.debug(
                    f"Updating {cls_fqn}.{attribute} = {getattr(cls, attribute)} based on .ini files "
                    f"(it was {old_value})")
        except KeyError:
            found_in_bases = _add_base_attributes_recursively(attribute, cls)
            if not found_in_bases:
                logger.warn(f"The {cls_fqn} class is decorated with "
                            f"enb.ini.managed.attributes, but contains an attribute "
                            f"{repr(attribute)} which is not present in its configuration nor in any of "
                            f"its base classes. "
                            f"The class' default value in the python code definition of ({cls.__dict__[attribute]}) "
                            f"is used instead.")

    for k, v in ini.sections_by_name[cls_fqn].items():
        if not hasattr(cls, k):
            logger.warn(
                f"In the .ini configuration files, managed attribute {repr(k)} is defined for {cls_fqn}, "
                f"but {cls.__name__} itself does not define that class attribute. The attribute is NOT added "
                f"to {cls.__name__}.")

    return cls


def _add_base_attributes_recursively(attribute, base_cls, current_cls=None):
    """Given a class base_cls, attempt to get the value of attribute defined for any of its base classes,
    recursively.

    :param attribute: name of the attribute to be queried and potentially set.
    :param base_cls: class whose attribute is being managed.
    :param current_cls: used for recursion, it must be None when invoked outside this method.
    """
    if current_cls is None:
        current_cls = base_cls

    found_in_bases = False

    try:
        setattr(base_cls, attribute, ini.get_key(section=class_to_fqn(current_cls), name=attribute))
        found_in_bases = True
    except KeyError:
        for base in current_cls.__bases__:
            if base is None:
                continue
            if _add_base_attributes_recursively(attribute=attribute, base_cls=base_cls,
                                                current_cls=base):
                found_in_bases = True
                break

    return found_in_bases
