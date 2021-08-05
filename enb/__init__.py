#!/usr/bin/env python3
"""Electronic notebook (enb) library.
"""
import os as _os
import sys as _sys
import appdirs as _appdirs

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

# Pre-definition tools
from . import misc

# Global configuration modules
from . import config

# Core modules
## Basic ATable features
from . import ray_cluster
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
# TODO: pgm should not be a core module - move somewhere into icompression ?
from . import pgm

# Plugin support
from . import plugins