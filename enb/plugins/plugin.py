#!/usr/bin/env python3
"""Tools define plugin installables.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import os
import glob
import inspect
import shutil
import platform
import subprocess
import enb

from .installable import Installable


class Plugin(Installable):
    """Plugins are self-contained, python modules that may assume enb is installed.

    - They can be installed into your projects via the enb CLI (e.g., with `enb plugin install <name> <clone_dir>`),
      and then imported like any other module.

    - The list of plugins available off-the-box can be obtained using the enb CLI (e.g., with `enb plugin list`).

    - Plugins may declare pip dependencies, which are attempted to be satisfied automatically when the plugins
      are installed. In addition, plugins may define their `extra_requirements_message` member to be not None,
      in which case it describes manual intervention required from the user either as a pre-installation
      or post-installation step. That message is shown when attempting to install the plugin with
      not-None `extra_requirements_message`.

    - The __init__.py file is preserved if present. If not present, one is created automatically,
      which imports all symbols from all .py modules in the plugin.
    """

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False):
        """Make a copy of this plugin into `installation_dir`, ready to be imported.
        By default, a verbatim copy of the source plugin's dir is made.
        Any previous contents in installation_dir are overwritten.
        Then any explicit requirements are met (external software may be downloaded
        and pip packages installed).
        
        :param installation_dir: destination dir where the plugin is to be copied to and, when necessary, built.
        :param overwrite_destination: if True, the destination path is deleted before
          installation. If False and installation_dir already exists, an error
          is raised (plugins are intended to be self-contained, isolated python modules).
        """
        if not overwrite_destination and os.path.exists(installation_dir):
            raise ValueError(f"Plugin {repr(cls)} cannot be installed into existing "
                             f"path {installation_dir} because "
                             f"overwrite_destination={overwrite_destination}.")
        super().install(installation_dir=installation_dir,
                        overwrite_destination=True)
        print(f"Plugin {repr(cls.name)} successfully installed into {repr(installation_dir)}.")
        if enb.config.options.verbose:
            cls.print_info()

    @classmethod
    def build(cls, installation_dir):
        """Perform any additional retrieval, compilation and setup necessary for this plugin
        to be importable and usable. By default:

        - The existence of installation_dir as a directory is performed.
        - Install any required apt modules
        - Any needed python modules are installed via pip
        - Cleanup any generic files that might not be needed at this point
        - The __init__.py file is preserved or generated automatically
        """
        # Existence assertion
        assert os.path.isdir(installation_dir), \
            f"{cls.__name__}.build(installation_dir={repr(installation_dir)}): installation_dir does not exist"

        # cleanup
        shutil.rmtree(os.path.join(installation_dir, "__pycache__"), ignore_errors=True)

        # add custom __init__ if needed
        init_path = os.path.join(os.path.dirname(os.path.abspath(inspect.getfile(cls))), "__init__.py")
        with open(os.path.join(installation_dir, "__init__.py"), "w") as init_file:
            if os.path.exists(init_path):
                # An __init__.py file already existed, simply copy it
                with open(init_path, "r") as source_init:
                    init_file.write(source_init.read())
            else:
                # No __init__.py found. Generating one that publishes all symbols by default
                for py_path in [p for p in glob.glob(os.path.join(installation_dir, "*.py"))
                                if not os.path.basename(p).startswith("__")]:
                    module_name = os.path.basename(py_path)[:-3]
                    init_file.write(f"from . import {module_name}\n")
                    init_file.write(f"from .{module_name} import *\n\n")


class PluginMake(Plugin):
    """Plugin that assumes the existence of a valid Makefile in the installation folder,
    and uses it for building the plugin.
    """

    @classmethod
    def build(cls, installation_dir):
        super().build(installation_dir=installation_dir)
        platform_name = platform.system().lower()
        make_path = os.path.join(installation_dir, f"Makefile.{platform_name}")
        if not os.path.exists(make_path):
            make_path = os.path.join(installation_dir, f"Makefile")
        if os.path.exists(make_path):
            print(f"Building downloaded plugin {cls.name}...")
            invocation = f"cd {os.path.dirname(os.path.abspath(make_path))} && make -f {os.path.basename(make_path)}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Error bulding {repr(cls)} with {make_path}. "
                                f"Status = {status} != 0."
                                f"\nInput=[{invocation}].\nOutput=[{output}]")
        else:
            raise ValueError(f"Cannot build {repr(cls)}: no valid makefile "
                             f"in {installation_dir}.")

class PluginJava(Plugin):
    @classmethod
    def build(cls, installation_dir):
        if shutil.which("java") is None:
            enb.logger.warn(f"Warning! The 'java' program was not found in the path, but is required by the {repr(cls.name)} plugin. "
                            f"Installing anyway...")
        super().build(installation_dir=installation_dir)