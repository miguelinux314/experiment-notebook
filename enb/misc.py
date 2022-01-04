#!/usr/bin/env python3
"""Miscellaneous tools for `enb`.

This module does not and should not import anything from enb, so that other modules
may use misc tools at definition time.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/07/11"

import builtins
import os
import sys
import csv
import re
import contextlib
import socket


def get_defining_class_name(f):
    """Return the name of the class of which f is a method, or None if not bound to any class.
    """
    try:
        return f.__qualname__.split('.<locals>', 1)[0].rsplit('.')[-2]
    except IndexError:
        return None


def remove_argparse_action(parser, action):
    """Entirely remove an action from a parser, from its subparsers and groups if it exists.
    One wonders why this is not part of the default interface...

    Adapted from https://stackoverflow.com/a/49753634.
    """
    try:
        parser._remove_action(action)
    except ValueError:
        pass
    try:
        parser._actions.remove(action)
    except ValueError:
        pass

    for g in parser._action_groups:
        try:
            g._remove_action(action)
        except ValueError:
            pass
        try:
            g._actions.remove(action)
        except ValueError:
            pass
        try:
            g._group_actions.remove(action)
        except ValueError:
            pass

    a = action
    try:
        parser._remove_action(a)
    except ValueError:
        pass
    try:
        parser._actions.remove(a)
    except ValueError:
        pass

    for o in a.option_strings:
        try:
            del parser._option_string_actions[o]
        except KeyError:
            pass

    vars_action = vars(a)
    try:
        var_group_actions = vars_action['_group_actions']
    except KeyError:
        var_group_actions = None
    if var_group_actions is not None:
        for x in var_group_actions:
            if x.dest == arg:
                var_group_actions.remove(x)


def split_camel_case(camel_string):
    """Split a camel case string like ThisIsAClass into a string like "This Is A Class".
    """
    return " ".join(re.findall(r'[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))', camel_string))


def get_all_subclasses(*base_classes):
    """Return a set of all subclasses of the classes in base_classes,
    which have been defined at this point.

    The base classes are never returned as subclasses.

    :param base_classes: the list of classes for which subclasses are to be found
    """
    base_class_set = set(base_classes)
    subclasses = set(base_classes)
    previous_length = None
    while previous_length != len(subclasses):
        previous_length = len(subclasses)
        new_codec_classes = set(c for cls in subclasses for c in cls.__subclasses__())
        subclasses.update(new_codec_classes)

    return set(cls for cls in subclasses if cls not in base_class_set)


class Singleton(type):
    """Classes using this as will only be instantiated once.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """This method replaces the regular initializer of classes with this as their metaclass.
        *args and **kwargs are passed directly to their initializer and do not otherwise affect the Singleton behavior.
        """
        try:
            return cls._instances[cls]
        except KeyError:
            cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]


class ExposedProperty:
    """This method can be used to expose object properties as public callables
    that return what requesting that property would.
    """

    def __init__(self, instance, property_name):
        self.property_name = property_name
        self.instance = instance

    def __call__(self, *args, **kwargs):
        return getattr(self.instance, self.property_name)


class CircularList(list):
    """A tuned list that automatically applies modulo len(self) to the given index,
    allowing for circular, index-based access to the data (whereas itertools.cycle does
    not allow accessing elements by index).
    """

    def __getitem__(self, item):
        return super().__getitem__(item % len(self))


def class_to_fqn(cls):
    cls_fqn = f"{str(cls.__module__) + '.' if cls.__module__ is not None else ''}" \
              f"{cls.__name__}"
    return cls_fqn


def csv_to_latex_tabular(input_csv_path, output_tex_path, contains_header=True, use_booktabks=True):
    """Read a CSV table from a file and output it as a latex table to another file.
    The first row is assumed to be the header.

    :param input_csv_path: path to a file containing CSV data.
    :param output_tex_file: path where the tex contents are to be stored, ready to be `\input` in latex.
    :param contains_header: if True, the first line is assumed to be a header containing column names.
    :param use_booktabs: if True, a booktabs-based decoration style is used for the table. Otherwise,
      standard latex is used only.
    """
    with open(input_csv_path, "r") as csv_file, open(output_tex_path, "w") as tex_file:
        tex_file.write("\\begin{tabular}{")

        for i, row in enumerate(csv.reader(csv_file)):
            if i == 0:
                tex_file.write("l" * len(row) + "}\n")

            if i == 0 and contains_header:
                tex_file.write("\\toprule\n" if use_booktabks else "\\hline\n")
                tex_file.write(" & ".join(f"\\textbf{{{c}}}" for c in row).replace(
                    "_", "\\_").replace("%", "\%") + r" \\" + "\n")
                tex_file.write("\\midrule\n" if use_booktabks else "\\hline\n")
            else:
                tex_file.write(" & ".join(row).replace(
                    "_", "\\_").replace("%", "\%") + r" \\" + "\n")

        tex_file.write("\\bottomrule\n" if use_booktabks else "\\hline\n")
        tex_file.write("\\end{tabular}\n")


def get_node_ip():
    """Get the current IP address of this node.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    address = s.getsockname()[0]
    s.close()
    return address
