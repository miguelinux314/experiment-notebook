#!/usr/bin/env python3
# Example code mentioned in the enb.atable documentation
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/10/08"

import enb

if __name__ == '__main__':

    example_indices = ["ab c" * i for i in range(10)]  # It could be any list of iterables

    print(f"{' TableA ':->100s}")


    class TableA(enb.atable.ATable):
        def column_index_length(self, index, row):
            return len(index)


    table_a = TableA(index="my_index_name")
    df = table_a.get_df(target_indices=example_indices)
    for i, (index, row) in enumerate(df.iterrows()):
        assert row["index_length"] == len(row["my_index_name"]), (row["index_length"], len(row["my_index_name"]))
    print(df.head())

    print(f"{' TableB ':->100s}")


    class TableB(TableA):
        @enb.atable.column_function("uppercase", label="Uppercase version of the index")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()

        @enb.atable.column_function(
            enb.atable.ColumnProperties(
                "first_and_last",
                label="First and last characters of the index",
                has_dict_values=True),

            "constant_zero",

            enb.atable.ColumnProperties(
                "space_count",
                label="Number of spaces in the string",
                plot_min=0),

        )
        def function_for_two_columns(self, index, row):
            row["first_and_last"] = {"first": index[0] if index else "", "last": index[-1] if index else ""}
            row["constant_zero"] = 0
            row["space_count"] = sum(1 for c in index if c == " ")


    print(TableB().get_df(target_indices=example_indices).head())

    print(f"{' TableC ':->100s}")


    class TableC(enb.atable.ATable):
        @enb.atable.column_function("uppercase", "lowercase")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()
            row["lowercase"] = index.lower()


    print(TableC)
    print(f"[watch] TableC.column_to_properties={TableC.column_to_properties}")
    print(TableC().get_df(target_indices=example_indices))

    print(f"{' TypesTable ':->100s}")


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
        )
        def set_columns(self, index, row):
            row["uppercase"] = index.upper()
            row["lowercase"] = index.lower()
            row["first_last_iterable"] = (index[0], index[-1]) if index else []
            row["first_last_dict"] = dict(first=index[0], last=index[-1]) if index else {}


    types_df = TypesTable().get_df(target_indices=example_indices)
    print(types_df.head())
    print(types_df.iloc[0])
    print([type(v) for v in types_df.iloc[0]])
