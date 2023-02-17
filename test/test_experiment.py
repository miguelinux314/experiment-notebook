#!/usr/bin/env python3
"""Unit tests for experiment.py
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2023/02/17"

import unittest
import enb


class TestExperimentTask(unittest.TestCase):
    def test_task_equality(self):
        assert enb.experiment.ExperimentTask() \
               == enb.experiment.ExperimentTask()
        assert enb.experiment.ExperimentTask() \
               == enb.experiment.ExperimentTask(dict())
        assert enb.experiment.ExperimentTask(dict()) \
               == enb.experiment.ExperimentTask()

        assert enb.experiment.ExperimentTask(dict(a=1, b=2)) \
               == enb.experiment.ExperimentTask(dict(a=1, b=2))
        assert enb.experiment.ExperimentTask(dict(a=1, b=2)) \
               != enb.experiment.ExperimentTask(dict(a=1, b=2, c=3))
        assert enb.experiment.ExperimentTask(dict(a=1, b=2)) \
               != enb.experiment.ExperimentTask(dict(a=1))
        assert enb.experiment.ExperimentTask(dict(a=1, b=2)) \
               != enb.experiment.ExperimentTask(dict(a=1, b=100))
        assert enb.experiment.ExperimentTask(dict(a=1, b=2)) \
               != enb.experiment.ExperimentTask(dict(a=1))
        assert enb.experiment.ExperimentTask(dict(a=1, b=2)) \
               != enb.experiment.ExperimentTask(dict())

        assert enb.experiment.ExperimentTask(dict(a=1, b=2)) == \
               enb.experiment.ExperimentTask(dict(a=1, b=2))
        assert enb.experiment.ExperimentTask(dict(a=1, b=2, c=3)) \
               != enb.experiment.ExperimentTask(dict(a=1, b=2))
        assert enb.experiment.ExperimentTask(dict(a=1)) \
               != enb.experiment.ExperimentTask(dict(a=1, b=2))
        assert enb.experiment.ExperimentTask(dict(a=1, b=100)) \
               != enb.experiment.ExperimentTask(dict(a=1, b=2))
        assert enb.experiment.ExperimentTask(dict(a=1)) \
               != enb.experiment.ExperimentTask(dict(a=1, b=2))
        assert enb.experiment.ExperimentTask(dict()) \
               != enb.experiment.ExperimentTask(dict(a=1, b=2))

        class OtherTask(enb.experiment.ExperimentTask):
            pass

        assert enb.experiment.ExperimentTask() != OtherTask()


if __name__ == '__main__':
    unittest.main()
