#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rull all test modules in the current working dir
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "19/09/2019"

import os
import unittest
import sys
import argparse
import datetime

# So that all tests can use the intended module structure transparently
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
os.chdir(os.path.dirname(os.path.dirname(__file__)))


import enb.ray_cluster

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="Be verbose? Repeat for more", action="count", default=0)
options = parser.parse_known_args()[0]

enb.ray_cluster.init_ray()

if __name__ == '__main__':
    suite = unittest.TestLoader().discover(os.path.dirname(__file__))

    if options.verbose:
        print(f"Running {suite.countTestCases()} tests @ {datetime.datetime.now()}")
        print(f"{'[Params]':-^30s}")
        for param, value in options.__dict__.items():
            print(f"{param}: {value}")
        print(f"{'':-^30s}")
        print()

    unittest.TextTestRunner(verbosity=3 if options.verbose else 1).run(suite)
