#!/usr/bin/env python3
"""Timed calls to subprocess, so that real execution times can be obtained.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2020/05/23"

import os
import subprocess
import re
import time
import platform

from enb.config import options
from enb.log import logger

class InvocationError(Exception):
    """Raised when an invocation fails.
    """
    pass


def get_status_output_time_memory(
        invocation, expected_status_value=0, wall=None, timeout=None):
    """Run invocation, and return its status, output, and total (wall or
    user+system) time in seconds.

    :param expected_status_value: if not None, status must be equal to this
      value or an InvocationError is raised.
    :param wall: if True, execution wall time is returned. If False,
      user+system CPU time is returned. (both in seconds). If None, the value
      of enb.config.options.report_wall_time is used.
    :param timeout: if not None and not 0, an exception is raised if the
      execution exceeds this value

    :return: status, output, time, used_memory_kb
    """
    timeout = None if timeout == 0 else timeout

    if wall is None:
        wall = options.report_wall_time

    if "darwin" in platform.system().lower():
        time_command = "/usr/local/bin/gtime"
    else:
        time_command = "/usr/bin/time"

    if os.path.isfile(time_command):
        invocation = f"{time_command} -f 'u%U@s%S@m%M' {invocation} 2>&1"
        memory_available = True
    else:
        invocation = f"{invocation}"
        wall = True
        memory_available = False

    wall_time_before = time.time()
    try:
        output = subprocess.check_output(
            invocation, shell=True, timeout=timeout).decode("utf-8")
        status = 0
    except subprocess.CalledProcessError as ex:
        output = ex.output
        status = ex.returncode
    except subprocess.TimeoutExpired as ex:
        output = ex.output if ex.output is not None and ex.output != "None" \
            else f"Timeout exceeded ({timeout})"
        status = -1
    try:
        output = output.decode("utf-8")
    except Exception as ex:
        if not isinstance(output, str):
            logger.debug(f"Error decoding output ({type(output)}) to utf-8:\n"
                         f"{repr(ex)}")
    wall_time_after = time.time()

    output_lines = output.splitlines()
    output = "\n".join(output_lines[:-1]
                       if not wall and len(output_lines) > 1 else output_lines)

    if expected_status_value is not None and status != expected_status_value:
        raise InvocationError(
            f"status={status} != {expected_status_value}.\nInput=[{invocation}].\nOutput=[{output}]")

    measured_memory_kb = None
    if memory_available:
        try:
            m = re.fullmatch(r"u(\d+\.\d+)@s(\d+\.\d+)@m(\d+)", output_lines[-1])
        except IndexError:
            m = None
        if m is not None:
            measured_time = float(m.group(1)) + float(m.group(2))
            measured_memory_kb = int(m.group(3))
        else:
            raise InvocationError(f"Output {output_lines} did not contain "
                                  f"a valid time signature")
    if wall:
        measured_time = wall_time_after - wall_time_before

    return status, output, measured_time, measured_memory_kb


def get_status_output_time(invocation, expected_status_value=0, wall=None,
                           timeout=None):
    """Run invocation, and return its status, output, and total (wall or
    user+system) time in seconds.

    :param expected_status_value: if not None, status must be equal to this
      value or an InvocationError is raised.
    :param wall: if True, execution wall time is returned. If False,
      user+system CPU time is returned. (both in seconds). If None, the value
      of enb.config.options.report_wall_time is used.
    :param timeout: if not None and not 0, an exception is raised if the
      execution exceeds this value

    :return: status, output, time
    """
    return get_status_output_time_memory(
        invocation=invocation, expected_status_value=expected_status_value,
        wall=wall,timeout=timeout)[:3]
