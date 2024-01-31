#!/usr/bin/env python3
"""Installation script for the enb library.

Adapted from
https://www.jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/.

Refer to the user manual (https://miguelinux314.github.io/experiment-notebook)
for additional information on how to install this software.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/09/19"

import os
import importlib
import configparser
from setuptools import setup, find_packages

setup_package_list = ["setuptools", "wheel"]

for module_name in setup_package_list:
    try:
        importlib.import_module(module_name)
    except (ModuleNotFoundError, ImportError) as ex:
        raise ModuleNotFoundError(
            f"\n\n{'@' * 80}\n"
            f"{'@' * 80}\n"
            "\n"
            f"Package {module_name} needs to be installed in your python environment "
            f"to be able to install enb.\n"
            f"The full list of pre-installation requirements is: "
            f"{', '.join(setup_package_list)}.\n\n"
            f"Please run `pip install {' '.join(setup_package_list)}` "
            f"before installing enb\n\n"
            f"{'@' * 80}\n"
            f"{'@' * 80}\n"
            "\n") from ex

# Read the configuration from ./enb/config/enb.ini, section "enb"
enb_options = configparser.ConfigParser()
enb_options.read(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "enb", "config",
                 "enb.ini"))
enb_options = enb_options["enb"]

with open("README.md", "r") as readme_file:
    setup(
        # Metadata about the project
        name=enb_options["name"],
        version=enb_options["version"],
        url=enb_options["url"],
        download_url=enb_options["download_url"],
        license=enb_options["license"],
        author=enb_options["author"],
        author_email=enb_options["author_email"],
        description=enb_options["description"],
        long_description=readme_file.read(),
        long_description_content_type="text/markdown",
        platforms=enb_options["platforms"],
        python_requires=enb_options["python_requires"],
        classifiers=[
            "Programming Language :: Python",
            f"Development Status :: {enb_options['development_status']}",
            "Natural Language :: English",
            "Environment :: Console",
            "Intended Audience :: Developers",
            f"License :: OSI Approved :: {enb_options['license']}",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Topic :: Scientific/Engineering",
        ],

        # UI
        entry_points={
            # Main CLI entry point
            "console_scripts": ["enb=enb.__main__:main"]
        },

        # Dependencies
        setup_requires=setup_package_list,

        install_requires=[
            "pathos", "appdirs", "deprecation", "jinja2>=3.1.2", "matplotlib",
            "numpngw",
            "numpy", "pandas>=1.4.1", "imageio",
            "pdf2image", "psutil", "requests", "scipy", "sortedcontainers",
            "astropy", "natsort", "rich", "h5py"],

        # This part determines the contents of the installed folder in your python's
        # site-packages location.
        # MANIFEST.in is assumed to have been updated, i.e., via git hooks.
        # This allows core plugins and templates to be automatically included.
        packages=[p for p in find_packages() if p.startswith("enb")],
        include_package_data=True)
