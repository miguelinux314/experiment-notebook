#!/usr/bin/env python3
# Example code mentioned in the enb.atable documentation
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/10/08"

import enb

if __name__ == '__main__':

    example_indices = ["ab c" * i for i in range(10)]  # It could be any list of iterables

    print("\n\nA")

    class TableA(enb.atable.ATable):
        def column_index_length(self, index, row):
            return len(index)


    table_a = TableA(index="my_index_name")
    df = table_a.get_df(target_indices=example_indices)
    print(df.head())

    print("\n\nB")

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

    print("\n\nC")

    class TableC(enb.atable.ATable):
        @enb.atable.column_function("uppercase", "lowercase")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()
            row["lowercase"] = index.lower()

    print(TableC)
    print(f"[watch] TableC.column_to_properties={TableC.column_to_properties}")
    
    print(TableC().get_df(target_indices=example_indices))