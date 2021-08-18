#!/usr/bin/env python3
"""Tools to connect to ray clusters
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/11/21"

import time
import sys
import os
import datetime
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


class ProgressiveGet:
    """When an instance is created, the computation of the requested list of ray ids is started
    in parallel the background (unless they are already running).

    The returned instance is an iterable object. Each to next() with this instance will either
    return the instance if any tasks are still running, or raise StopIteration if all are complete.
    Therefore, instances of this class can be used as the right operand of `in` in for loops.

    A main application of this for-loop approach is to periodically run a code snippet (e.g., for logging)
    while the computation is performed in the background. The loop will continue until all tasks are completed.
    One can then call `ray.get(ray_id_list)` and retrieve the obtained results without any expected delay.

    Note that the for-loop body will always be executed at least once, namely after every potentially
    blocking call to :meth:`ray.wait`.
    """

    def __init__(self, ray_id_list, weight_list=None, iteration_period=1):
        """
        Start the computation of ray_id_list in the background, and get ready to receive next() requests.

        :param ray_id_list: list of ray ids that are to be processed
        :param weight_list: if not None, a list of the same length as ray_id list, which contains
          nonnegative values that describe the weight of each task. If provided, they should be highly correlated
          with the computation time of each associated task to provide accurate completion time estimations.
        :param iteration_period: a non-negative value that determines the wait period allowed for ray to
          obtain new results when next() is used. When using this instance in a for loop, it determines approximately
          the periodicity with which the loop body will be executed.
        """
        iteration_period = float(iteration_period)
        if iteration_period < 0:
            raise ValueError(f"Invalid iteration period {iteration_period}: it cannot be negative (but it can be zero)")
        self.id_list = list(ray_id_list)
        self.weight_list = weight_list if weight_list is not None else [1] * len(self.id_list)
        self.iteration_period = iteration_period
        self.pending_ids = list(self.id_list)
        self.completed_ids = []
        self.update_finished_tasks(timeout=0)
        self.start_time = datetime.datetime.now()

    def update_finished_tasks(self, timeout=None):
        timeout = timeout if timeout is not None else self.iteration_period
        self.completed_ids, self.pending_ids = ray.wait(
            self.id_list, num_returns=len(self.id_list), timeout=timeout)
        assert len(self.completed_ids) + len(self.pending_ids) == len(self.id_list)

    def __iter__(self):
        """This instance is itself iterable.
        """
        return self

    def __next__(self):
        """When next(self) is invoked (directly or using for x in self),
        the lists of complete and pending elements are updated.
        If there are no pending tasks, StopIteration is raised.
        """
        self.update_finished_tasks()
        if not self.pending_ids:
            raise StopIteration
        return self
