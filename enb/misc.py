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
