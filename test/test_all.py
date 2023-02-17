#!/usr/bin/env python3
"""Run all test modules in the current working dir
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/09/19"

import os
import glob
import shutil
import unittest
import argparse
import datetime

# So that all tests can use the intended module structure transparently

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="Be verbose? Repeat for more",
                    action="count", default=0)
options = parser.parse_known_args()[0]

if __name__ == '__main__':
    # Clean any persistence dirs in test/
    _ = [shutil.rmtree(p)
         for p in glob.glob(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.py"))
         if os.path.isdir(p)]

    suite = unittest.TestLoader().discover(os.path.dirname(__file__))

    if options.verbose:
        print(
            f"Running {suite.countTestCases()} tests "
            f"@ {datetime.datetime.now()}")
        print(f"{'[Params]':-^30s}")
        for param, value in options.__dict__.items():
            print(f"{param}: {value}")
        print(f"{'':-^30s}")
        print()

    unittest.TextTestRunner(verbosity=3, failfast=True).run(suite)

    shutil.rmtree(os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "persistence_test_all.py"),
        ignore_errors=True)
