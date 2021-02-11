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
    """Initialize the ray cluster if it wasn't initialized before.

    If a ray configuration file is given in the options
    (must contain IP:port in the first line), then this method attempts joining
    the cluster. Otherwise, a new (local) cluster is created.

    :param force: if True, ray is initialized even if it was already running
      (generally problematic, specially if jobs are running)
    """
    if not ray.is_initialized() or force:
        if os.path.exists(options.ray_config_file):
            with open(options.ray_config_file, "r") as options_file:
                address_line = options_file.readline().strip()
                if options.verbose:
                    print(f"Joining cluster [config: {address_line}] "
                          f"[CPUlimit={options.ray_cpu_limit}]...")
                ray.init(address=address_line, num_cpus=options.ray_cpu_limit)
        else:
            if options.verbose:
                print("Making new cluster...")

            ray.init(num_cpus=options.ray_cpu_limit)
