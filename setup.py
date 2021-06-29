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

from setuptools import setup, find_packages
import io
import codecs
import os

here = os.path.abspath(os.path.dirname(__file__))


def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)


setup(
    # Meta
    name='enb',
    version="0.2.7",
    url='https://github.com/miguelinux314/experiment-notebook',
    download_url="https://github.com/miguelinux314/experiment-notebook/archive/v0.2.7.tar.gz",
    license='MIT',
    author='Miguel Hernandez Cabronero (Universitat Autònoma de Barcelona)',
    author_email='miguel.hernandez@uab.cat',
    description='Library to gather and disseminate computer-based experimental results.',
    long_description=read('README.md'),
    platforms='any',
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
        "console_scripts": ["enb=enb.__main__:enb"]
    },

    # Setup config
    setup_requires=['wheel', 'deprecation'],
    install_requires=[
        'wheel', 'deprecation', 'pandas', 'psutil', 'ray[default]', 'matplotlib', 'numpy', 'scipy',
        'recordclass', 'sortedcontainers', 'imageio', 'redis',
        'sphinx_rtd_theme', 'numpngw', 'astropy', 'deprecation'],
    packages=find_packages(),

    include_package_data=True,
)
