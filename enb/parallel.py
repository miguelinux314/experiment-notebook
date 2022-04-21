#!/usr/bin/env python3
"""Abstraction layer to provide parallel processing both locally and on ray clusters.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2022/01/02"

import functools
import os
import time
import datetime
import pathos

from .config import options
from . import log
from .log import logger
from . import parallel_ray


def init():
    """If ray is present, this method initializes it.
    If the fallback engine is used, it is ensured that all globals
    are correctly shared with the pool.
    """
    if parallel_ray.is_ray_enabled():
        parallel_ray.init_ray()
    else:
        fallback_init()


def fallback_init():
    """Initialization of the fallback engine. This needs to be called before
    each parallelization, or globals used in the pool might be updated.
    """
    if FallbackFuture.pathos_pool is not None:
        FallbackFuture.pathos_pool.clear()
        FallbackFuture.pathos_pool = None


def chdir_project_root():
    """When invoked, it changes the current working dir to the project's root.
    """
    if parallel_ray.is_parallel_process() and parallel_ray.is_remote_node() and not options.no_remote_mount_needed:
        os.chdir(os.path.expanduser(parallel_ray.RemoteNode.remote_project_mount_path))
    else:
        os.chdir(options.project_root)


def parallel(*args, **kwargs):
    """Decorator for methods intended to run in parallel.

    When ray is available, the .remote() call is performed on the ray decorated function.
    When it is not, a fallback parallelization method is used.

    To run a parallel method `f`, call `f.start` with the arguments you want to pass to f.
    An id object is returned immediately. The result can then be retrieved by calling
    `enb.parallel.get` with the id object.

    Important: parallel calls should not generally read or modify global variables.
    The main exception is enb.config.options, which can be read from parallel calls.
    """
    if parallel_ray.is_ray_enabled():
        return parallel_ray.parallel_decorator(*args, **kwargs)
    else:
        return fallback_parallel_decorator(*args, **kwargs)


def get(ids, **kwargs):
    """Get results for the started ids passed as arguments.

    If timeout is part of kwargs, at most those many seconds are waited.
    Otherwise, this is a blocking call.
    """
    if parallel_ray.is_ray_enabled():
        return parallel_ray.get(ids, **kwargs)
    else:
        return fallback_get(ids, **kwargs)


def get_completed_pending_ids(ids, timeout=0):
    """Given a list of ids returned by start calls, return two lists:
    the first one with the input ids that are ready, and the second
    one with the input ids that are not.
    """
    if parallel_ray.is_ray_enabled():
        return parallel_ray.get_completed_pending_ids(ids, timeout=timeout)
    else:
        return fallback_get_completed_pending_ids(ids, timeout=timeout)


class FallbackFuture:
    """The fallback future is invoked when get is called.
    """
    current_id = 0
    pathos_pool = None

    def __init__(self, f, args, kwargs):
        if self.__class__.pathos_pool is None:
            self.__class__.pathos_pool = pathos.pools.ProcessPool(
                nodes=options.cpu_limit if options.cpu_limit and options.cpu_limit > 0
                else None)
        self.f = f
        self.args = args
        self.kwargs = kwargs
        self.current_id = self.__class__.current_id
        self.__class__.current_id += 1
        self.pathos_result = self.pathos_pool.apipe(f, *args, **kwargs)

    def get(self, **kwargs):
        return self.pathos_result.get(**kwargs)

    def ready(self):
        return self.pathos_result.ready()

    def __hash__(self):
        return hash(self.current_id)


def fallback_parallel_decorator(*decorator_args, **decorator_kwargs):
    """Decorator for methods intended to run in parallel in the local machine.
    """

    def wrapper(f):
        f.start = lambda *_args, **_kwargs: FallbackFuture(f=f, args=_args, kwargs=_kwargs)
        return f

    return wrapper


def fallback_get(ids, **kwargs):
    """Fallback get method when ray is not available.
    """
    return [fallback_future.get(**kwargs) for fallback_future in ids]


def fallback_get_completed_pending_ids(ids, timeout=0):
    """Get two lists, one for completed and one for pending fallback ids.
    """
    complete = []
    pending = []
    for fallback_future in ids:
        if fallback_future.ready():
            complete.append(fallback_future)
        else:
            pending.append(fallback_future)

    time_before = time.time()
    while pending and time.time() - time_before < timeout:
        time.sleep(0.1)
        complete = []
        pending = []
        for fallback_future in ids:
            if fallback_future.ready():
                complete.append(fallback_future)
            else:
                pending.append(fallback_future)

    return complete, pending


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

    def __init__(self, id_list, weight_list=None, iteration_period=1, alive_bar=None):
        """
        Start the background computation of ids returned by start calls of methods decorated with enb.paralell.parallel.
        After this call, the object is ready to receive next() requests.

        :param id_list: list ids whose values are to be returned.
        :param weight_list: if not None, a list of the same length as ray_id list, which contains
          nonnegative values that describe the weight of each task. If provided, they should be highly correlated
          with the computation time of each associated task to provide accurate completion time estimations.
        :param iteration_period: a non-negative value that determines the wait period allowed for ray to
          obtain new results when next() is used. When using this instance in a for loop, it determines approximately
          the periodicity with which the loop body will be executed.
        :param alive_bar: if not None, it should be bar instance from the alive_progress library, 
           while inside its with-context.
           If it is provided, it is called with the fraction of available tasks on each call 
           to `update_finished_tasks`. 
        """
        self.alive_bar = alive_bar
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
        
        if self.alive_bar is not None:
            self.alive_bar(len(self.completed_ids)/len(self.full_id_list))
            

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
