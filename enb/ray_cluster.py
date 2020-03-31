#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tools to connect to ray clusters
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "21/11/2019"

import os
import ray

from enb.config import get_options

options = get_options()


def init_ray(force=False):
    """Initialize the ray cluster. If a ray configuration file is given
    in the options (must contain IP:port in the first line), then
    this method attempts joining the cluster. Otherwise, a new (local) cluster is
    crated.
    """
    if not ray.is_initialized() or force:
        if os.path.exists(options.ray_config_file):
            address_line = open(options.ray_config_file, "r").readline().strip()
            if options.verbose:
                print(f"Joining cluster [config: {address_line}]...")
            ray.init(address=address_line)
        else:
            if options.verbose:
                print("Making new cluster...")
            ray.init()
