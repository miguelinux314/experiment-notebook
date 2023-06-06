#!/usr/bin/env python3
"""Experiment notebook (enb) library.

Please see https://github.com/miguelinux314/experiment-notebook
for further information.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/03/31"

# pylint: disable wrong-import-position

import warnings as _warnings
import atexit as _atexit
import os as _os
import sys as _sys
import appdirs as _appdirs
import numpy as _np

# Make all warnings errors
_np.seterr(all="raise")
_warnings.simplefilter('error', UserWarning)

# Current installation dir of enb
enb_installation_dir = _os.path.dirname(_os.path.abspath(__file__))

# User configuration dir (e.g., ~/.config/enb in many linux distributions)
user_config_dir = _os.path.join(
    _os.path.abspath(_os.path.expanduser(_appdirs.user_config_dir())), "enb")
if not _os.path.exists(user_config_dir):
    _os.makedirs(user_config_dir, exist_ok=True)
if not _os.path.isdir(user_config_dir):
    print(
        f"[enb.__init__.py]: user_config_dir={user_config_dir} "
        f"is not a directory or could not be created.")

# Absolute, real path to the calling script's dir.
# Configuration files present here will overwrite
# those in `user_config_dir`.
calling_script_dir = _os.path.realpath(
    _os.path.dirname(_os.path.abspath(_sys.argv[0]))) \
    if _sys.argv[0] else _os.getcwd()

# Are we currently running the main enb CLI or the CLI for a host script?
# True means main enb CLI.
is_enb_cli = _os.path.basename(_sys.argv[0]) in ["__main__.py", "enb"]

# Data dir
default_base_dataset_dir = _os.path.join(calling_script_dir, "datasets")
# Persistence dir
default_persistence_dir = _os.path.join(calling_script_dir,
                                        f"persistence_{_os.path.basename(_sys.argv[0])}")
# Plots dir
default_output_plots_dir = _os.path.join(calling_script_dir,
                                         "plots") if not is_enb_cli else "./plots"
# Analysis dir
default_analysis_dir = _os.path.join(calling_script_dir,
                                     "analysis") if not is_enb_cli else "./analysis"

# Fix getcwd for the specific case enb is imported from the sphinx documentation tool
if _os.path.basename(_sys.argv[0]) == "sphinx-build":
    default_persistence_dir = _os.path.join(_os.getcwd(), "build",
                                            f"persistence_{_os.path.basename(_sys.argv[0])}")
    default_base_dataset_dir = _os.path.join(_os.getcwd(), "build", "datasets")
    default_output_plots_dir = _os.path.join(_os.getcwd(), "build", "plots")
    default_analysis_dir = _os.path.join(_os.getcwd(), "build", "analysis")

# pylint: disable=wrong-import-position
# Basic tools among core modules
from . import misc
# Logging tools
from . import log
# Global configuration modules
from . import config
# Logging tools
from .log import logger
# Paralellization modules
from . import parallel
from . import parallel_ray

# Temporary fix until the dill library is fixed
parallel.parallel_fix_dill_crash()

# Setup logging so that it is used from here on. Done here to avoid circular dependencies.
logger.selected_log_level = log.get_level(
    name=config.options.selected_log_level,
    lower_priority=config.options.verbose)
logger.show_prefixes = config.options.log_level_prefix
logger.show_prefix_level = logger.get_level(
    name=config.options.show_prefix_level)

if config.options.log_print and not parallel_ray.is_parallel_process():
    logger.replace_print()

# Remaining core modules
## Keystone ATable features
from . import atable
## Basic Experiment features
from . import sets
from . import experiment
## Data analysis (e.g., plotting) modules
from . import plotdata
from . import render
from . import aanalysis
## Image compression modules
from . import icompression
from . import isets
from . import pgm
from . import tarlite
# Plugin and template support
from . import plugins

# Secondary module import
from . import fits
from . import png

# For backwards compatibility
isets.FITSVersionTable = fits.FITSVersionTable
isets.PNGCurationTable = png.PNGCurationTable
isets.raw_path_to_png = png.raw_path_to_png
isets.render_array_png = png.render_array_png

# Kept for backwards compatibility
icompression.FITSVersionTable = fits.FITSVersionTable
icompression.FitsWrapperCodec = fits.FITSWrapperCodec
icompression.PNGWrapperCodec = png.PNGWrapperCodec
icompression.PGMWrapperCodec = pgm.PGMWrapperCodec

# Setup to be run only when enb is imported in the main process
if not parallel_ray.is_parallel_process():
    # Setup common to
    log.core(config.get_banner())
    log.debug(
        f"Additional .ini files employed: {repr(config.ini.all_ini_paths)}.")

    __file__ = _os.path.abspath(__file__)
    if not is_enb_cli:
        _os.chdir(calling_script_dir)

    if parallel_ray.is_ray_enabled():
        logger.info("Using ray for parallelization.")
        _atexit.register(parallel_ray.stop_ray)
        # The list of modules loaded so far passed to any possible ray remote
        # nodes so that they don't attempt to load them again.
        # pylint: disable=protected-access
        config.options._initial_module_names = list(
            m.__name__ for m in _sys.modules.values() if
            hasattr(m, "__name__"))
    else:
        logger.info("Using pathos for parallelization.")

    misc.capture_usr1()

# Run the setter functions on the default values too, allowing validation and normalization
config.options.update(config.options, trigger_events=True)

# Remote process invoked with ray need to have some imports added
parallel_ray.fix_imports()
