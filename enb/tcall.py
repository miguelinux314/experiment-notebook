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


class InvocationError(Exception):
    """Raised when an invocation fails.
    """
    pass


def get_status_output_time(invocation, expected_status_value=0, wall=False):
    """Run invocation, and return its status, output, and total
    (wall or user+system) time in seconds.

    :param expected_status_value: if not None, status must be equal to this value or
      an InvocationError is raised.
    :param wall: if True, execution wall time is returned. Otherwise, user+system CPU time is returned.
      (both in seconds).
      
    :return: status, output, time
    """

    if "darwin" in platform.system():
        time_command = "/usr/local/bin/gtime"
    else:
        time_command = "/usr/bin/time"

    if os.path.isfile(time_command):
        invocation = f"{time_command} -f 'u%U@s%S' {invocation}"
    else:
        invocation = f"{invocation}"
        wall = True

    wall_time_before = time.time()
    status, output = subprocess.getstatusoutput(invocation)
    wall_time_after = time.time()

    output_lines = output.splitlines()
    output = "\n".join(output_lines[:-1] if not wall else output_lines)
    if expected_status_value is not None and status != expected_status_value:
        raise InvocationError(
            f"status={status} != {expected_status_value}.\nInput=[{invocation}].\nOutput=[{output}]".format(
                status, invocation, output))

    if wall:
        measured_time = wall_time_after - wall_time_before
    else:
        m = re.fullmatch(r"u(\d+\.\d+)@s(\d+\.\d+)", output_lines[-1])
        if m is not None:
            measured_time = float(m.group(1)) + float(m.group(2))
        else:
            raise InvocationError(f"Output {output_lines} did not contain a valid time signature")

    return status, output, measured_time
