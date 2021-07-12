#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ================================
# Experiment Notebook setup script
# ================================
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
#  pip install -e .
#
# Tip: use virtual environments to make sure to have the right package configuration.
#
# Adapted from https://www.jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/.
#

import os
import io
from setuptools import setup, find_packages

here = os.path.dirname(os.path.abspath(__file__))


def read(*filenames, **kwargs):
    """Return the contents of one or more files.
    """
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

    # Dependencies
    setup_requires=['wheel', 'deprecation'],
    install_requires=[
        'wheel', 'deprecation', 'pandas', 'psutil', 'ray[default]', 'matplotlib', 'numpy', 'scipy',
        'recordclass', 'sortedcontainers', 'imageio', 'redis',
        'sphinx_rtd_theme', 'numpngw', 'astropy', 'deprecation', 'pdf2image'],

    # This part determines the contents of the installed folder in your python's site-packages location.
    # MANIFEST.in is assumed to have been updated, i.e., via git hooks.
    # This allows core plugins and templates to be automatically included.
    packages=find_packages(),
    include_package_data=True,
)
