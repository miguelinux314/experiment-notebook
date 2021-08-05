#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Miscelaneous tools for `enb`.

This module does not and should not import anything from enb, so that other modules
may use misc tools at definition time.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "11/07/2021"

import re


def get_banner():
    """Returns the enb banner.
    """
    return f"\n{' [ enb - Experiment Notebook ] ':.^100}\n"


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
