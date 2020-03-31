#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

import enb.atable as atable


class Subclass(atable.ATable):
    pass


class Subclass(Subclass):
    @Subclass.column_function("index_length")
    def set_index_length(self, index, series):
        series["index_length"] = len(index)


class TestATable(unittest.TestCase):
    def test_subclassing(self):
        for parallel in [True, False]:
            df_length = 5
            sc = Subclass(index="index")
            assert sc.column_to_properties["index_length"].fun is Subclass.set_index_length
            df = sc.get_df(target_indices=["a" * i for i in range(df_length)],
                           parallel_row_processing=parallel)
            assert len(df) == df_length
            assert (df["index_length"].values == range(df_length)).all()

if __name__ == '__main__':
    unittest.main()