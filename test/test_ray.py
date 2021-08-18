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
    def test_ray_is_automatically_started(self):
        enb.ray_cluster.init_ray()
        assert ray.is_initialized()

    def test_progress_run(self):
        self.test_ray_is_automatically_started()

        sleep_time = 0.3

        @ray.remote
        def wait_a(_):
            time.sleep(sleep_time)

        @ray.remote
        def wait_b(_):
            time.sleep(sleep_time / 2)

        target_ids = [wait_a.remote(ray.put(_)) for _ in range(5)] \
                     + [wait_b.remote(ray.put(_)) for _ in range(5)]

        pg = enb.ray_cluster.ProgressiveGet(ray_id_list=target_ids, iteration_period=0.6)
        time_before = time.time()

        for i, _ in enumerate(pg):
            assert len(pg.completed_ids) < len(target_ids)
            assert i < 10, pg
        time_after = time.time()

        assert time_after - time_before > sleep_time

        # All ids should be immediately ready after iterating the ProgressiveGet instance
        ray.get(target_ids, timeout=0)


if __name__ == '__main__':
    unittest.main()
