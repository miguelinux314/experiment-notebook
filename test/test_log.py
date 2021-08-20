#!/usr/bin/env python3
"""Unit tests for log.py
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/14"

import unittest
import enb


class TestLog(unittest.TestCase):
    def test_verbose_updates_logging(self):
        original_log_level_name = enb.log.logger.selected_log_level.name
        original_verbosity_level = enb.config.options.verbose
        try:
            levels_by_priority = enb.log.logger.levels_by_priority()
            assert len(levels_by_priority) > 2

            for i in range(1, len(levels_by_priority)):
                assert levels_by_priority[i - 1].priority <= levels_by_priority[i].priority

            for i in range(len(levels_by_priority) - 1):
                for j in range(i + 1, len(levels_by_priority)):
                    enb.config.options.verbose = 0
                    enb.log.logger.selected_log_level = levels_by_priority[i]
                    enb.config.options.verbose = \
                        levels_by_priority[j].priority \
                        - enb.log.logger.level_message.priority
                    assert enb.log.logger.selected_log_level is levels_by_priority[j], \
                        dict(i=i, j=j, verbose=enb.config.options.verbose,
                             selected_level=enb.log.logger.selected_log_level,
                             target_level_j=levels_by_priority[j])

                    enb.config.options.verbose = 0
                    enb.log.logger.selected_log_level = levels_by_priority[j]
                    enb.config.options.verbose += \
                        levels_by_priority[i].priority \
                        - enb.log.logger.level_message.priority
                    assert enb.log.logger.selected_log_level is levels_by_priority[i], \
                        dict(i=i, j=j, verbose=enb.config.options.verbose,
                             selected_level=enb.log.logger.selected_log_level,
                             target_level_i=levels_by_priority[i])
        finally:
            enb.config.options.verbose = original_verbosity_level
            enb.log.logger.selected_log_level = enb.log.get_level(original_log_level_name)


if __name__ == '__main__':
    unittest.main()
