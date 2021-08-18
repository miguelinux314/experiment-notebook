#!/usr/bin/env python3
"""Tools to connect to ray clusters
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/11/21"

import sys
import os
import ray
from enb.config import options


def init_ray(force=False):
    """Initialize the ray cluster if it wasn't initialized before.

    If a ray configuration file is given in the options
    (must contain IP:port in the first line), then this method attempts joining
    the cluster. Otherwise, a new (local) cluster is created.

    :param force: if True, ray is initialized even if it was already running
      (generally problematic, specially if jobs are running)
    """
    if not ray.is_initialized() or force:
        if options.verbose:
            print(f"[I]nfo: making new cluster [CPUlimit={options.ray_cpu_limit}]")
        ray.init(num_cpus=options.ray_cpu_limit, include_dashboard=False,
                 local_mode=options.sequential)

def on_remote_process():
    """Return True if and only if the call is made from a remote ray process.
    """
    return os.path.basename(sys.argv[0]) == options.worker_script_name