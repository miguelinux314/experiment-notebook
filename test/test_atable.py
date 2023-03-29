#!/usr/bin/env python3

import os
import glob
import pickle
import unittest
import string
import numpy as np

import enb.atable
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

    @atable.column_function(
        atable.ColumnProperties("constant_one", plot_min=1, plot_max=1),
        "constant_zero",
        atable.ColumnProperties("first_ten_numbers", has_iterable_values=True),
        atable.ColumnProperties("ascii_table", has_dict_values=True),
    )
    def set_mixed_type_columns(self, index, row):
        row["constant_one"] = 1
        row["constant_zero"] = 0
        row["first_ten_numbers"] = list(range(10))
        row["ascii_table"] = {l: ord(l) for l in string.ascii_letters}


class TestATable(unittest.TestCase):
    def test_subclassing(self):
        """Verify that ATable can be subclassed with well defined behavior
        """
        df_length = 5
        sc = Subclass(index="index")
        assert sc.column_to_properties["index_length"].fun.__qualname__ == Subclass.set_index_length.__qualname__, \
            (sc.column_to_properties["index_length"].fun, Subclass.set_index_length,
             Subclass.set_index_length.__qualname__)
        df = sc.get_df(target_indices=["a" * i for i in range(df_length)])
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
        row = df.iloc[0]
        for i, c in enumerate((chr(o) for o in range(ord("a"), ord("f") + 1)), start=1):
            assert row[c] == i

        assert row["constant_zero"] == 0, row["constant_zero"]
        assert row["constant_one"] == 1, row["constant_one"]
        assert row["first_ten_numbers"] == list(range(10)), row["first_ten_numbers"]
        assert len(row["ascii_table"]) == len(string.ascii_letters), len(row["ascii_table"])
        assert all(v == ord(k) for k, v in row["ascii_table"].items()), row["ascii_table"]


class TestFailingTable(unittest.TestCase):
    def test_always_failing_column(self):
        ft = FailingTable()
        target_indices = string.ascii_letters
        original_verbose = enb.config.options.verbose

        try:
            enb.config.options.verbose = -1
            ft.get_df(target_indices=target_indices)
            enb.config.options.verbose = original_verbose
            raise RuntimeError("The previous call should have failed")
        except enb.atable.ColumnFailedError as ex:
            assert len(ex.exception_list) == len(target_indices)
            pass
        except (NotImplementedError, pickle.PickleError):
            pass
        finally:
            enb.config.options.verbose = original_verbose


class FailingTable(enb.atable.ATable):
    def column_failing(self, index, row):
        raise NotImplementedError("I am expected to crash - no worries!")


class TestSummaryTable(unittest.TestCase):
    def test_summary_table(self):
        base_table = enb.sets.FilePropertiesTable()

        target_paths = [
            p for p in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "*"))
            if os.path.isfile(p)]

        for chunk_size in range(1, len(target_paths)+1):
            enb.config.options.chunk_size = chunk_size

            base_df = base_table.get_df(target_indices=target_paths)

            summary_table = enb.atable.SummaryTable(full_df=base_df)
            summary_df = summary_table.get_df()

            assert summary_df.iloc[0]["group_label"].lower() == "all", summary_df.iloc[0]["group_label"]
            assert summary_df.iloc[0]["group_size"] == len(target_paths)


class CustomType:
    def __init__(self, custom_prop):
        self.custom_prop = custom_prop
        self.other_prop = 2 * custom_prop


class TestObjectColumns(unittest.TestCase):
    def test_object_values(self):
        df = TypesTable().get_df(target_indices=string.ascii_letters)
        assert np.all(df["custom_type_column"].apply(type).str.endswith(CustomType.__name__)), \
            ", ".join(str(type(t)) for t in df["custom_type_column"].unique())
        assert np.all(df["custom_type_column"].apply(lambda ct: ct.custom_prop) == 1)
        assert np.all(df["custom_type_column"].apply(lambda ct: ct.other_prop) == 2)


class TypesTable(enb.atable.ATable):
    @enb.atable.column_function(
        "uppercase",
        "lowercase",
        enb.atable.ColumnProperties(
            "first_last_iterable",
            label="First and last characters of the index",
            has_iterable_values=True),
        enb.atable.ColumnProperties(
            "first_last_dict",
            label="First and last characters of the index",
            has_dict_values=True),
        enb.atable.ColumnProperties(
            "custom_type_column", has_object_values=True)
    )
    def set_columns(self, index, row):
        row["uppercase"] = index.upper()
        row["lowercase"] = index.lower()
        row["first_last_iterable"] = (index[0], index[-1]) if index else []
        row["first_last_dict"] = dict(first=index[0], last=index[-1]) if index else {}
        row["custom_type_column"] = CustomType(custom_prop=len(index))


if __name__ == '__main__':
    unittest.main()
