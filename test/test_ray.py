#!/usr/bin/env python3
"""Unit tests for the enb's ray subsystem.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/18"

import unittest
import enb
import ray
import time

class TestRay(unittest.TestCase):
    if enb.parallel_ray.is_ray_enabled():
        def test_ray_is_automatically_started(self):
            enb.parallel_ray.init_ray()
            assert ray.is_initialized()

        def test_progress_run(self):
            self.test_ray_is_automatically_started()

            sleep_time = 0.5

            @ray.remote
            def wait_a(_):
                time.sleep(sleep_time)

            @ray.remote
            def wait_b(_):
                time.sleep(sleep_time / 2)

            target_ids = [wait_a.remote(ray.put(_)) for _ in range(5)] \
                         + [wait_b.remote(ray.put(_)) for _ in range(5)]

            pg = enb.parallel.ProgressiveGetter(id_list=target_ids, iteration_period=0.6)

            for i, _ in enumerate(pg):
                assert len(pg.completed_ids) < len(target_ids)
                assert i < 10, pg

            # All ids should be immediately ready after iterating the ProgressiveGet instance
            ray.get(target_ids, timeout=0)
    else:
        def test_skip(self):
            enb.logger.verbose("Skipping ray test because a ray ssh cluster is not selected.")


if __name__ == '__main__':
    unittest.main()
