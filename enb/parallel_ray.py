#!/usr/bin/env python3
"""Tools to execute functions in parallel_decorator using the ray library
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/11/21"

import logging
import shutil
import string
import math
import threading
import time
import sys
import os
import builtins
import subprocess
import random
import pandas as pd
import psutil
import signal
import glob
import platform
import ast
import importlib
import textwrap

import enb
from . import config
from .config import options
from . import log
from .log import logger

# Ray is only expected to be available on linux nodes when clustering is desired.
try:
    import ray

    _ray_present = True
except ImportError as ex:
    _ray_present = False

_ssh_present = shutil.which("ssh") is not None
_sshfs_present = shutil.which("sshfs") is not None
_dpipe_present = shutil.which("dpipe") is not None
_ray_cli_present = shutil.which("ray") is not None


def is_ray_enabled():
    """Return True if and only if ray is available and the current platform is one
    of the supported for ray clustering (currently only linux).
    """
    if not _ray_present:
        return False
    elif platform.system().lower() == "windows":
        return False
    elif not _ray_present:
        logger.debug("The ray library is available but the ray command is not available. Please fix your path.")
        return False
    elif options.no_ray:
        return False
    return True


class HeadNode:
    """Class used to initialize and stop a ray head node.

    The stop() method must be called after start(),
    or a ray cluster will remain active.
    """

    def __init__(self, ray_port, ray_port_count):
        if not is_ray_enabled():
            raise RuntimeError("The ray module is not present or is not available. "
                               "You can install it with 'pip install ray'.")

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
                         + (f" --num-cpus {options.cpu_limit}" if options.cpu_limit else "")
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise RuntimeError(f"Error starting head ray process\n"
                                   f"Command: {repr(invocation)}. Ouput:\n{output}")

        with logger.info_context(f"Initializing ray client on local port {self.ray_port}"):
            # The exported environment consists of all *.py files.
            # Furthermore, the list of current modules minus the ones found after
            # initializing enb is passed as an environment variable to
            # allow the needed imports before parallel_decorator methods are invoked.
            excludes = [os.path.relpath(p, options.project_root)
                        for p in glob.glob(os.path.join(options.project_root, "**", "*"), recursive=True)
                        if os.path.isfile(p) and not p.endswith(".py")]

            modules_needed_remotely = [m.__name__ for m in sys.modules.values()
                                       if hasattr(m, "__name__") and m.__name__ not in options._initial_module_names
                                       and not m.__name__.startswith("_")]

            ray.init(address=f"localhost:{self.ray_port}",
                     _redis_password=self.session_password,
                     runtime_env=dict(working_dir=options.project_root,
                                      excludes=excludes,
                                      env_vars=dict(_needed_modules=str(modules_needed_remotely))),
                     # runtime_env=dict(py_modules=py_modules),
                     logging_level=logging.CRITICAL if options.verbose <= 2 else logging.INFO)

        if options.ssh_cluster_csv_path:
            failing_tool = None
            if not _ssh_present:
                failing_tool = "ssh"
            elif not _sshfs_present:
                failing_tool = "sshfs"
            elif not _dpipe_present:
                failing_tool = "dpipe"
            if failing_tool:
                enb.logger.warn(f"An enb cluster configuration was selected ({repr(options.ssh_cluster_csv_path)}) "
                                f"but {failing_tool} was not found in the path. "
                                f"No remote nodes will be used in this session.\n"
                                f"Please install {failing_tool} in your system and/or fix the path it and retry.")
            else:
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
                        with logger.info_context(f"Connecting to {rn}"):
                            try:
                                rn.connect()
                                connected_nodes.append(rn)
                            except RuntimeError as ex:
                                print(
                                    f"Error connecting to {rn}: {repr(ex)}. Execution will continue without this node.")
                    self.remote_nodes = connected_nodes

                logger.info(f"All ({len(self.remote_nodes)}) nodes connected")

    def stop(self):
        if self.remote_nodes:
            with logger.info_context("Stopping remote nodes...\n", msg_after=f"disconnected all remote nodes."):
                for rn in self.remote_nodes:
                    rn.disconnect()
            self.remote_nodes = []

        with logger.info_context("Disconnecting from ray"):
            ray.shutdown()

        with logger.info_context("Stopping ray server."):
            # This tiny delay allows error messages from child processes to reach the
            # orchestrating process for logging.
            # It might need to be tuned for distributed computation across networks.
            time.sleep(options.preshutdown_wait_seconds)

            invocation = "ray stop --force"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                logger.error("Error stopping ray process. You might need to run `ray stop` manually.\n"
                             f"Command: {repr(invocation)}. Ouput:\n{output}")

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
        assert not is_parallel_process()

        try:
            return self._head_node_address
        except AttributeError:
            self._head_node_address = enb.misc.get_node_ip()
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
    remote_project_mount_path = "~/.enb_remote"

    def __init__(self, address, ssh_port, head_node, ssh_user=None, local_ssh_file=None, cpu_limit=None):
        assert is_ray_enabled()

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
        assert not is_parallel_process()

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

        # Create remote_node_folder_path on the parallel_decorator host if not existing
        with logger.info_context(f"Creating parallel_decorator mount point on {self.address}"):
            invocation = f"ssh -p {self.ssh_port if self.ssh_port else 22} " \
                         f"{'-i ' + self.local_ssh_file if self.local_ssh_file else ''} " \
                         f"{self.ssh_user + '@' if self.ssh_user else ''}{self.address} " \
                         f"mkdir -p {self.remote_project_mount_path}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise RuntimeError(f"Error creating parallel_decorator mount point on {self}.\n"
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
                raise RuntimeError(f"Error starting parallel_decorator ray on {self}.\n"
                                   f"Command: {repr(invocation)}. Ouput:\n{output}")

    def mount_project_remotely(self):
        # Mount the project root on remote_node_folder_path
        invocation = f"dpipe /usr/lib/openssh/sftp-server = " \
                     f"ssh -p {self.ssh_port if self.ssh_port else 22} " \
                     f"{'-i ' + self.local_ssh_file if self.local_ssh_file else ''} " \
                     f"{self.ssh_user + '@' if self.ssh_user else ''}{self.address} " \
                     f"sshfs :{options.project_root} {self.remote_project_mount_path} -C -o sshfs_sync -o slave"

        self.mount_popen = subprocess.Popen(
            invocation, stdout=subprocess.PIPE,
            preexec_fn=os.setsid, shell=True)

        threading.Thread(target=self.mount_popen.communicate, daemon=True).start()

    def disconnect(self):
        assert not is_parallel_process()

        # Create remote_node_folder_path on the parallel_decorator host if not existing
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
        with logger.info_context(f"Initializing ray cluster [CPUlimit={options.cpu_limit}]"):
            if not options.disable_swap:
                # From https://github.com/ray-project/ray/issues/10895 - allow using swap memory when needed,
                # avoiding early termination of jobs due to that.
                os.environ["RAY_DEBUG_DISABLE_MEMORY_MONITOR"] = "1"

            _head_node = HeadNode(ray_port=options.ray_port,
                                  ray_port_count=options.ray_port_count)
            _head_node.start()
            options.head_address = _head_node.get_node_ip()
            logger.verbose(_head_node.status_str)


def stop_ray():
    global _head_node
    if _head_node is not None:
        _head_node.stop()


def is_parallel_process():
    """Return True if and only if the call is made from a parallel_decorator ray process,
    which can be running in the head node or any of the parallel_decorator nodes (if any is present).
    """
    return is_ray_enabled() and os.path.basename(sys.argv[0]) == options.worker_script_name


def is_remote_node():
    """Return True if and only if the call is performed from a parallel_decorator ray process
    running on a node different from the head.
    """
    if not is_ray_enabled():
        return False
    if not is_parallel_process():
        print("Base process")
        return False
    else:
        try:
            return options._name_to_property["head_address"] != enb.misc.get_node_ip()
        except KeyError:
            return False


def is_ray_initialized():
    return is_ray_enabled() and ray.is_initialized


def parallel_decorator(*args, **kwargs):
    """Wrapper of the @`ray.remote` decorator that automatically updates enb.config.options
    for parallel_decorator processes, so that they always access the intended configuration.
    """
    kwargs["num_cpus"] = kwargs["num_cpus"] if "num_cpus" in kwargs else 1
    kwargs["num_gpus"] = kwargs["num_gpus"] if "num_gpus" in kwargs else 0

    def ray_remote_wrapper(f):
        enb.logger.debug(f"Wrapping {f} with ray")

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
            """Wrapper for ray's `.parallel_decorator()` method invoked in the local side.
            It makes sure that `remote_side_wrapper` receives the options argument.
            """
            try:
                try:
                    current_print = builtins.print
                    builtins.print = logger._original_print
                except AttributeError:
                    pass

                # apply ray.put to all arguments before passing them
                return method_proxy.ray_remote(
                    ray.put(dict(config.options.items())),
                    *[ray.put(argument) for argument in a],
                    **{key: ray.put(value) for key, value in k.items()})
            finally:
                builtins.print = current_print

        # method_proxy.remote = local_side_remote
        # method_proxy.start = method_proxy.remote
        del method_proxy.remote
        method_proxy.start = local_side_remote

        return method_proxy

    return ray_remote_wrapper


def get(ids, **kwargs):
    """Call ray's get method with the given arguments.
    """
    return ray.get(ids, **kwargs)


def get_completed_pending_ids(ids, timeout=0):
    """Return the list of completed and pending ids.
    """
    return ray.wait(ids, num_returns=len(ids), timeout=timeout)


def fix_imports():
    """An environment variable is passed to the children processes
    for them to be able to import all modules that were
    imported after loading enb. This prevents the remote
    functions to fail the deserialization process
    due to missing definitions.
    """
    if is_parallel_process():
        imported_modules = set()
        for module_name in sorted(ast.literal_eval(os.environ['_needed_modules'])):
            try:
                importlib.import_module(module_name)
                imported_modules.add(module_name)
            except ImportError as _ex:
                module_parts = module_name.split(".")
                for i in range(1, len(module_parts) - 1):
                    if ".".join(module_parts[:i]) in imported_modules:
                        break
                    else:
                        logger.error(f"Error importing module {repr(module_name)}: {repr(_ex)}.")
