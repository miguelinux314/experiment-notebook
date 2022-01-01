#!/usr/bin/env python3
"""Electronic Notebook (enb) library.

Please see https://github.com/miguelinux314/experiment-notebook for further information.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/03/31"

import os as _os
import sys as _sys
import ast as _ast
import importlib as _importlib
import appdirs as _appdirs
import numpy as _np
import warnings as _warnings
import ray as _ray
import atexit as _atexit

# Make all warnings errors
_np.seterr(all="raise")
_warnings.simplefilter('error', UserWarning)

# Current installation dir of enb
enb_installation_dir = _os.path.dirname(_os.path.abspath(__file__))

# User configuration dir (e.g., ~/.config/enb in many linux distributions)
user_config_dir = _os.path.join(_os.path.abspath(_os.path.expanduser(_appdirs.user_config_dir())), f"enb")
if not _os.path.exists(user_config_dir):
    _os.makedirs(user_config_dir, exist_ok=True)
if not _os.path.isdir(user_config_dir):
    print(f"[enb.__init__.py]: user_config_dir={user_config_dir} is not a directory or could not be created.")

# Absolute, real path to the calling script's dir. Configuration files present here will overwrite
# those in `user_config_dir`.
calling_script_dir = _os.path.realpath(_os.path.dirname(_os.path.abspath(_sys.argv[0])))

# Data dir
default_base_dataset_dir = _os.path.join(calling_script_dir, "datasets")
# Persistence dir
default_persistence_dir = _os.path.join(calling_script_dir, f"persistence_{_os.path.basename(_sys.argv[0])}")

# Are we currently running the main enb CLI or the CLI for a host script? True means main enb CLI.
is_enb_cli = _os.path.basename(_sys.argv[0]) in ["__main__.py", "enb"]

# Basic tools among core modules
from . import misc
# Logging tools
from . import log
# Global configuration modules
from . import config
# Logging tools
from .log import logger
# ray for parallelization
from . import ray_cluster

# Setup logging so that it is used from here on. Done here to avoid circular dependencies.
logger.selected_log_level = log.get_level(name=config.options.selected_log_level,
                                          lower_priority=config.options.verbose)
logger.show_prefixes = config.options.log_level_prefix
logger.show_prefix_level = logger.get_level(name=config.options.show_prefix_level)
if config.options.log_print and not ray_cluster.on_remote_process():
    logger.replace_print()

# Remaining core modules
## Keystone ATable features
from . import atable
## Basic Experiment features
from . import sets
from . import experiment
## Data analysis (e.g., plotting) modules
from . import plotdata
from . import aanalysis
## Image compression modules
from . import icompression
from . import isets
from . import pgm
# Plugin and template support
from . import plugins

# Set up ray and other remaining logging aspects
if not ray_cluster.on_remote_process():
    # Don't show the banner in each child instance
    log.core(config.get_banner())
    _atexit.register(lambda: ray_cluster.stop_ray() if _ray.is_initialized() else None)
    __file__ = _os.path.abspath(__file__)
    if not is_enb_cli:
        _os.chdir(calling_script_dir)
    config.options._initial_module_names = list(
        m.__name__ for m in _sys.modules.values() if hasattr(m, "__name__"))

# Run the setter functions on the default values too, allowing validation and normalization
config.options.update(config.options, trigger_events=True)

# An environment variable is passed to the children processes
# for them to be able to import all modules that were
# imported after loading enb. This prevents the remote
# functions to fail the deserialization process
# due to missing definitions.
if ray_cluster.on_remote_process():
    _imported_modules = set()
    for _module_name in sorted(_ast.literal_eval(_os.environ['_needed_modules'])):
        try:
            _importlib.import_module(_module_name)
            _imported_modules.add(_module_name)
        except ImportError as _ex:
            _module_parts = _module_name.split(".")
            for i in range(1, len(_module_parts) - 1):
                if ".".join(_module_parts[:i]) in _imported_modules:
                    break
                else:
                    logger.error(f"Error importing module {repr(_module_name)}: {repr(_ex)}.")
