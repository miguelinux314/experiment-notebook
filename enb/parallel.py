#!/usr/bin/env python3
"""Abstraction layer to provide parallel processing both locally and on ray clusters.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2022/01/02"

import functools
import os
import time
import datetime

# import multiprocessing
import concurrent.futures

from . import config
from .config import options
from . import log
from .log import logger
from . import parallel_ray


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
    if parallel_ray.is_ray_enabled():
        return parallel_ray.parallel(*args, **kwargs)
    else:
        return local_parallel(*args, **kwargs)


def get(ids, **kwargs):
    if parallel_ray.is_ray_enabled():
        return parallel_ray.get(ids, **kwargs)
    else:
        return local_get(ids, **kwargs)


def get_completed_pending_ids(ids, timeout=0):
    """Given a list of ids returned by start calls, return two lists:
    the first one with the input ids that are ready, and the second
    one with the input ids that are not.
    """
    if parallel_ray.is_ray_enabled():
        return parallel_ray.get_completed_pending_ids(ids, timeout=timeout)
    else:
        completed_ids = []
        pending_ids = []
        for input_id in ids:
            try:
                get([input_id], timeout=timeout)
                completed_ids.append(input_id)
            except concurrent.futures.TimeoutError:
                pending_ids.append(input_id)

        return completed_ids, pending_ids


def local_parallel(*args, **kwargs):
    """Decorator for methods intended to run in parallel in the local machine.
    """

    def wrapper(f):
        logger.debug(f"Wrapping {f} with multiprocess")
        f.start = lambda *args, **kwargs: local_future_call(f, args, kwargs)
        return f

    return wrapper


_multiprocess_pool = None


def local_future_call(f, args, kwargs):
    global _multiprocess_pool
    if _multiprocess_pool is None:
        _multiprocess_pool = concurrent.futures.ProcessPoolExecutor(
            config.options.ray_cpu_limit if config.options.ray_cpu_limit or config.options.ray_cpu_limit else None)
    submission = _multiprocess_pool.submit(f, *args, **kwargs)

    print(f"[watch] submission={submission}")

    print(f"[watch] f={f}")
    print(f"[watch] args={args}")
    print(f"[watch] kwargs={kwargs}")

    # print(f"[watch] enb.FilePropertiesTable.set_corpus={enb.FilePropertiesTable.set_corpus}")

    print(f"[watch] submission.result()={submission.result()}")

    return submission


def on_multiprocess_error(*args, **kwargs):
    print(f"Error on multiprocess call:")
    print(f"[watch] args={args}")
    print(f"[watch] kwargs={kwargs}")


def local_get(ids, **kwargs):
    """Method to get the results of methods decorated with enb.parallel.multiprocess_parallel.
    """
    return [async_result.result(**kwargs) for async_result in ids]


def chdir_project_root():
    """When invoked, it changes the current working dir to the project's root.
    """
    if parallel_ray.on_parallel_process() and parallel_ray.on_remote_node():
        os.chdir(os.path.expanduser(parallel_ray.RemoteNode.remote_project_mount_path))
    else:
        os.chdir(options.project_root)


class ProgressiveGetter:
    """When an instance is created, the computation of the requested list of calls is started
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

    def __init__(self, id_list, weight_list=None, iteration_period=1):
        """
        Start the background computation of ids returned by start calls of methods decorated with enb.paralell.parallel.
        After this call, the object is ready to receive next() requests.

        :param id_list: list ids whose values are to be returned
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
        self.full_id_list = list(id_list)
        self.weight_list = weight_list if weight_list is not None else [1] * len(self.full_id_list)
        self.id_to_weight = {i: w for i, w in zip(self.full_id_list, self.weight_list)}
        self.iteration_period = iteration_period
        self.pending_ids = list(self.full_id_list)
        self.completed_ids = []
        self.update_finished_tasks(timeout=0)
        self.start_time = time.time_ns()
        self.end_time = None

    def update_finished_tasks(self, timeout=None):
        """Wait for up to timeout seconds or until ray completes computation
        of all pending tasks. Update the list of completed and pending tasks.
        """
        self.completed_ids, self.pending_ids = get_completed_pending_ids(
            self.full_id_list,
            timeout=timeout if timeout is not None else self.iteration_period)

        try:
            if not self.pending_ids and self.end_time is None:
                self.end_time = time.time_ns()
        except AttributeError:
            self.end_time = time.time_ns()

        assert len(self.completed_ids) + len(self.pending_ids) == len(self.full_id_list)

    def report(self):
        """Return a string that represents the current state of this progressive run.
        """
        if self.pending_ids:
            running_nanos = time.time_ns() - self.start_time
        else:
            running_nanos = self.end_time - self.start_time
        seconds = max(0, running_nanos / 1e9)
        seconds, minutes = seconds - 60 * (seconds // 60), seconds // 60
        minutes, hours = int(minutes % 60), int(minutes // 60)

        total_weight = sum(self.id_to_weight.values())
        completed_weight = sum(self.id_to_weight[i] for i in self.completed_ids)

        time_str = f"{hours:02d}h {minutes:02d}min {seconds:02.3f}s"
        percentage_str = f"{100 * (completed_weight / total_weight):0.1f}%"
        now_str = f"(current time: {datetime.datetime.now()})"

        if self.pending_ids:
            return f"Progress report ({percentage_str}): " \
                   f"{len(self.completed_ids)} / {len(self.full_id_list)} completed tasks. " \
                   f"Elapsed time: {time_str} {now_str}."

        else:
            return f"Progress report: completed all {len(self.full_id_list)} tasks in " \
                   f"{time_str} {now_str}."

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
