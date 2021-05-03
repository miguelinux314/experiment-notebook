#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

import test_all
import enb.atable as atable


class Subclass(atable.ATable):
    @atable.column_function("index_length")
    def set_index_length(self, index, row):
        row["index_length"] = len(index)

class DefinitionModesTable(atable.ATable):
    """Example ATable subclass that exemplifies multiple ways of defining columns.
    """
    def column_a(self, index, row):
        """Methods that start with column_* are automatically recognized as column definitions.
        The returned value is the value set into the appropriate column of row.
        """
        return 1

    def column_b(self, index, row):
        """Previously defined column values for this row can be used in other columns.
        Columns are computed in the order they are defined."""
        return row["a"] + 1

    @atable.column_function("c")
    def set_column_c(self, index, row):
        """The @enb.atable.column_function decorator can be used to explicitly mark class methods as
        column functions, i.e., functions that set one or more column functions.

        Functions decorated with @enb.atable.column_function must explicitly edit the row parameter
        to update the column function being set.
        """
        row["c"] = row["b"] + 1

    @atable.column_function("d")
    def set_column_d(self, index, row):
        """The _column_name is automatically be defined before calling a decorated (or column_*) function.
        This way, the function code needs not change if the column name is renamed.
        """
        row[_column_name] = row["c"] + 1

    def ignore_column_f(self, index, row):
        """Any number of methods can be defined normally in the ATable subclass.
        These are not invoked automatically by enb.
        """
        raise Exception("This method is never invoked")

    @atable.column_function(
        [atable.ColumnProperties("e"),
         atable.ColumnProperties("f", label="label for f", plot_min=0, plot_max=10)]
    )
    def set_multiple_colums(self, index, row):
        """Multiple columns can be set with the same decorated column function
        (not with undecorated column_* methods).

        The @enb.atable.column_function decorator accepts a list of atable.ColumnProperties instances,
        one per column being set by this function.

        Check out the documentation for atable.ColumnProperties, as it allows providing hints
        for plotting any column individually.
        See https://miguelinux314.github.io/experiment-notebook/using_analyzer_subclasses.html
        for more details.
        """
        row["e"] = row["d"] + 1
        row["f"] = row["e"] + 1


class TestATable(unittest.TestCase):
    def test_subclassing(self):
        """Verify that ATable can be subclassed with well defined behavior
        """
        for parallel in [True, False]:
            df_length = 5
            sc = Subclass(index="index")
            assert sc.column_to_properties["index_length"].fun.__qualname__ == Subclass.set_index_length.__qualname__, \
                (sc.column_to_properties["index_length"].fun, Subclass.set_index_length,
                 Subclass.set_index_length.__qualname__)
            df = sc.get_df(target_indices=["a" * i for i in range(df_length)], parallel_row_processing=parallel)
            assert len(df) == df_length
            assert (df["index_length"].values == range(df_length)).all(), \
                (df["index_length"].values)

    def test_column_definition_modes(self):
        """Test the different methods of adding columns to a table and verify that they work properly.

        Sets the columns from a to f with values from 1 to 6.
        """

        table = DefinitionModesTable()
        df = table.get_df(target_indices=["val0"])
        assert len(df) == 1, len(df)
        for i, c in enumerate((chr(o) for o in range(ord("a"), ord("f") + 1)), start=1):
            assert df.iloc[0][c] == i


if __name__ == '__main__':
    unittest.main()
