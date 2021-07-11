#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Miscelaneous tools for `enb`.

This module does not and should not import anything from enb, so that other modules
may use misc tools at definition time.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "11/07/2021"


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