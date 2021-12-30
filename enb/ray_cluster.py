#!/usr/bin/env python3
"""Tools to connect to ray clusters
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/11/21"

import logging
import string
import math
import threading
import time
import sys
import os
import datetime
import builtins
import subprocess
import random
import pandas as pd
import socket
import ray
import psutil
import signal

from . import config
from .config import options
from . import log
from .log import logger


class HeadNode:
    """Class used to initialize and stop a ray head node.

    The stop() method must be called after start(),
    or a ray cluster will remain active.
    """

    def __init__(self, ray_port, ray_port_count):
        assert ray_port == int(ray_port), ray_port
        assert ray_port_count == int(ray_port_count), ray_port_count
        assert 1025 <= ray_port, ray_port
        assert ray_port_count >= 1
        assert ray_port + ray_port_count - 1 <= 65535, (ray_port, ray_port_count, ray_port + ray_port_count - 1)
        self.ray_port = int(ray_port)
        self.ray_port_count = int(ray_port_count)
        self.session_password = ''.join(random.choices(string.ascii_letters, k=128))
        # List of RemoteNode instances started by this head node
        self.remote_nodes = []
        self.address = self.get_node_ip()

    def start(self):
        with logger.info_context(f"Stoping any previous instance of ray..."):
            invocation = "ray stop --force"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                    status, invocation, output))

        with logger.info_context(f"Starting ray on port {self.ray_port}"):
            invocation = f"ray start --head " \
                         f"--include-dashboard false " \
                         f"--port {self.ray_port} " \
                         f"--ray-client-server-port {self.ray_port + 1} " \
                         f"--node-manager-port {self.ray_port + 2} " \
                         f"--object-manager-port {self.ray_port + 3} " \
                         f"--gcs-server-port  {self.ray_port + 4} " \
                         f"--min-worker-port  {self.ray_port + 5} " \
                         f"--max-worker-port  {self.ray_port + self.ray_port_count - 1} " \
                         f"--redis-password='{self.session_password}' " \
                         + (f" --num-cpus {options.ray_cpu_limit}" if options.ray_cpu_limit else "")
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise RuntimeError(f"Error starting head ray process\n"
                                   f"Command: {repr(invocation)}. Ouput:\n{output}")

        with logger.info_context(f"Initializing ray client on local port {self.ray_port}"):
            ray.init(address=f"localhost:{self.ray_port}",
                     _redis_password=self.session_password,
                     logging_level=logging.CRITICAL)


        if options.ssh_cluster_csv_path:
            if not os.path.exists(options.ssh_cluster_csv_path):
                raise ValueError(f"The cluster configuration file was set to {repr(options.ssh_cluster_csv_path)}"
                                 f"but it does not exist. "
                                 f"Either set enb.config.options.ssh_cluster_csv_path to None "
                                 f"or to an existing file. See "
                                 f"https://miguelinux314.github.io/experiment-notebook/installation.html "
                                 f"for more details.")

            self.remote_nodes = self.parse_cluster_config_csv(options.ssh_cluster_csv_path)
            with logger.info_context(f"Connecting {len(self.remote_nodes)} remote nodes.",
                                     msg_after=f"Done connecting {len(self.remote_nodes)} remote nodes."):
                connected_nodes = []
                for rn in self.remote_nodes:
                    try:
                        with logger.info_context(f"Connecting to {rn}"):
                            rn.connect()
                            connected_nodes.append(rn)
                    except Exception as ex:
                        # Only nodes connected up to this point need to be disconnected.
                        self.remote_nodes = connected_nodes
                        raise ex

            logger.info("All nodes connected")

    def stop(self):
        # This tiny delay allows error messages from child processes to reach the
        # orchestrating process for logging.
        # It might need to be tuned for distributed computation across networks.
        time.sleep(options.preshutdown_wait_seconds)

        with logger.info_context("Stopping ray server"):
            invocation = "ray stop --force"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                logger.error("Error stopping ray process. You might need to run `ray stop` manually.\n"
                             f"Command: {repr(invocation)}. Ouput:\n{output}")

        with logger.info_context("Disconnecting from ray"):
            ray.shutdown()

        if self.remote_nodes:
            with logger.info_context("Stopping remote nodes...\n", msg_after=f"disconnected all remote nodes."):
                for rn in self.remote_nodes:
                    rn.disconnect()
            self.remote_nodes = []

    def parse_cluster_config_csv(self, csv_path):
        """Read a CSV defining remote nodes and return a list with as many RemoteNode as
        data rows in the CSV.
        """

        def clean_value(s, default_value=None):
            return s if (isinstance(s, str) and s) or not math.isnan(s) else default_value

        return [RemoteNode(
            address=clean_value(row["address"], None),
            ssh_user=clean_value(row["ssh_user"], os.getlogin()),
            ssh_port=clean_value(row["ssh_port"], 22),
            local_ssh_file=clean_value(row["local_ssh_file"], None),
            cpu_limit=clean_value(row["cpu_limit"], None),
            head_node=self)
            for _, row in pd.read_csv(csv_path).iterrows()]

    def get_node_ip(self):
        """Adapted from https://stackoverflow.com/a/166589/992926.
        """
        assert not on_remote_process()

        try:
            return self._head_node_address
        except AttributeError:
            self._head_node_address = get_node_ip()
            return self._head_node_address

    @property
    def status_str(self):
        """Return a string reporting the status of the cluster"""
        return f"The current enb/ray cluster consists of:\n" \
               f"\t- {len(self.remote_nodes) + 1} total nodes.\n" + \
               ((f"\t- {len(self.remote_nodes)} remote nodes:\n\t\t * " +
                 f'\n\t\t * '.join(str(rn) for rn in self.remote_nodes) + "\n") if self.remote_nodes else "") + \
               f"\t- {int(ray.cluster_resources()['CPU'])} virtual CPU cores.\n" \
               f"\t- {int(ray.cluster_resources()['GPU']) if 'GPU' in ray.cluster_resources() else 0} GPU devices."


# Single HeadNode instance that controls the ray cluster
_head_node = None


class RemoteNode:
    """Represent a remote node of the cluster, with tools to connect via ssh.
    """
    remote_node_folder_path = "~/.enb_remote"

    def __init__(self, address, ssh_port, head_node, ssh_user=None, local_ssh_file=None, cpu_limit=None):
        self.address = address
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.local_ssh_file = local_ssh_file
        self.head_node = head_node
        self.mount_popen = None
        self.cpu_limit = cpu_limit
        if self.cpu_limit is not None and self.cpu_limit <= 0:
            self.cpu_limit = None

    def connect(self):
        assert not on_remote_process()

        # Create remote_node_folder_path on the remote host if not existing
        with logger.info_context(f"Stopping ray on {self.address}"):
            invocation = f"ssh -p {self.ssh_port if self.ssh_port else 22} " \
                         f"{'-i ' + self.local_ssh_file if self.local_ssh_file else ''} " \
                         f"{self.ssh_user + '@' if self.ssh_user else ''}{self.address} " \
                         f"ray stop --force"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise RuntimeError(f"Error stopping remote ray process on {self}.\n"
                                   f"Command: {repr(invocation)}. Ouput:\n{output}")


        # Create remote_node_folder_path on the remote host if not existing
        with logger.info_context(f"Creating remote mount point on {self.address}"):
            invocation = f"ssh -p {self.ssh_port if self.ssh_port else 22} " \
                         f"{'-i ' + self.local_ssh_file if self.local_ssh_file else ''} " \
                         f"{self.ssh_user + '@' if self.ssh_user else ''}{self.address} " \
                         f"mkdir -p {self.remote_node_folder_path}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise RuntimeError(f"Error creating remote mount point on {self}.\n"
                                   f"Command: {repr(invocation)}. Ouput:\n{output}")

        # Mount the project root on remote_node_folder_path - use a separate process
        self.mount_project_remotely()

        with logger.info_context(f"Starting ray process on {self.address}"):
            invocation = f"ssh -p {self.ssh_port if self.ssh_port else 22} " \
                         f"{'-i ' + self.local_ssh_file if self.local_ssh_file else ''} " \
                         f"{self.ssh_user + '@' if self.ssh_user else ''}{self.address} " \
                         f"ray start --address {self.head_node.address}:{self.head_node.ray_port} " \
                         f"--ray-client-server-port {self.head_node.ray_port + 1} " \
                         f"--node-manager-port {self.head_node.ray_port + 2} " \
                         f"--object-manager-port {self.head_node.ray_port + 3} " \
                         f"--min-worker-port  {self.head_node.ray_port + 5} " \
                         f"--max-worker-port  {self.head_node.ray_port + self.head_node.ray_port_count - 1} " \
                         f"--redis-password='{self.head_node.session_password}' " \
                         + (f" --num-cpus {self.cpu_limit}" if self.cpu_limit else "")
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise RuntimeError(f"Error starting remote ray on {self}.\n"
                                   f"Command: {repr(invocation)}. Ouput:\n{output}")

    def mount_project_remotely(self):
        # Mount the project root on remote_node_folder_path
        invocation = f"dpipe /usr/lib/openssh/sftp-server = " \
                     f"ssh -p {self.ssh_port if self.ssh_port else 22} " \
                     f"{'-i ' + self.local_ssh_file if self.local_ssh_file else ''} " \
                     f"{self.ssh_user + '@' if self.ssh_user else ''}{self.address} " \
                     f"sshfs :{options.project_root} {self.remote_node_folder_path} -C -o sshfs_sync -o slave"

        self.mount_popen = subprocess.Popen(
            invocation, stdout=subprocess.PIPE,
            preexec_fn=os.setsid, shell=True)

        threading.Thread(target=self.mount_popen.communicate, daemon=True).start()

    def disconnect(self):
        assert not on_remote_process()

        # Create remote_node_folder_path on the remote host if not existing
        with logger.info_context(f"Disconnecting {self.address} (stopping ray)"):
            invocation = f"ssh -p {self.ssh_port if self.ssh_port else 22} " \
                         f"{'-i ' + self.local_ssh_file if self.local_ssh_file else ''} " \
                         f"{self.ssh_user + '@' if self.ssh_user else ''}{self.address} " \
                         f"ray stop --force"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                logger.debug(f"Error disconnecting {self}. "
                             f"Command: {repr(invocation)}. Output:\n{output}")

        target_str = f"{self.ssh_user + '@' if self.ssh_user else ''}{self.address} " \
                     f"sshfs :{options.project_root}"
        for proc in psutil.process_iter():
            cmd_str = " ".join(proc.cmdline())
            if target_str in cmd_str:
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    logger.info(f"Cannot kill previously found process {proc.pid}")

    def __repr__(self):
        return f"{self.__class__.__name__}(address={self.address}, " \
               f"ssh_port={self.ssh_port}, ssh_user={self.ssh_user}, " \
               f"local_ssh_file={self.local_ssh_file}, " \
               f"cpu_limit={self.cpu_limit})"


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

            _head_node = HeadNode(ray_port=options.ray_port,
                                  ray_port_count=options.ray_port_count)
            _head_node.start()
            options.head_address = get_node_ip()
            logger.verbose(_head_node.status_str)
    else:
        logger.debug(f"Called init_ray with ray alredy initialized")


def stop_ray():
    global _head_node

    if ray.is_initialized:
        assert _head_node is not None
        _head_node.stop()


def on_remote_process():
    """Return True if and only if the call is made from a remote ray process,
    which can be running in the head node or any of the remote nodes (if any is present).
    """
    return os.path.basename(sys.argv[0]) == options.worker_script_name

def on_remote_node():
    """Return True if and only if the call is performed from a remote ray process
    running on a node different from the head.
    """
    if not on_remote_process():
        return False
    try:
        return options._name_to_property["head_address"] != get_node_ip()
    except AttributeError as ex:
        return False

def get_node_ip():
    """Get the current IP address of this node.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    address = s.getsockname()[0]
    s.close()
    return address

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
