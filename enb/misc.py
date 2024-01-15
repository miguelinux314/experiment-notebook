#!/usr/bin/env python3
"""Miscellaneous tools for `enb`.

This module does not and should not import anything from enb, so that other
modules may use misc tools at definition time."""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/07/11"

import re
import pdb
import signal
import socket
import csv
import time
import rich


def get_defining_class_name(method):
    """Return the name of the class of which f is a method, or None if not
    bound to any class.
    """
    try:
        return method.__qualname__.split('.<locals>', 1)[0].rsplit('.')[-2]
    except IndexError:
        return None


def remove_argparse_action(parser, action):
    """Entirely remove an action from a parser, from its subparsers and
    groups if it exists. Adapted from https://stackoverflow.com/a/49753634.
    """
    # pylint: disable=protected-access,too-many-branches
    try:
        parser._remove_action(action)
    except ValueError:
        pass
    try:
        parser._actions.remove(action)
    except ValueError:
        pass

    for group in parser._action_groups:
        try:
            group._remove_action(action)
        except ValueError:
            pass
        try:
            group._actions.remove(action)
        except ValueError:
            pass
        try:
            group._group_actions.remove(action)
        except ValueError:
            pass

    old_action = action
    try:
        parser._remove_action(old_action)
    except ValueError:
        pass
    try:
        parser._actions.remove(old_action)
    except ValueError:
        pass

    for option_str in old_action.option_strings:
        try:
            del parser._option_string_actions[option_str]
        except KeyError:
            pass

    vars_action = vars(old_action)
    try:
        var_group_actions = vars_action['_group_actions']
    except KeyError:
        var_group_actions = None
    if var_group_actions is not None:
        for group_action in var_group_actions:
            if group_action.dest == action:
                var_group_actions.remove(group_action)


def split_camel_case(camel_string):
    """Split a camel case string like ThisIsAClass into a string like "This
    Is A Class".
    """
    return " ".join(
        re.findall(r"[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))", camel_string))


def get_all_subclasses(*base_classes):
    """Return a set of all subclasses of the classes in base_classes,
    which have been defined at this point.

    The base classes are never returned as subclasses.

    :param base_classes: the list of classes for which subclasses are to be found
    """

    def get_subclasses_recursive(cls):
        direct_subclasses = set(cls.__subclasses__())
        recursive_subclasses = set()
        for subclass in direct_subclasses:
            recursive_subclasses = recursive_subclasses.union(
                get_subclasses_recursive(subclass))
        return direct_subclasses.union(recursive_subclasses)

    base_classes = set(base_classes)
    all_subclasses = set()

    for base_class in base_classes:
        all_subclasses = all_subclasses.union(
            get_subclasses_recursive(base_class))

    return set(cls for cls in all_subclasses if cls not in base_classes)


class Singleton(type):
    """Classes using this as metaclass will only be instantiated once.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """This method replaces the regular initializer of classes with this
        as their metaclass. `*args` and `**kwargs` are passed directly to
        their initializer and do not otherwise affect the Singleton behavior.
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

    # pylint: disable=too-few-public-methods
    def __init__(self, instance, property_name):
        self.property_name = property_name
        self.instance = instance

    def __call__(self, *args, **kwargs):
        return getattr(self.instance, self.property_name)


class CircularList(list):
    """A tuned list that automatically applies modulo len(self) to the given
    index, allowing for circular, index-based access to the data (whereas
    itertools.cycle does not allow accessing elements by index).
    """

    def __getitem__(self, item):
        return super().__getitem__(item % len(self))


class LapTimer:
    """Keep track of time duration similar to a lap timer. Useful to track
    the time elapsed between consecutive calls to print_lap.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.last_time = time.time()

    def print_lap(self, msg=None):
        """Print the elapsed time since the last time this method was called,
        or when this instance was created if it is the first time this method
        is called.
        """
        print(f"Elapsed{' ' + msg if msg is not None else ''}: "
              f"{time.time() - self.last_time}")
        self.last_time = time.time()


def class_to_fqn(cls):
    """Given a class (type instance), return its fully qualified name (FQN).
    """
    return f"{str(cls.__module__) + '.' if cls.__module__ is not None else ''}" \
           f"{cls.__name__}"


def csv_to_latex_tabular(input_csv_path, output_tex_path, contains_header=True,
                         use_booktabks=True):
    """Read a CSV table from a file and output it as a latex table to another
    file. The first row is assumed to be the header.

    :param input_csv_path: path to a file containing CSV data.
    :param output_tex_file: path where the tex contents are to be stored,
      ready to be added to latex with the `input` command.
    :param contains_header: if True, the first line is assumed to be a header
      containing column names.
    :param use_booktabs: if True, a booktabs-based decoration style is used
      for the table. Otherwise, standard latex is used only.
    """
    with open(input_csv_path, "r", encoding="utf-8") as csv_file, \
            open(output_tex_path, "w", encoding="utf-8") as tex_file:
        tex_file.write("\\begin{tabular}{")

        for i, row in enumerate(csv.reader(csv_file)):
            if i == 0:
                tex_file.write("l" * len(row) + "}\n")

            if i == 0 and contains_header:
                tex_file.write("\\toprule\n" if use_booktabks else "\\hline\n")
                tex_file.write(
                    " & ".join(f"\\textbf{{{escape_latex(c)}}}" for c in row) + r" \\" + "\n")
                tex_file.write("\\midrule\n" if use_booktabks else "\\hline\n")
            else:
                tex_file.write(" & ".join(escape_latex(row)) + r" \\" + "\n")

        tex_file.write("\\bottomrule\n" if use_booktabks else "\\hline\n")
        tex_file.write("\\end{tabular}\n")

def escape_latex(s):
    """Return a latex-scaped version of string s.
    """
    return s.replace("\\", "\\\\").replace("_", r"\_").replace(r"%", r"\%").replace("&", "\&")


def get_node_ip():
    """Get the current IP address of this node.
    """
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.connect(("8.8.8.8", 80))
    address = soc.getsockname()[0]
    soc.close()
    return address


def get_node_name():
    """Get the host name of this node. Alias for `socket.gethostname`.
    """
    return socket.gethostname()


def capture_usr1():
    """Capture the reception of a USR1 signal into pdb.

    From http://blog.devork.be/2009/07/how-to-bring-running-python-program.html.
    """

    def handle_pdb(sig, frame):
        # pylint: disable=unused-argument
        print("\n" * 2)
        print("Captured USR1 signal! Activating pdb...")
        print("\n" * 2)
        pdb.Pdb().set_trace(frame)

    signal.signal(signal.SIGUSR1, handle_pdb)

class BootstrapLogger:
    """Imitate enb.log.Logger's interface before it is loaded. This is needed to solve circular imports,
    i.e., when an error with the managed attributes decorator takes place before the full logger is available
    (within the config submodule).
    """

    def __init__(self):
        from .config.aoptions import get_options
        self.options = get_options()
        self.console = rich.console.Console(highlight=False, markup=False)

    def log(self, *args, style=None, **kwargs):
        self.console.print(*args, **kwargs, style=style, highlight=False, markup=False)

    def core(self, *args, **kwargs):
        self.log(*args, **kwargs, style="#28c9ff on #000000")

    def error(self, *args, **kwargs):
        self.log(*args, **kwargs, style="#ff5255 on #000000")

    def warn(self, *args, **kwargs):
        self.log(*args, **kwargs, style="#ffca4f on #000000")

    def message(self, *args, **kwargs):
        self.log(*args, **kwargs, style="#28c9ff on #000000")

    def verbose(self, *args, **kwargs):
        if self.options.verbose >= 1:
            self.log(*args, **kwargs, style="#c8ffc8 on #000000")

    def info(self, *args, **kwargs):
        if self.options.verbose >= 2:
            self.log(*args, **kwargs, style="#afffbe on #000000")

    def debug(self, *args, **kwargs):
        if self.options.verbose >= 3:
            self.log(*args, **kwargs, style="#909090 on #000000")
