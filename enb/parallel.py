#!/usr/bin/env python3
"""Abstraction layer to provide parallel processing both locally and on ray clusters.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2022/01/02"

import platform
from . import config
from .config import options
from . import log
from .log import logger
from . import parallel_ray

def is_ray_supported():
    return platform.system().lower() == "linux"

def parallel(*args, **kwargs):
    """Decorator for methods intended to run in parallel.

    On linux platforms, methods are run via ray, and the *args and **kwargs arguments are passed
    to the `@ray.remote` decorator. On other platforms, the multiprocessing library is employed.

    To run a parallel method `f`, call `f.start` with the arguments you want to pass to f.
    An id object is returned immediately. The result can then be retrieved by calling
    `enb.parallel.get` with the id object.

    Important: parallel calls should not read or modify global variables.
    The only exception is enb.config.options, which can be read from parallel calls.
    """
    if is_ray_supported():
        return parallel_ray.parallel(*args, **kwargs)
    else:
        return multiprocess_parallel(*args, **kwargs)

def get(ids, **kwargs):
    if is_ray_supported():
        return parallel_ray.get(ids, **kwargs)
    else:
        return multiprocess_get(ids, **kwargs)

def multiprocess_parallel(*args, **kwargs):
    """Decorator for methods intended to run in parallel in the local machine.
    """
    raise NotImplementedError

def multiprocess_get(ids, **kwargs):
    """Method to get the results of methods decorated with enb.parallel.multiprocess_parallel.
    """
    raise NotImplementedError