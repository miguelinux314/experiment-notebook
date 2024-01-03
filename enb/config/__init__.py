#!/usr/bin/env python3
"""
# The config module

## Introduction

The config module deals with two main aspects:

    1. It provides the enb.config.options object with global configurations shared among enb
       modules and accessible to scripts using enb.
       These options can be accessed and set programmatically (e.g., `enb.config.options.verbose += 1`),
       and also through the CLI (see details below, or run with `-h` a python script that imports enb).

    2. It provides the enb.config.ini object to access properties defined in `.ini` files.
       These affect the default CLI values and can be easily extended by users to support
       file-based configuration. See below for details on this part.

Both `enb.config.options` and `enb.config.ini` are `argparse.Namespace` instances.
After a more detailed description of these two tools,
a summary of configuration setting priority is also provided.

## enb.config.options and CLI interface

Option configuration in enb is centralized through enb.config.options. Several key aspects should be highlighted:

    - Properties defined in `enb.config.options` are used by enb modules, and can also be used by
      scripts using enb (host scripts).

    - Many core enb functions have optional arguments with default None values.
      Those functions will often substitute None for the corresponding value in enb.config.options,
      e.g., to locate the plot output directory.

    - Scripts using enb (host scripts) may alter values in enb.config.options, e.g., before calling enb methods.
      Properties are accessed and modified with `enb.config.options.property`
      and `enb.config.property = value`, respectively. You may want to use the `from enb.config import options` line
      in your host scripts to enable less verbosity.

    - The CLI can be used to set initial values of enb.config.options properties using `-*` and `--*` arguments.
      Running with `-h` any script that imports enb will show you detailed help on all available options and
      their default values.

    - The default values for enb.config.options and its CLI is obtained through enb.config.ini, described below.


An important note should be made about the interaction between enb.config.options and ray.
When ray spawns new (local or remote) processes to serve as workers, the Options singleton
is initialized for each of those process, with the catch that ray does **not** pass the user's CLI parameters.
Therefore, different enb.config.option values would be present in the parent script and the ray workers.
To mitigate this problem, an `options` parameter is defined and passed to many these functions,
e.g., with `f.remote(options=ray.put(enb.config.options))` if f is your `@enb.parallel.parallel`-decorated function.
The `@enb.config.propagates_options` decorator provides a slightly cleaner way of automating
this mitigation.

## enb.config.ini file-based configuration

See the `enb.ini` module for further information on how this is handled.

## Effective parameter values

Based on the above description and references,
the values in `enb.config.options` will be given by the first of these options:

1. Programmatically set properties, e.g., `enb.config.options.verbose += 2`.
   The last set value is used.
2. Parameters `-*` and `-**` passed directly to the invoked script.
3. Default CLI parameters specified in any `*.ini` files in the same folder as the invoked script
   (this can be empty).
4. Default CLI parameters specified in any `*.ini` files in enb's configuration file (e.g., `~/.config/enb/enb.ini`).

From there on, many enb functions adhere to the following principle:

1. If a parameter is set to a non-None value, that value is used.
2. If a parameter with default value None is set to None or not specified,
   its value is set based on the properties in `enb.config.options`.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

# enb.config.ini : file-based config management
from .aini import ini
# enb.config.options : CLI-based config management, defaulting to enb.config.ini
from .aoptions import propagates_options, get_options, set_options

options = aoptions.Options()
assert options is aoptions.Options(), "Singleton not working"


def report_configuration():
    """Return a string describing the current configuration status.
    """
    return "\n".join((
        "Combined ini file configurations:",
        repr(ini),
        "",
        "Parameters of enb.config.options(after CLI parsing and potential manual changes):",
        "\n".join((f"{k} = {v}" for k, v in options.items())),
        "",
        "Logging status:",
        log.report_level_status()
    ))
