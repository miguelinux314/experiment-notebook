#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logging utilities for `enb`
"""
__author__ = "Miguel Hernández-Cabronero"
__date__ = "2021/08/13"

from .config import options
from .config.singleton_cli import Singleton


class LogLevel:
    """Each of the available logging levels is an instance of this class.
    A level represents a named type of message, with a priority comparable
    to other levels.
    """

    def __init__(self, name, priority=0, prefix=None, help=None):
        """
        :param priority: minimum priority level needed to show this level.
        :param name: unique name for the level.
        :param prefix: prefix when printing messages of this level. If None, a default one
          is used based on the name.
        :param help: optional help explaining the purpose of the level.
        """
        self.name = name
        self.priority = priority
        self.label = prefix
        self.help = help

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name}:{self.priority})"


class Logger(metaclass=Singleton):
    """Message logging and printing hub for `enb`.

    Messages are only shown if their priority is at least as high as the configured minimum.

    The minimum required level name (from "core" down to "debug") can be selected via the CLI and the file-based configuration
    by setting the `max_log_level` flag/option.

    You can then modify this minimum value programmatically
    by setting `enb.config.options.minimum_priority_level` to a new :class:`LogLevel` instance,
    such as LOG_VERBOSE or any of the other constants defined above.
    """
    # Available logging levels and their intended usage
    levels = [
        LogLevel("core", help="Messages always shown, no matter the priority level"),
        LogLevel("error", help="A critical error that prevents from completing the main task"),
        LogLevel("warning", help="Something wrong or bogus happened, but the main task can be completed"),
        LogLevel("message", help="Task-central messages intended to appear in console"),
        LogLevel("verbose", help="Messages for the interested user, e.g., task progress"),
        LogLevel("info", help="Messages for the very interested user/developer, e.g., detailed task progress"),
        LogLevel("debug", help="Messages for debugging purposes, e.g., traces and watches"),
    ]
    # Assign an integer priority level to each defined level (higher: less priority).
    for i, level in enumerate(levels):
        level.priority = i
    # Keep easy access to the levels by their name
    name_to_level = {level.name: level for level in levels}
    # Minimum priority level required to be printed. It starts by the least restrictive option,
    # to allow logging during the configuration load process without introducing circular
    # references.
    max_log_level = sorted(name_to_level.values(), key=lambda l: l.priority)[0]

    def log(self, msg, level):
        """Conditionally log a message given its level.
        """
        if self.max_log_level.priority <= level.priority:
            print(f"{self}: {msg}")

    def core(self, msg):
        """A message of "core" level
        """
        self.log(msg=msg, level=self.level_core)

    def error(self, msg):
        """Log an error message.
        """
        self.log(msg=msg, level=self.level_error)

    def warn(self, msg):
        """Log a warning message.
        """
        self.log(msg=msg, level=self.level_warning)

    def message(self, msg):
        """Log a regular console message.
        """
        self.log(msg=msg, level=self.level_console)

    def verbose(self, msg):
        """Log a verbose console message.
        """
        self.log(msg=msg, level=self.level_verbose)

    def info(self, msg):
        """Log an extra-informative console message.
        """
        self.log(msg=msg, level=self.level_info)

    def debug(self, msg):
        """Log a debug trace.
        """
        self.log(msg=msg, level=self.level_debug)

    def level_active(self, name):
        """Return True if and only if the given name corresponds to a level with
        priority sufficient given self.min_priority_level.
        """
        return self.name_to_level[name].priority <= self.max_log_level.priority

    def core_active(self):
        """Return True if and only if the core level is currently active, i.e.,
        the current `self.min_priority_level` has a greater or equal priority value
        than the core level.
        """
        return self.level_active("core")

    def error_active(self):
        """Return True if and only if the error level is currently active, i.e.,
        the current `self.min_priority_level` has a greater or equal priority value
        than the error level.
        """
        return self.level_active("error")

    def warn_active(self):
        """Return True if and only if the warn level is currently active, i.e.,
        the current `self.min_priority_level` has a greater or equal priority value
        than the warn level.
        """
        return self.level_active("warn")

    def message_active(self):
        """Return True if and only if the message level is currently active, i.e.,
        the current `self.min_priority_level` has a greater or equal priority value
        than the message level.
        """
        return self.level_active("message")

    def verbose_active(self):
        """Return True if and only if the verbose level is currently active, i.e.,
        the current `self.min_priority_level` has a greater or equal priority value
        than the verbose level.
        """
        return self.level_active("verbose")

    def info_active(self):
        """Return True if and only if the info level is currently active, i.e.,
        the current `self.min_priority_level` has a greater or equal priority value
        than the info level.
        """
        return self.level_active("info")

    def debug_active(self):
        """Return True if and only if the debug level is currently active, i.e.,
        the current `self.min_priority_level` has a greater or equal priority value
        than the debug level.
        """
        return self.level_active("debug")


# Singleton instance of the logger, shared across modules even if reinstantiated.
logger = Logger()
assert logger is Logger(), "Singleton not working for log.py"

# Logging functions are exposed directly
log = logger.log
core = logger.core
error = logger.error
warn = logger.warn
message = logger.message
verbose = logger.verbose
info = logger.info
debug = logger.debug


def get_level(name):
    """Return the logging level associated with the name passed as argument.
    """
    return Logger.name_to_level[name]


def report_level_status():
    """:return: a string reporting the present logging levels and whether or not they are active.
    """
    lines = [f"{'level':8s}  {'priority':8s}  {'active':6s}"]
    lines.append("-" * len(lines[0]))
    lines.extend(f"{name:8s}  {str(level.priority):8s}  {logger.level_active(name)}"
                 for name, level in logger.name_to_level.items())
    return "\n".join(lines)
