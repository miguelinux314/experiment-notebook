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
import builtins
import subprocess

from . import config
from .config import options
from . import log
from .log import logger


class HeadNode:
    """Class used to initialize and stop a ray head node.

    The stop() method must be called after start(),
    or a ray cluster will remain active.
    """

    def __init__(self, ray_port):
        assert 1 < ray_port < 65535
        self.ray_port = int(ray_port)

    def start(self):
        with logger.verbose_context(f"\nStoping any previous instance of ray..."):
            invocation = "ray stop"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                    status, invocation, output))

        with logger.verbose_context(f"Starting ray on port {self.ray_port}"):
            invocation = f"ray start --head --include-dashboard false --port {self.ray_port} " \
                       + (f" --num-cpus {options.ray_cpu_limit}" if options.ray_cpu_limit else "")
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                    status, invocation, output))

        with logger.verbose_context(f"Initializing ray, conecting to port {self.ray_port}"):
            ray.init(f"0.0.0.0:{self.ray_port}")

    def stop(self):
        # This tiny delay allows error messages from child processes to reach the
        # orchestrating process for logging.
        # It might need to be tuned for distributed computation across networks.
        time.sleep(options.preshutdown_wait_seconds)

        with logger.info_context("Shutting down ray cluster"):
            ray.shutdown()

        with logger.info_context("Stopping head node"):
            invocation = "ray stop"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                    status, invocation, output))

    @property
    def status_str(self):
        """Return a string reporting the status of the cluster"""
        return f"The current enb/ray cluster consists of:\n" \
               f"\t- {len(ray.nodes())} nodes\n" \
               f"\t- {int(ray.cluster_resources()['CPU'])} virtual CPU cores.\n" \
               f"\t- {int(ray.cluster_resources()['GPU']) if 'GPU' in ray.cluster_resources() else 0} GPU devices."

# Single HeadNode instance that controls the ray cluster
_head_node = None


def init_ray():
    """Initialize the ray cluster if it wasn't initialized before.
    """
    global _head_node

    if not ray.is_initialized():
        if _head_node is not None:
            _head_node.stop()

        # Initialize cluster of workers
        with logger.info_context(f"Initializing ray cluster [CPUlimit={options.ray_cpu_limit}]"):
            if not options.disable_swap:
                # From https://github.com/ray-project/ray/issues/10895 - allow using swap memory when needed,
                # avoiding early termination of jobs due to that.
                os.environ["RAY_DEBUG_DISABLE_MEMORY_MONITOR"] = "1"

            _head_node = HeadNode(options.ray_port)
            _head_node.start()
            logger.info(_head_node.status_str)
    else:
        logger.debug(f"Called init_ray with ray alredy initialized")


def stop_ray():
    global _head_node

    if ray.is_initialized:
        assert _head_node is not None
        _head_node.stop()


def on_remote_process():
    """Return True if and only if the call is made from a remote ray process.
    """
    return os.path.basename(sys.argv[0]) == options.worker_script_name


class ProgressiveGetter:
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
        self.full_id_list = list(ray_id_list)
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
        timeout = timeout if timeout is not None else self.iteration_period
        self.completed_ids, self.pending_ids = ray.wait(
            self.full_id_list, num_returns=len(self.full_id_list), timeout=timeout)

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


def remote(*args, **kwargs):
    """Decorator of the @`ray.remote` decorator that automatically updates enb.config.options
    for remote processes, so that they always access the intended configuration.
    """
    kwargs["num_cpus"] = kwargs["num_cpus"] if "num_cpus" in kwargs else 1
    kwargs["num_gpus"] = kwargs["num_gpus"] if "num_gpus" in kwargs else 0

    def enb_remote_wrapper(f):
        def remote_method_wrapper(_opts, *a, **k):
            """Wrapper for the decorated function f, that updates enb.config.options before f is called.
            """
            config.options.update(_opts, trigger_events=False)
            new_level = logger.get_level(logger.level_message.name, config.options.verbose)
            log.logger.selected_log_level = new_level
            log.logger.replace_print()
            return f(*a, **k)

        method_proxy = ray.remote(*args, **kwargs)(remote_method_wrapper)
        method_proxy.ray_remote = method_proxy.remote

        def local_side_remote(*a, **k):
            """Wrapper for ray's `.remote()` method invoked in the local side.
            It makes sure that `remote_side_wrapper` receives the options argument.
            """
            try:
                try:
                    current_print = builtins.print
                    builtins.print = logger._original_print
                except AttributeError:
                    pass

                return method_proxy.ray_remote(_opts=ray.put(dict(config.options.items())), *a, **k)
            finally:
                builtins.print = current_print

        method_proxy.remote = local_side_remote

        return method_proxy

    return enb_remote_wrapper
