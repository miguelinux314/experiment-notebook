#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "18/09/2019"

import os
import glob
import ast
import configparser
import textwrap

import enb
from ..misc import Singleton as _Singleton


class Ini(metaclass=_Singleton):
    """Class of the enb.config.ini object, that exposes file-defined configurations.
    """
    global_ini_path = os.path.join(enb.enb_installation_dir, "config", "enb.ini")
    user_ini_path = os.path.join(enb.user_config_dir, "enb.ini")
    local_ini_paths = sorted(glob.glob(os.path.join(enb.calling_script_dir, "*.ini")),
                             key=lambda s: os.path.basename(s).lower())

    def __init__(self):
        super().__init__()
        # Keep track of what config files have been used to get the final result
        self.used_config_paths = []

        # Parse configuration files with the specified prioritization
        self.config_parser = configparser.ConfigParser()
        self.update_from_path(self.global_ini_path)
        if os.path.exists(self.user_ini_path):
            self.update_from_path(self.user_ini_path)
        for ini_path in self.local_ini_paths:
            self.update_from_path(ini_path)

    def update_from_path(self, ini_path):
        """Update the current configuration by reading the contents of ini_path.
        """
        self.config_parser.read(ini_path)
        self.used_config_paths.append(ini_path)

    def get_key(self, section, name):
        """Return a read key value in the given section (if existing),
        after applying ast.literal_eval on the value.
        """
        return ast.literal_eval(self.config_parser[section][name])

    @property
    def sections_by_name(self):
        """Get a list of all configparser.Section instances, including the default section.
        """
        return list(self.config_parser.items())

    def __repr__(self):
        s = "File-based configuration for enb, originally read in this order:\n  - "
        s += "\n  - ".join(self.used_config_paths)
        s = textwrap.indent(s, "# ")
        for section_name, section in sorted(ini.sections_by_name):
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
