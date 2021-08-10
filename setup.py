#!/usr/bin/env python3
"""Installation script for the enb library.

Adapted from https://www.jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/.

Refer to the user manual (https://miguelinux314.github.io/experiment-notebook) for additional information on
how to install this software.
"""
__author__ = "Miguel Hernández-Cabronero <miguel.hernandez@uab.cat>"
__since__ = "19/09/2019"

import os
import io
from setuptools import setup, find_packages
import configparser
import subprocess
import sys

# Needed tools to automatically populate the setup
invocation = f"{sys.executable} -m pip install bs4 markdown"
status, output = subprocess.getstatusoutput(invocation)
if status != 0:
    raise RuntimeError("Error installing needed build libraries. "
                       f"Status = {status} != 0.\nInput=[{invocation}].\nOutput=[{output}]")
from bs4 import BeautifulSoup
from markdown import markdown

# Read the configuration from ./enb/config/enb.ini, section "enb"
enb_options = configparser.ConfigParser()
enb_options.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "enb", "config", "enb.ini"))
enb_options = enb_options["enb"]


def strip_markdown_files(*filenames, **kwargs):
    """Return the contents of one or more files.
    """
    # Concatenate the contents of the input files
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    content_concatenation = sep.join(buf).strip()

    # Apply markdown to html and html to text
    html = markdown(content_concatenation)
    return ''.join(BeautifulSoup(html, features="html.parser").findAll(text=True))


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
    long_description=strip_markdown_files('README.md'),
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
    setup_requires=['wheel', 'deprecation', 'bs4', 'markdown'],
    install_requires=[
        'numpy', 'pandas', 'matplotlib', 'scipy', 'ray[default]', 'psutil', 'redis', 'appdirs',
        'imageio', 'numpngw', 'requests', 'astropy', 'jinja2',
        'deprecation', 'recordclass', 'sortedcontainers', 'wheel', 'pdf2image',
    ],

    # This part determines the contents of the installed folder in your python's site-packages location.
    # MANIFEST.in is assumed to have been updated, i.e., via git hooks.
    # This allows core plugins and templates to be automatically included.
    packages=[p for p in find_packages() if p.startswith("enb")],
    include_package_data=True,
)
