#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logging utilities for `enb`.

It uses only symbols from .misc, but no other module in enb.
"""
__author__ = "Miguel Hernández-Cabronero"
__date__ = "2021/08/13"

import contextlib
import sys
import time
import rich
import rich.progress
import rich.markup
import rich.console

from .misc import ExposedProperty
from .misc import Singleton
from . import config


class LogLevel:
    """Each of the available logging levels is an instance of this class. A
    level represents a named type of message, with a priority comparable to
    other levels.
    """

    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    def __init__(self, name, priority=0, prefix=None, help_message=None, style=None):
        """
        :param priority: minimum priority level needed to show this level.
        :param name: unique name for the level.
        :param prefix: prefix when printing messages of this level. If None,
          a default one is used based on the name.
        :param help_message: optional help explaining the purpose of the level.
        :param style: if not None, a color with which messages of this level are displayed. See
          https://rich.readthedocs.io/en/stable/appendix/colors.html for more details about
          available colors. If None, the default color is used.
        """
        self.name = name
        self.priority = priority
        self.label = prefix
        self.help = help_message
        if prefix is not None:
            self.prefix = prefix
        else:
            self.prefix = f"[{name[0].upper()}] "
        self.style = style

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name}:{self.priority})"


@config.aini.managed_attributes
class Logger(metaclass=Singleton):
    """Message logging and printing hub for `enb`.

    Messages are only shown if their priority is at least as high as the
    configured minimum.

    The minimum required level name (from "core" down to "debug") can be
    selected via the CLI and the file-based configuration by setting the
    `selected_log_level` flag/option.

    You can then modify this minimum value programmatically by setting
    `enb.config.options.minimum_priority_level` to a new :class:`LogLevel`
    instance, such as LOG_VERBOSE or any of the other constants defined above.
    """

    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    # Default style for core level messages
    style_core = "#28c9ff"
    # Default style for error level messages
    style_error = "bold #ff5255"
    # Default style for warning level messages
    style_warn = "#ffca4f"
    # Default style for message level messages
    style_message = "#28c9ff"
    # Default style for verbose level messages
    style_verbose = "#a5d3a5"
    # Default style for info level messages
    style_info = "#9b5ccb"
    # Default style for debug level messages
    style_debug = "#909090"
    # Style for the banner line
    banner_line_style = "#767676 bold"
    # Style for the regular text in the banner
    banner_plain_text_style = "#767676"
    # Style for the 'enb' part in the banner
    banner_enb_name_style = "#f3ac05 bold"
    # Style for the version part in the banner
    banner_enb_version_style = "#9b5ccb bold"

    def __init__(self):
        # Available logging levels and their intended usage
        self.levels = [
            LogLevel("core",
                     help_message="Messages always shown, "
                                  "no matter the priority level",
                     style=self.style_core),
            LogLevel("error",
                     help_message="A critical error that prevents "
                                  "from completing the main task",
                     style=self.style_error),
            LogLevel("warn",
                     help_message="Something wrong or bogus happened, "
                                  "but the main task can be completed",
                     style=self.style_warn),
            LogLevel("message",
                     help_message="Task-central messages intended "
                                  "to appear in console",
                     style=self.style_message),
            LogLevel("verbose",
                     help_message="Messages for the interested user, "
                                  "e.g., task progress",
                     style=self.style_verbose),
            LogLevel("info",
                     help_message="Messages for the very interested "
                                  "user/developer, e.g., detailed "
                                  "task progress",
                     style=self.style_info),
            LogLevel("debug",
                     help_message="Messages for debugging purposes, "
                                  "e.g., traces and watches",
                     style=self.style_debug),
        ]
        # Assign an integer priority level to each defined level (higher:
        # less priority).
        for i, level in enumerate(self.levels):
            level.priority = i
        # Keep easy access to the levels by their name
        self.name_to_level = {level.name: level for level in self.levels}

        # Minimum priority level required to be printed. It starts by the
        # least restrictive option, to allow logging during the configuration
        # load process without introducing circular references.
        self.selected_log_level = \
            sorted(self.name_to_level.values(),
                   key=lambda lev: lev.priority)[0]

        # Create a few IDE-friendly attributes that point to the predefined levels by name
        self.level_core = self.get_level("core")
        self.level_error = self.get_level("error")
        self.level_warn = self.get_level("warn")
        self.level_message = self.get_level("message")
        self.level_verbose = self.get_level("verbose")
        self.level_info = self.get_level("info")
        self.level_debug = self.get_level("debug")
        # This value is changed based on the file and CLI configuration by
        # enb/__init__.py
        self.show_prefixes = False
        # show_prefix_level determines the level required to include prefixes
        # in any shown messages.
        self.show_prefix_level = self.level_info

        # Last levels and end strings used when logging
        self._last_end = None
        self._last_level = None
        # Store the original builtins print function when replacing
        self._original_print = None
        # Lazy imports from parallel_ray, to avoid circular definitions
        self._is_parallel_process = None
        self._is_ray_enabled = None

    def levels_by_priority(self):
        """Return a list of the available levels, sorted from higher to lower
        priority.
        """
        return sorted(self.name_to_level.values(),
                      key=lambda level: level.priority)

    def log(self, msg, level, end="\n", file=None, markup=False, highlight=False, style=None,
            rule=False, rule_kwargs=None):
        """Conditionally log a message given its level. It only shares "end"
        with builtins.print as keyword argument.

        :param msg: message to be logged
        :param level: priority level for the message
        :param end: string appended after the message, if it is shown.
        :param file: file where to log the message, or None to automatically
          select sys.stdout
        :param markup: should rich markup be interpreted within the message?
        :param highlight: should rich apply automatic highlighting of numbers, constants, etc., to the message?
        :param style: if not None, the level's current style is overwritten by this
        :param rule: should the message be displayed with console.rule()?
        :param rule_kwargs: if rule_kwargs is True, these parameters are passed to console.rule
        """
        # pylint: disable=too-many-arguments
        file = file or sys.stdout

        if level.priority <= self.selected_log_level.priority:
            try:
                # pylint: disable=access-member-before-definition
                last_end = self._last_end
                last_level = self._last_level
            except AttributeError:
                last_end = "\n"
                last_level = self.selected_log_level

            forfeit_prefix = last_level is level and not last_end.endswith("\n")
            forfeit_prefix = forfeit_prefix \
                             or (self.selected_log_level.priority
                                 <= self.show_prefix_level.priority)
            split_message_str = "" if last_level is None \
                                      or last_level is level \
                                      or last_end is None \
                                      or last_end.endswith("\n") \
                else "\n"

            output_msg = \
                f"{split_message_str}" \
                + (str(level.prefix) if self.show_prefixes
                                        and not forfeit_prefix else '') + \
                f"{msg}{end}"

            try:
                from .progress import ProgressTracker
                console = ProgressTracker.console
                console.markup = markup
                console.highlight = highlight
            except AttributeError:
                console = None
            console = console or rich.console.Console(file=file, markup=markup, highlight=highlight)
            style = style or level.style

            if rule:
                console.rule(output_msg, **(rule_kwargs or dict()))
            else:
                console.print(output_msg, end="", style=style, highlight=highlight, markup=markup)

            self._last_end = end
            self._last_level = level

    def show_banner(self, level=None):
        """Shows the enb banner, including the current version.

        :param level: the priority level with which the banner is shown. If None, verbose is used by default.
        """
        banner_contents = (
            f"[{self.banner_line_style}][bold])[/bold][/{self.banner_line_style}] "
            f"[{self.banner_plain_text_style}]"
            f"Powered by "
            f"[{self.banner_enb_name_style}]enb[/{self.banner_enb_name_style}] "
            f"[{self.banner_enb_version_style}]"
            f"v{config.ini.get_key('enb', 'version')}"
            f"[/{self.banner_enb_version_style}]"
            f"[/{self.banner_plain_text_style}]"
            f" [{self.banner_line_style}][bold]([/bold][/{self.banner_line_style}]"
            )

        level = level or self.level_verbose
        self.log("", level=level)
        self.log(banner_contents, end="", rule=True, markup=True,
                 rule_kwargs=dict(style=self.banner_line_style,
                                  align="center"), level=level)
        self.log("", level=level)

    @property
    def is_parallel_process(self):
        """Lazy property to determine whether this is currently a parallel process.
        """
        if self._is_parallel_process:
            is_parallel_process = self._is_parallel_process
        else:
            from .parallel_ray import is_parallel_process
            self._is_parallel_process = is_parallel_process
        return is_parallel_process

    @property
    def is_ray_enabled(self):
        """Lazy property to determine whether ray is available and enabled.
        """
        if self._is_ray_enabled:
            is_ray_enabled = self._is_ray_enabled
        else:
            from .parallel_ray import is_ray_enabled
            self._is_ray_enabled = is_ray_enabled
        return is_ray_enabled

    def core(self, msg, **kwargs):
        """A message of "core" level.

        :param kwargs: optional arguments passed to self.log (must be
          compatible)
        """
        self.log(msg=msg, level=self.level_core, **kwargs)

    def error(self, msg, **kwargs):
        """Log an error message.

        :param kwargs: optional arguments passed to self.log (must be
          compatible)
        """
        self.log(msg=msg, level=self.level_error, **kwargs)

    def warn(self, msg, **kwargs):
        """Log a warning message.

        :param kwargs: optional arguments passed to self.log (must be
          compatible)
        """
        self.log(msg=msg, level=self.level_warn, **kwargs)

    def message(self, msg, **kwargs):
        """Log a regular console message.

        :param kwargs: optional arguments passed to self.log (must be
          compatible)
        """
        self.log(msg=msg, level=self.level_message, **kwargs)

    def verbose(self, msg, **kwargs):
        """Log a verbose console message.

        :param kwargs: optional arguments passed to self.log (must be
          compatible)
        """
        self.log(msg=msg, level=self.level_verbose, **kwargs)

    def info(self, msg, **kwargs):
        """Log an extra-informative console message.

        :param kwargs: optional arguments passed to self.log (must be
          compatible)
        """
        self.log(msg=msg, level=self.level_info, **kwargs)

    def debug(self, msg, **kwargs):
        """Log a debug trace.

        :param kwargs: optional arguments passed to self.log (must be
          compatible)
        """
        self.log(msg=msg, level=self.level_debug, **kwargs)

    @contextlib.contextmanager
    def log_context(self, msg, level, sep="...", msg_after=None,
                    show_duration=True):
        """Log a message before executing the `with` block code, run the
        block, and log another message when the block is completed. The
        message given the selected priority level, and is only displayed
        based on `self.selected_log_level`. The block of code is executed
        regardless of the logging options.

        :param msg: Message typically describing the
        :param level: Priority level for the shown messages.
        :param sep: separator printed between msg_before and msg_after (
          newline is not required in it to allow single-line reporting)
        :param msg_after: message shown after `msg` and `sep` upon
          completion. If none, one is automatically selected based on msg.
        :param show_duration: if True, a message displaying the run time is
          logged upon completion.
        """
        # pylint: disable=too-many-arguments
        # Show entry message
        self.log(msg=msg, end=sep, level=level)
        time_before = time.time()

        # Run block
        yield None
        run_time = time.time() - time_before

        # Show exit message
        if msg_after is None:
            space = " "
            try:
                space = space if not self._last_end.endswith("\n") else ""
                msg_after = f"{space}done" if self._last_level is level and self._last_end == sep \
                    else f"done ({msg.rstrip()})"
            except AttributeError:
                msg_after = f"{space}done"
        if show_duration:
            msg_after += f" (took {run_time:.2f}s)"
        msg_after += "." if msg_after[-1] != "." else ""
        self.log(msg=msg_after, level=level)

    def core_context(self, msg, sep="...", msg_after=None, show_duration=True):
        """Logging context of core priority.

        :param msg: Message to show before starting the code block.
        :param sep: separator printed between msg_before and msg_after (
          newline is not required in it to allow single-line reporting).
        :param msg_after: message shown after `msg` and `sep` upon completion.
        :param show_duration: if True, a message displaying the run time is
          logged upon completion.
        """
        return self.log_context(msg=msg, level=self.level_core,
                                sep=sep, msg_after=msg_after,
                                show_duration=show_duration)

    def message_context(self, msg, sep="...", msg_after=None,
                        show_duration=True):
        """Logging context of message priority.

        :param msg: Message to show before starting the code block.
        :param sep: separator printed between msg_before and msg_after (
          newline is not required in it to allow single-line reporting)
        :param msg_after: message shown after `msg` and `sep` upon completion.
        :param show_duration: if True, a message displaying the run time is
          logged upon completion.
        """
        return self.log_context(msg=msg, level=self.level_message,
                                sep=sep, msg_after=msg_after,
                                show_duration=show_duration)

    def verbose_context(self, msg, sep="...", msg_after=None,
                        show_duration=True):
        """Logging context of verbose priority.

        :param msg: Message to show before starting the code block.
        :param sep: separator printed between msg_before and msg_after (
          newline is not required in it to allow single-line reporting)
        :param msg_after: message shown after `msg` and `sep` upon completion.
        :param show_duration: if True, a message displaying the run time is
          logged upon completion.
        """
        return self.log_context(msg=msg, level=self.level_verbose,
                                sep=sep, msg_after=msg_after,
                                show_duration=show_duration)

    def info_context(self, msg, sep="...", msg_after=None, show_duration=True):
        """Logging context of info priority.

        :param msg: Message to show before starting the code block.
        :param sep: separator printed between msg_before and msg_after (
          newline is not required in it to allow single-line reporting)
        :param msg_after: message shown after `msg` and `sep` upon completion.
        :param show_duration: if True, a message displaying the run time is
          logged upon completion.
        """
        return self.log_context(msg=msg, level=self.level_info,
                                sep=sep, msg_after=msg_after,
                                show_duration=show_duration)

    def debug_context(self, msg, sep="...", msg_after=None, show_duration=True):
        """Logging context of debug priority.

        :param msg: Message to show before starting the code block.
        :param sep: separator printed between msg_before and msg_after (
          newline is not required in it to allow single-line reporting)
        :param msg_after: message shown after `msg` and `sep` upon completion.
        :param show_duration: if True, a message displaying the run time is
          logged upon completion.
        """
        return self.log_context(msg=msg, level=self.level_debug,
                                sep=sep, msg_after=msg_after,
                                show_duration=show_duration)

    def level_active(self, name, **kwargs):
        """Return True if and only if the given name corresponds to a level
        with priority sufficient given self.min_priority_level.
        """
        # pylint: disable=unused-argument
        if isinstance(name, LogLevel):
            name = name.name
        return self.name_to_level[name].priority <= self.selected_log_level.priority

    @property
    def core_active(self):
        """Return True if and only if the core level is currently active,
        i.e., the current `self.min_priority_level` has a greater or equal
        priority value than the core level.
        """
        return self.level_active("core")

    @property
    def error_active(self):
        """Return True if and only if the error level is currently active,
        i.e., the current `self.min_priority_level` has a greater or equal
        priority value than the error level.
        """
        return self.level_active("error")

    @property
    def warn_active(self):
        """Return True if and only if the warn level is currently active,
        i.e., the current `self.min_priority_level` has a greater or equal
        priority value than the warn level.
        """
        return self.level_active("warn")

    @property
    def message_active(self):
        """Return True if and only if the message level is currently active,
        i.e., the current `self.min_priority_level` has a greater or equal
        priority value than the message level.
        """
        return self.level_active("message")

    @property
    def verbose_active(self):
        """Return True if and only if the verbose level is currently active,
        i.e., the current `self.min_priority_level` has a greater or equal
        priority value than the verbose level.
        """
        return self.level_active("verbose")

    @property
    def info_active(self):
        """Return True if and only if the info level is currently active,
        i.e., the current `self.min_priority_level` has a greater or equal
        priority value than the info level.
        """
        return self.level_active("info")

    @property
    def debug_active(self):
        """Return True if and only if the debug level is currently active,
        i.e., the current `self.min_priority_level` has a greater or equal
        priority value than the debug level.
        """
        return self.level_active("debug")

    def report_level_status(self):
        """:return: a string reporting the present logging levels and whether
          or not they are active.
        """
        lines = [f"{'level':8s}  {'priority':8s}  {'active':6s}"]
        lines.append("-" * len(lines[0]))
        lines.extend(
            f"{name:8s}  {str(level.priority):8s}  {self.level_active(name)}"
            for name, level in self.name_to_level.items())
        return "\n".join(lines)

    def get_level(self, name, lower_priority=0):
        """If lower_priority is 0, return the logging level associated with
        the name passed as argument. Otherwise, the aforementioned level's
        priority is lowered by that numeric amount (positive values means
        less prioritary levels can be selected).

        After that, the available level with the closest priority is chosen.
        """
        # Obtain the logger for the given name
        base_level = self.name_to_level[name]

        # Shift priority if requested - always return something in the list
        # of available levels
        if lower_priority != 0:
            new_priority = base_level.priority + lower_priority
            levels_by_priority = logger.levels_by_priority()
            base_level = levels_by_priority[0]
            for level in levels_by_priority[1:]:
                if level.priority <= new_priority:
                    base_level = level
                else:
                    break

        return base_level

    def print_to_log(self, *args, sep=" ", end="\n", file=None):
        """Method used to substitute print if configured to do so.
        If file is None, then sys.stdout is used by default.
        """
        self.message(f"{sep.join((str(a) for a in args))}", end=end, file=file)

    def __repr__(self):
        return f"{self.__class__.__name__}(selected={self.selected_log_level})"


# Singleton instance of the logger, shared across modules even if reinstantiated.
logger = Logger()
assert logger is Logger(), "Singleton not working for log.py"

# Expose logging functions
get_level = logger.get_level
log = logger.log
core = logger.core
error = logger.error
warn = logger.warn
message = logger.message
verbose = logger.verbose
info = logger.info
debug = logger.debug

# Expose functions to check whether a level is active or not
core_active = ExposedProperty(instance=logger, property_name="core_active")
error_active = ExposedProperty(instance=logger, property_name="error_active")
warn_active = ExposedProperty(instance=logger, property_name="warn_active")
message_active = ExposedProperty(instance=logger, property_name="message_active")
verbose_active = ExposedProperty(instance=logger, property_name="verbose_active")
info_active = ExposedProperty(instance=logger, property_name="info_active")
debug_active = ExposedProperty(instance=logger, property_name="debug_active")

# Expose status report functions
show_banner = logger.show_banner
report_level_status = logger.report_level_status
