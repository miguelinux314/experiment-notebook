#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ===================
# Experiment Notebook setup
# ===================
#
# Author: Miguel Hernández Cabronero <miguel.hernandez@uab.cat>
#
# ---------------------------------------------
# INSTALLATION (refer to the user manual for additional information)
#
# Option 1) from pip
# 	pip install enb
#
# Option 2) install this once
#  pip install .
#
# Option 3) install this and link to track any changes made to the code
#  pip install .
#
# Tip: use pip install -e . to install a live link so that changes are automatically applied to your environment.
#
# From https://www.jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/
import os

here = os.path.dirname(os.path.abspath(__file__))
# try:
#     # Try to use git tracking to decide what to include in the package
#     from setuptools import setup, find_packages
#     print("[U]sing git tracking for setup...")
# except ImportError:
#     # Falling back to regular installation without git tracking
#     assert not os.path.isdir(os.path.join(here, ".git")), \
#         f"The current source folder {here} contains a .git dir " \
#         f"(indicating it is tracked by git) but could not import setuptools (try `pip install setuptools_git`)"
#     from distutils.core import setup

from setuptools import setup, find_packages

import io


def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)


setup(
    # Metadata about the project
    name='enb',
    version="dev-0.2.8",
    url='https://github.com/miguelinux314/experiment-notebook',
    download_url="https://github.com/miguelinux314/experiment-notebook/archive/v0.2.8.tar.gz",
    license='MIT',
    author='Miguel Hernandez Cabronero (Universitat Autònoma de Barcelona), et al.',
    author_email='miguel.hernandez@uab.cat',
    description='Automated experiment definition, execution and analysis based on a declarative paradigm.',
    long_description=read('README.md'),
    platforms='any',
    python_requires=">=3.6",
    classifiers=[
        'Programming Language :: Python',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering',
    ],
    # UI
    entry_points={
        # Main CLI entry point
        "console_scripts": ["enb=enb.__main__:main"]
    },

    # Setup config
    setup_requires=['wheel', 'deprecation'],
    install_requires=[
        'wheel', 'deprecation', 'pandas', 'psutil', 'ray[default]', 'matplotlib', 'numpy', 'scipy',
        'recordclass', 'sortedcontainers', 'imageio', 'redis',
        'sphinx_rtd_theme', 'numpngw', 'astropy', 'deprecation', 'pdf2image'],

    packages=find_packages(),
    include_package_data=True,
)
