#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ===================
# Experiment Notebook setup
# ===================
#
# Author: Miguel Hernández Cabronero <miguel.hernandez@uab.cat>
#
# ---------------------------------------------
# INSTALLATION
#
# To install for all users, run
#
# $ sudo python setup.py  install
#
# To install for the current user only, run
#
# $ python setup.py  install --user
# ---------------------------------------------
#
# See documentation for more information and usage examples.
#


# Taken from https://www.jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import io
import codecs
import os
import sys
import glob

here = os.path.abspath(os.path.dirname(__file__))

def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.md')

setup(
    name='enb',
    version="0.2.3",
    url='https://github.com/miguelinux314/experiment-notebook',
    download_url="https://github.com/miguelinux314/experiment-notebook/archive/v0.2.2.tar.gz",
    license='MIT',
    author='Miguel Hernandez Cabronero (Universitat Autònoma de Barcelona)',
    install_requires=['pandas', 'ray', 'matplotlib', 'numpy', 'recordclass', 'sortedcontainers', 'imageio', 'redis', 'sphinx_rtd_theme', 'numpngw'],
    author_email='miguel.hernandez@uab.cat',
    description='Library to gather and disseminate computer-based experimental results.',
    long_description=long_description,
    packages=find_packages(),
    include_package_data=True,
    platforms='any',

    classifiers = [
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
)
