#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

import test_all
import enb.atable as atable


class Subclass(atable.ATable):
    @atable.column_function("index_length")
    def set_index_length(self, index, row):
        row["index_length"] = len(index)


class TestATable(unittest.TestCase):
    def test_subclassing(self):
        for parallel in [True, False]:
            df_length = 5
            sc = Subclass(index="index")
            assert sc.column_to_properties["index_length"].fun.__qualname__ == Subclass.set_index_length.__qualname__, \
                (sc.column_to_properties["index_length"].fun, Subclass.set_index_length,
                 Subclass.set_index_length.__qualname__)
            df = sc.get_df(target_indices=["a" * i for i in range(df_length)],
                           parallel_row_processing=parallel)
            assert len(df) == df_length
            assert (df["index_length"].values == range(df_length)).all(), \
                (df["index_length"].values)

if __name__ == '__main__':
    unittest.main()