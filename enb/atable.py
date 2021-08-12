#!/usr/bin/env python3
"""
.. include:: ../tag_definition.rst

:mod:`enb.atable`: Automatic tables with implicit column definition
-------------------------------------------------------------------

|ATable| produces |DataFrame| instances
=======================================

This module defines the |ATable| class,
which is the base for all automatic tables in |enb|.

All |ATable| subclasses generate a |DataFrame| instance
when their `get_df` method is successfully called. These are powerful dynamic tables
that can be used directly, and/or passed to some of the tools in the |aanalysis| module
to easily produce figures and tables.

|ATable| provides automatic persistence
=======================================

The produced tables are automatically stored into persistent disk storage in CSV format.
This offers several key advantages:

- It avoids recalculating already known values. This speeds up subsequent
  calls to `get_df` for the same inputs.

- It allows sharing your raw results in a convenient way.

Using existing |ATable| columns
===============================

|enb| implements several |ATable| subclasses that can be directly used in your code.
All |ATable| subclasses work as follows:

1. They accept an iterable (e.g., a list) of *indices* as an input. An *index* is often a string, e.g.,
   a path to an element of your test dataset. Note that |enb| is capable of creating that list
   of indices if you point it to your dataset folder.

2. For each row, the set of defined data *columns* (e.g., the dependent/independent variables of an experiment)
   is computed and stored to disk along with the row's index.
   You can reuse existing ATable subclasses directly and/or create new subclasses.

Consider the following toy example::

        import enb

        class TableA(enb.atable.ATable):
            def column_index_length(self, index, row):
                return len(index)

Our `TableA` class accepts list-like values (e.g., strings) as indices,
and defines the `index_length` column as the number of elements (e.g., characters) in the index.

One can then use the `get_df` method to obtain a |DataFrame| instance as follows::

        table_a = TableA(index="my_index_name")
        example_indices = ["ab c" * i for i in range(10)]  # It could be any list of iterables
        df = table_a.get_df(target_indices=example_indices)
        print(df.head())

The previous code should produce the following output::

                                  my_index_name index_length
        __atable_index
        ('',)                                              0
        ('ab c',)                          ab c            4
        ('ab cab c',)                  ab cab c            8
        ('ab cab cab c',)          ab cab cab c           12
        ('ab cab cab cab c',)  ab cab cab cab c           16


Note that the `__atable_index` is the dataframe's index, which is set and
used by ATable subclasses internally. This internal index is not
included in the persistence data
(i.e., it is not part of the CSV tables output to disk).
Notwithstanding, the column values needed to build back this index are
stored in the CSV

New columns: defining and composing |ATable| subclasses
=======================================================

|enb| defines many columns in their core and plugin classes.
If you need more, you can easily create new |ATable| subclasses with custom columns,
as explained next.

You can use string, number and boolean types for scalar columns,
and dict-like and list-like (mappings and iterables) for non-scalar columns.

Basic column definition
+++++++++++++++++++++++

The fastest way of defining a column is to subclass |ATable| and to
create methods with names that start with `column_`.
The value returned by these methods is automatically stored
in the appropriate cell of the dataframe.

An example of this approach is copied from `TableA` above::

        import enb

        class TableA(enb.atable.ATable):
            def column_index_length(self, index, row):
                return len(index)

which defines the `index_length` column in that table.

Advanced column definition
++++++++++++++++++++++++++

To further customize your new columns, you can use the |column_function| decorator.

1. You can add column metainformation on how |aanalysis| plots the data by default,
   e.g., labels, ranges, logarithmic axes, etc. An example column with descriptive
   label can be defined as follows::

        @enb.atable.column_function("uppercase", label="Uppercase version of the index")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()

   See the |ColumnProperties| class for all available plotting cues.


2. You can set two or more columns with a single function.
   To do so, you can pass a list of |ColumnProperties| instances to the |column_function| decorator.
   Each instance describes one column, which can be independently customized.

3. You can define columns to contain non-scalar data. The following default types are supported:
   tuples, lists, dicts.

4. You can mix strings and |ColumnProperties| instances in the |column_function| decorator.


The following snippet illustrates points 2 onwards::

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
                row["first_and_last"] = {"first": index[0] if index else "",
                                         "last": index[-1] if index else ""}
                row["constant_zero"] = 0
                row["space_count"] = sum(1 for c in index if c == " ")

After the definition, the table's dataframe can be obtained with
`print(TableB().get_df(target_indices=example_indices).head())` to obtain simething similar to::

                                      file_path index_length         uppercase               first_and_last space_count constant_zero
    __atable_index
    ('',)                                              0                      {'first': '', 'last': ''}           0             0
    ('ab c',)                          ab c            4              AB C  {'first': 'a', 'last': 'c'}           1             0
    ('ab cab c',)                  ab cab c            8          AB CAB C  {'first': 'a', 'last': 'c'}           2             0
    ('ab cab cab c',)          ab cab cab c           12      AB CAB CAB C  {'first': 'a', 'last': 'c'}           3             0
    ('ab cab cab cab c',)  ab cab cab cab c           16  AB CAB CAB CAB C  {'first': 'a', 'last': 'c'}           4             0

"""
__author__ = "Miguel Hernández-Cabronero <miguel.hernandez@uab.cat>"
__since__ = "2019/09/19"

import ast
from builtins import hasattr
import collections
import collections.abc
import copy
import datetime
import functools
import glob
import inspect
import itertools
import math
import os
import sys
import time
import traceback

import deprecation
import ray
import pandas as pd

import enb.config
from enb import config
from enb import ray_cluster
from enb.config import options
from enb.misc import get_defining_class_name


class CorruptedTableError(Exception):
    """Raised when a table is Corrupted, e.g., when loading a
    CSV with missing indices.
    """

    def __init__(self, atable, ex=None, msg=None):
        """
        :param msg: message describing the error that took place
        """
        self.atable = atable
        self.ex = ex
        self.msg = msg

    def __str__(self):
        attribute_strings = []
        for k, v in sorted(self.__dict__.items()):
            attribute_strings.append(f"{k}={repr(v)}")
        return f"{self.__class__.__name__}({', '.join(attribute_strings)})"

    def __repr__(self):
        return self.__str__()


class ColumnFailedError(CorruptedTableError):
    """Raised when a function failed to fill a column.
    """

    def __init__(self, atable=None, index=None, column=None, msg=None, ex=None):
        """
        :param atable: atable instance that originated the problem
        :param column: column where the problem happened
        :param ex: exception that lead to the problem, or None
        :param msg: message describing the problem, or None
        """
        super().__init__(atable=atable, msg=msg, ex=ex)
        self.index = index
        self.column = column


class ColumnProperties:
    """
    All columns defined in an |ATable| subclass have a corresponding |ColumnProperties| instance,
    which provides metainformation about it. Its main uses are providing plotting
    cues and to allow non-scalar data (tuples, lists and dicts).

    Once an |ATable| subclass c is defined, `c.column_to_properties` contains a mapping from
    a column's name to its ColumnProperties instance.

    It is possible to change attributes of column properties instances, and to replace
    the ColumnProperties instances in `column_to_properties`.

    For instance, one may want to
    plot a column with its original cues first, and then create a second version with semi-logarithmic
    axes. Then it would suffice to use |aanalysis| tools with the |ATable| subclass default `column_to_properties`
    first, then modify one or more ColumnProperties instances, and finally apply the same tools again.
    """

    def __init__(self, name, fun=None, label=None,
                 plot_min=None, plot_max=None,
                 semilog_x=False, semilog_y=False,
                 semilog_x_base=10, semilog_y_base=10,
                 hist_label=None, hist_min=None, hist_max=None,
                 hist_bin_width=None,
                 has_dict_values=False,
                 has_iterable_values=False,
                 hist_label_dict=None,
                 **extra_attributes):
        """
        Column-function linking:
        :param name: unique name that identifies a column.
        :param fun: function to be invoked to fill a column value. If None, |enb| will set this for you
          when you define columns with `column_` or |column_function|.

        Type specification:
        :param has_dict_values: set to True if and only if the column cells contain value mappings (i.e., dicts),
          as opposed to scalar values. Both keys and values should be valid scalar values (numeric, string or boolean).
          It cannot be True if `has_iterable_values` is True.
        :param has_iterable_values: set to True if and only if the column cells should contain iterables,
          i.e., tuples or lists. It cannot be True if `has_dict_values` is True.
        The has_ast_values property of the ColumnProperties instance will return true if and only if
        either of these arguments is True.

        Plot rendering hints:
        :param label: descriptive label of the column, intended to be displayed in plot (e.g., axes) labels
        :param plot_min: minimum value to be plotted for the column. For histograms,
          this refers to the range of key (X-axis) values.
        :param plot_max: minimum value to be plotted for the column. For histograms,
          this refers to the range of key (X-axis) values.
        :param semilog_x: True if a log scale should be used in the X axis
        :param semilog_y: True if a log scale should be used in the Y axis
        :param semilog_x_base: log base to use if semilog_x is true
        :param semilog_y_base: log base to use if semilog_y is true

        Parameters specific to histograms, only applicable when has_dict_values is True.
        :param hist_bin_width: histogram bin used when calculating distributions
        :param hist_label_dict: None, or a dictionary with x-value to label dict
        :param secondary_label: secondary label for the column, i.e., the Y axis
          of an histogram column.
        :param hist_min: if not None, the minimum value to be plotted in histograms.
          If None, the AAnalyzer instance decides the range (typically (0,1)).
        :param hist_max: if not None, the maximum value to be plotted in histograms.
          If None, the AAnalyzer instance decides the range (typically (0,1)).
        :param hist_label: if not None, the label to be shown globally in the Y axis.

        User-defined attributes:
        :param **extra_extra_attributes: any parameters passed are set as attributes of the created
          instance (with __setattr__). These attributes are not directly used by |enb|'s core,
          but can be safely used by host code.
        """
        self.name = name
        self.fun = fun
        self.label = label if label is not None else str(name)
        self.plot_min = plot_min
        self.plot_max = plot_max
        self.semilog_x = semilog_x
        self.semilog_y = semilog_y
        self.semilog_x_base = semilog_x_base
        self.semilog_y_base = semilog_y_base
        self.hist_bin_width = hist_bin_width
        self.has_dict_values = has_dict_values or self.hist_bin_width is not None
        self.has_iterable_values = has_iterable_values
        if self.has_dict_values and self.has_iterable_values:
            raise ValueError(
                "has_dict_values and has_iterable_values cannot be both set to True at once")
        self.hist_label_dict = hist_label_dict
        self.hist_label = hist_label
        self.hist_min = hist_min
        self.hist_max = hist_max
        for k, v in extra_attributes.items():
            self.__setattr__(k, v)

    @property
    def has_ast_values(self):
        """Determine whether this column requires ast for literal parsing,
        e.g., for supported non-scalar data: dicts and iterables.
        """
        return self.has_dict_values or self.has_iterable_values

    def __repr__(self):
        args = ", ".join(f"{repr(k)}={repr(v)}" for k, v in self.__dict__.items() if v is not None)
        return f"{self.__class__.__name__}({args})"


class MetaTable(type):
    """Metaclass for |ATable| and all subclasses, which
    guarantees that the column_to_properties is a static OrderedDict instance
    different from other classes' column_to_properties. This way,
    |ATable| and all subclasses can access and update
    their dicts separately for each class, effectively allowing to split
    the definition of columns across multiple |ATable| instances.

    Note: Table classes should inherit from |ATable|, not |MetaTable|.
    You probably don't ever need to use this class directly.
    """
    pendingdefs_classname_fun_columnpropertylist_kwargs = []

    def __new__(cls, name, bases, dct):
        if MetaTable in bases:
            raise SyntaxError(f"Please use ATable, not MetaTable, for subclassing.")

        # Explore parent classes and search for all column_to_properties definitions,
        # so that they are inherited into the subclass cls.
        unique_bases = []
        for base in bases:
            if base in unique_bases:
                continue
            try:
                _ = base.column_to_properties
            except AttributeError:
                base.column_to_properties = collections.OrderedDict()
            unique_bases.append(base)
        bases = tuple(unique_bases)

        # The |ATable| subclass is initialized and its column_to_properties
        # is filled by default with the parent classes' definitions.
        dct.setdefault("column_to_properties", collections.OrderedDict())
        subclass = super().__new__(cls, name, bases, dct)
        for base in bases:
            try:
                # It is ok to update keys later decorated in the
                # subclasses. That happens after meta-creation,
                # therefore overwrites the following updates
                subclass.column_to_properties.update(base.column_to_properties)
            except AttributeError:
                pass

        # Make sure that subclasses do not re-use a base class column
        # function name without it being decorated as column function
        # (unexpected behavior).
        MetaTable.assert_unreported_overwrite(subclass)

        # Add pending decorated and column_* methods (declared as columns before subclass existed),
        # in the order they were declared (needed when there are data dependencies between columns).
        inherited_classname_fun_columnproperties_kwargs = [
            t for t in cls.pendingdefs_classname_fun_columnpropertylist_kwargs
            if t[0] != subclass.__name__]
        decorated_classname_fun_columnproperties_kwargs = [
            t for t in cls.pendingdefs_classname_fun_columnpropertylist_kwargs
            if t[0] == subclass.__name__]
        for classname, fun, cp, kwargs in inherited_classname_fun_columnproperties_kwargs:
            ATable.add_column_function(cls=subclass, fun=fun, column_properties=cp, **kwargs)

        # Column functions are added to a list while the class is being defined.
        # After that, the subclass' column_to_properties attribute is updated according
        # to the column definitions.
        funname_to_pending_entry = {t[1].__name__: t for t in decorated_classname_fun_columnproperties_kwargs}

        for fun in (f for f in subclass.__dict__.values() if inspect.isfunction(f)):
            try:
                # Decorated function: the column properties are already present
                classname, fun, cp_list, kwargs = funname_to_pending_entry[fun.__name__]
                for cp in cp_list:
                    ATable.add_column_function(cls=subclass, fun=fun, column_properties=cp, **kwargs)
                del funname_to_pending_entry[fun.__name__]
            except KeyError:
                # Non decorated function: decorate automatically if it starts with 'column_*'
                assert all(cp.fun is not fun for cp in subclass.column_to_properties.values())
                if not fun.__name__.startswith("column_"):
                    continue
                column_name = fun.__name__[len("column_"):]
                if not column_name:
                    raise SyntaxError(f"Function name '{fun.__name__}' not allowed in ATable subclasses")
                wrapper = MetaTable.get_auto_column_wrapper(fun=fun)
                cp = ColumnProperties(name=column_name, fun=wrapper)
                ATable.add_column_function(cls=subclass, fun=fun, column_properties=cp)

        assert len(funname_to_pending_entry) == 0, (subclass, funname_to_pending_entry)
        cls.pendingdefs_classname_fun_columnpropertylist_kwargs.clear()

        return subclass

    @staticmethod
    def assert_unreported_overwrite(subclass):
        """
        Raise a SyntaxError if any of the methods defined in subclass overwrites
        (i.e., defines a method with the same name as)
        a parent's class method and two conditions are met:

        - subclass' parent(s) defined the method as a column function
        - subclass does not use the @|redefines_column| decorator

        If the subclass does use @|redefines_column|, then no error is raised and
        subclass is updated to reflect this change.

        Note that this syntax restriction is imposed to maintain OOP intuitions true about
        column functions, or raise the appropriate SyntaxError.
        Otherwise, the parent's method would be invoked to fill in the |DataFrame|,
        even though subclass has a method with the same name. This is opposed
        to basic OOP principles, and thus is not allowed.
        """
        for column, properties in subclass.column_to_properties.items():
            try:
                defining_class_name = get_class_that_defined_method(properties.fun).__name__
            except AttributeError:
                defining_class_name = None
            if defining_class_name != subclass.__name__:
                ctp_fun = properties.fun
                try:
                    sc_fun = getattr(subclass, properties.fun.__name__)
                except AttributeError:
                    # Not overwritten, nothing else to check here
                    continue

                if ctp_fun != sc_fun:
                    if get_defining_class_name(ctp_fun) != get_defining_class_name(sc_fun):
                        if hasattr(sc_fun, "_redefines_column"):
                            properties = copy.copy(properties)
                            properties.fun = ATable.build_column_function_wrapper(fun=sc_fun,
                                                                                  column_properties=properties)
                            subclass.column_to_properties[column] = properties
                        else:
                            # NOTE: it is technically possible to change
                            raise SyntaxError(f"{defining_class_name}'s subclass {subclass.__name__} "
                                              f"overwrites method {properties.fun.__name__}, "
                                              f"but it does not decorate it with @enb.atable.column_function "
                                              f"for column {column} - please add the decorator manually.")

    @staticmethod
    def get_auto_column_wrapper(fun):
        """Create a wrapper for a function with a signature compatible with column-setting functions,
        so that its returned value is assigned to the row's column.
        """

        def wrapper(self, index, row):
            f"""Column wrapper for {fun.__name__}"""
            row[_column_name] = fun(self, index, row)

        return wrapper


class ATable(metaclass=MetaTable):
    """Automatic table with implicit column definition.

    ATable subclasses' have the `get_df` method, which returns a |DataFrame| instance with
    the requested data. You can use (multiple) inheritance using one or more ATable subclasses
    to combine the columns of those subclasses into the newly defined one. You can then define
    methods with names that begin with `column_`, or using the
    `@enb.atable.column_function` decorator on them.

    See |atable| for more detailed help and examples.
    """
    # Default input sample extension. If affects the result of enb.atable.get_all_test_files,
    # filtering out any file that does not end with the given string. Leave empty not to filter out
    # any file found in the data dir.
    #
    # Update in subclasses as needed
    dataset_files_extension = ""

    # Name of the index used internally
    private_index_column = "__atable_index"
    # Column names in this list are not retrieved nor saved to file
    ignored_columns = []

    def __init__(self, index="index", csv_support_path=None, column_to_properties=None):
        """
        :param index: string with column name or list of column names that will be
          used for indexing. Indices provided to self.get_df must be
          either one instance (when a single column name is given)
          or a list of as many instances as elements are contained in self.index.
          See self.indices
        :param csv_support_path: path to a file where this ATable contents
          are to be stored and retrieved. If None, persistence is disabled.
        :param column_to_properties: if not None, it is a mapping from strings to callables
          that defines the columns of the table and how to obtain the cell values
        """
        self.index = index
        self.csv_support_path = csv_support_path
        if column_to_properties is not None:
            self.column_to_properties = collections.OrderedDict(column_to_properties)

        # # Rows get a timestamp column automatically
        # self.add_column_function(
        #     cls=self.__class__, fun=lambda self, index, row: row["row_created"] = datetime.datetime.now, column_properties=ColumnProperties(
        #         "row_created", label="Row creation time"))

        #  Whenever a row is returned by get_df, it is complete, i.e.,
        #  it contains data in all defined columns.
        #  This column is set to False by |enb| when new columns
        #  are defined in the table. After that, only rows
        #  requested via `target_indices` are marked back as complete
        #  once `get_df` finishes their computation.
        # self.add_column_function(
        #     cls=self.__class__, fun=lambda: True, column_properties=ColumnProperties(
        #         "row_complete", label="Are all columns in the row present?"))

    # Methods related to defining columns and retrieving them afterwards

    @classmethod
    def column_function(cls, *column_properties, **kwargs):
        """Decorator for functions that produce values for column_name when
        given the current index and current column values.

        Decorated functions are expected to have signature (atable, index, row),
        where atable is an ATable instance,
        index is a tuple of index values (corresponding to self.index),
        and row is a dict-like instance to be filled in by f.

        Columns are sorted by the order in which they are defined, i.e., when
        a function is decorated for the corresponding column.
        Redefinitions are not allowed.

        A variable _column is added to the decorated function's scope, e.g.,
        to assign values to the intended column of the row object.

        :param column_properties: a list of one or more of the following types of elements:

          * a string with the column's name to be used in the table. A new |ColumnProperties| instance
            is then created, passing `**kwargs` to the initializer.

          * a ColumnProperties instance. In this case `**kwargs` is ignored.
        """

        def decorator_wrapper(fun):
            return ATable.add_column_function(
                *column_properties, cls=cls, fun=fun, **kwargs)

        return decorator_wrapper

    @classmethod
    def redefines_column(cls, fun):
        """Decorator to be applied on overwriting methods that are meant to fill
        the same columns as the base class' homonym method.
        """
        fun._redefines_column = True
        return fun

    @staticmethod
    def add_column_function(cls, fun, column_properties, **kwargs):
        """Main entry point for column definition in |ATable| subclasses.

        Methods decorated with |column_function|, or with a name beginning with `column_`
        are automatically "registered" using this function. It can be invoked
        directly to add columns manually, although it is not recommended in most scenarios.

        :param cls: the |ATable| subclass to which a new column is to be added.
        :param column_properties: a |ColumnProperties| instance describing the
          column to be created. This list may also contain strings, which are interpreted
          as column names, creating the corresponding columns.
        :param fun: column-setting function. It must have a signature compatible with a call
          `(self, index, row)`, where `index` is the row's index and `row` is a dict-like
          object where the new column is to be stored. Previously set columns can also be
          read from `row`. When a column-setting method is decorated,
          fun is automatically set so that the decorated method is called, but it is not guaranteed
          that fun is the decorated method.
        """
        if not issubclass(cls, ATable):
            raise SyntaxError("Column definition is only supported for classes that inherit from ATable, "
                              f"but {cls} was found.")
        if not isinstance(column_properties, ColumnProperties):
            raise SyntaxError("Only subclasses of ColumnProperties are allowed for the column_properties argument "
                              f"(found type {type(column_properties)} -- {column_properties})")

        # Effectively register the column function into the class
        fun_wrapper = cls.build_column_function_wrapper(fun=fun, column_properties=column_properties)
        column_properties.fun = fun_wrapper
        cls.column_to_properties[column_properties.name] = column_properties

        return fun_wrapper

    @staticmethod
    def normalize_column_function_arguments(column_property_list, fun, **kwargs):
        """Helper method to verify and normalize the `column_property_list` varargs passed to add_column_function.
        Each element of that list is passed as the `column_properties` argument to this function.

        - If the element is a string, it is interpreted as a column name, and a new ColumnProperties
          object is is created with that name and the `fun` argument to this function. The kwargs argument
          is passed to that initializer.

        - If the element is a |ColumnProperties| instance, it is returned without modification.
          The kwargs argument is ignored in this case.

        - Otherwise, a SyntaxError is raised.

        :param column_property_list: one of the elements of the `*column_property_list` parameter to add_column_function.
        :param fun: the function being decorated.

        :return: a nonempty list of valid ColumnProperties instances
        """
        normalized_cp_list = []
        for cp in column_property_list:
            if isinstance(cp, str):
                normalized_cp_list.append(ColumnProperties(name=cp, fun=fun, **kwargs))
            elif isinstance(cp, ColumnProperties):
                normalized_cp_list.append(cp)
            elif isinstance(cp, collections.abc.Iterable):
                # Deprecated
                ATable._normalize_list_of_column_properties()
                normalized_cp_list.extend(ATable.normalize_column_function_arguments(
                    column_property_list=cp, fun=fun))
            else:
                raise SyntaxError("Invalid arguments passed to add_column_function: "
                                  f"{cp} (type {type(cp)}), {fun}, {kwargs} ")
        return normalized_cp_list

    @staticmethod
    @deprecation.deprecated(
        deprecated_in="0.3.0",
        removed_in="1.0.0",
        current_version=enb.config.ini.get_key("enb", "version"),
        details="Passing a list of column properties such as "
                "@enb.atable.column_function([cp1,cp2]) instead "
                "of passing them as positional arguments,"
                "@enb.atable.column_function(cp1,cp2) is deprecated")
    def _normalize_list_of_column_properties():
        """It does nothing. Method defined just to provide deprecation information when
        the old interface is used.
        """
        pass

    @classmethod
    def build_column_function_wrapper(cls, fun, column_properties):
        """Build the wrapper function applied to all column-setting functions given
        a column properties instance.

        |ATable|'s implementation of `build_column_function_wrapper` adds two variables
        to the column-setting function's scope: `_column_name` and `_column_properties`,
        in addition to verifying the column-setting function's signature.

        Notwithstanding, this behavior can be altered in |ATable| subclasses, affecting only
        the wrappers for that class' column-setting functions.

        :param fun: function to be called by the wrapper.
        :param column_properties: |ColumnProperties| instance with properties associated to the column.
        :return: a function that wraps fun adding `_column_name` and `_column_properties` to its scope.
        """
        # Math fun's signature with the expected one (self, index, row). Variable names are not checked.
        fun_spec = inspect.getfullargspec(fun)
        if len(fun_spec.args) != 3 or any(v is not None for v in (fun_spec.varargs, fun_spec.varkw)):
            raise SyntaxError(f"Trying to add a column-setting method {fun} to {cls.__name__}, "
                              f"but an invalid signature was found. "
                              f"Column-setting methods should have a (self, index, row) signature. "
                              f"Instead, the following signature was provided: {fun_spec}.")

        # Create a wrapper that adds some temporary globals
        @functools.wraps(fun)
        def fun_wrapper(self, index, row):
            if isinstance(fun, functools.partial):
                globals = fun.func.__globals__
            else:
                globals = fun.__globals__

            old_globals = dict(globals)
            globals.update(_column_name=column_properties.name,
                           _column_properties=column_properties)
            try:
                returned_value = fun(self, index, row)
                if returned_value is not None:
                    row[column_properties.name] = returned_value
            finally:
                globals.clear()
                globals.update(old_globals)

        return fun_wrapper

    @property
    def indices(self):
        """If `self.index` is a string, it returns a list with that column name.
        If self.index is a list, it returns `self.index`.
        Useful to iterate homogeneously regardless of whether single or multiple indices are used.
        """
        return unpack_index_value(self.index)

    @property
    def indices_and_columns(self):
        """:return: a list of all defined columns, i.e., those for which a function has been defined.
        """
        return self.indices + list(k for k in self.column_to_properties.keys()
                                   if k not in itertools.chain(self.indices, self.ignored_columns))

    # Methods to generate a DataFrame instance with the requested data

    def get_df(self, target_indices=None, target_columns=None,
               fill=None, overwrite=None, parallel_row_processing=None,
               chunk_size=None):
        """Core method for all |ATable| subclasses to obtain the table's content.
        The following principles guide the way `get_df` works:

        - This method returns a |DataFrame| containing
          one row per element in `target_indices`,
          and as many columns as there are defined in self.column_to_properties.
          If `target_indices` is None, all files in enb.config.options.base_dataset_dir
          are used (after filtering by self.dataset_files_extension) by default.

        - Any persistence data already present is loaded, and only new
          indices or columns are added. This way, each column-setting function
          needs to be called only once per index for any given |ATable| subclass.

        - Results are returned only for `target_indices`, even if you previously computed
          other rows. Thus, only not-already-present indices and new columns require
          actual computation. Any new result produced by this call is appended to the already
          existing persistence data.

        - Rows computed in a previous call to this `get_df` are not deleted from
          persistent data storage, even if `target_indices` contains fewer or different
          indices than in previous calls.

        - Beware that if you remove a column definition from this |ATable| subclass and run `get_df`,
          that column will be removed from persistent storage. If you add a new column,
          that value will be computed for all rows in `target_indices`,

        - You can safely select new and/or different `target_indices`. New data are stored, and existent
          rows are not removed. If you add new column definitions, those are computed for `target_indices`
          only. If there are other previously existing rows, they are flagged as incomplete, and
          those new columns will be computed only when those rows' indices are included in `target_indices`.

        Recall that table cell values are restricted to be
        numeric, string, boolean or non-scalar, i.e., list, tuple or dict.

        :param target_indices: list of indices that are to be contained in the table, or None to infer
          automatically from the dataset.
        :param target_columns: if not None, it must be a list of column names (defined for this class) that
          are to be obtained for the specified indices. If None, all columns are used.
        :param fill: If True or False, it determines whether values are computed for the selected indices.
          If None, values are only computed if enb.config.options.no_new_results is False.
        :param overwrite: values selected for filling are computed even if they are present
          in permanent storage. Otherwise, existing values are skipped from the computation.
        :param parallel_row_processing: if True, processing of rows is performed in a parallel,
           possibly distributed fashion. Otherwise, they are processed serially using the invoking thread.
        :param chunk_size: If None, its value is assigned from options.chunk_size. After this,
           if not None, the list of target indices is split in
           chunks of size at most chunk_size elements (each one corresponding to one row in the table).
           Results are made persistent every time one of these chunks is completed.
           If None, a single chunk is defined with all indices.

        :return: a DataFrame instance containing the requested data
        :raises: CorruptedTableError, ColumnFailedError, when an error is encountered
          processing the data.
        """
        # ATable subclasses make automatic use of ray's parallelization
        # capabilities. This initializes the ray subsystem if it was not
        # up already.
        ray_cluster.init_ray()

        target_columns = target_columns if target_columns is not None else list(self.column_to_properties.keys())

        overwrite = overwrite if overwrite is not None else options.force
        fill = fill if fill is not None else options.no_new_results is False
        parallel_row_processing = parallel_row_processing if parallel_row_processing is not None \
            else not options.sequential

        # Use the provided target indices or discover automatically from the dataset folder
        target_indices = list(target_indices) if target_indices is not None \
            else get_all_input_files(ext=self.dataset_files_extension)
        if not target_indices:
            raise ValueError("No target indices could be found. "
                             "Double check that the base_dataset_dir is correctly "
                             "set and that you are passing the right value to the "
                             "`target_indices` argument of get_df().")

        # Split the work into one or more chunks, which are completed before moving on to the next one.
        chunk_size = chunk_size if chunk_size is not None else options.chunk_size
        chunk_size = chunk_size if chunk_size is not None else len(target_indices)
        if chunk_size <= 0:
            raise SyntaxError(f"Invalid chunk_size {chunk_size}. Re-run with -h for syntax help.")
        chunk_list = [target_indices[i:i + chunk_size]
                      for i in range(0, len(target_indices), chunk_size)]
        assert len(chunk_list) > 0

        if fill:
            for i, chunk in enumerate(chunk_list):
                if options.verbose:
                    print(
                        f"[{self.__class__.__name__}:get_df] Starting chunk {i + 1}/{len(chunk_list)} (chunk_size={chunk_size}, "
                        f"{100 * i * chunk_size / len(target_indices):.1f}"
                        f"-{min(100, 100 * ((i + 1) * chunk_size) / len(target_indices)):.1f}%) "
                        f"@ {datetime.datetime.now()}")
                df = self.get_df_one_chunk(
                    target_indices=chunk, target_columns=target_columns,
                    fill=True,
                    overwrite=overwrite, parallel_row_processing=parallel_row_processing,
                    run_sanity_checks=False)

        if len(chunk_list) > 1 or not fill:
            # Get the full df if needed
            df = self.get_df_one_chunk(
                target_indices=target_indices, target_columns=target_columns,
                fill=False,
                overwrite=False,
                parallel_row_processing=parallel_row_processing,
                run_sanity_checks=enb.config.options.force_sanity_checks)

        return df

    def get_df_one_chunk(self, target_indices, target_columns, fill,
                         overwrite, parallel_row_processing, run_sanity_checks):
        """Internal implementation of the :meth:`get_df` functionality,
        to be applied to a single chunk of indices. It is essentially a self-contained
        call to meth:`enb.atable.ATable.get_df` as described in its documentation, where
        data are stored in memory until all computations are done, and then the persistent storage
        is updated if needed.

        :param target_columns: list of indices for this chunk
        :param target_columns: list of column names to be filled in this call
        :param fill: if False, results are not computed (they default to None). Instead,
          only data in persistent storage is used.
        :param overwrite: values selected for filling are computed even if they are present
          in permanent storage. Otherwise, existing values are skipped from the computation.
        :param parallel_row_processing: if True, processing of rows is performed in a parallel,
           possibly distributed fashion. Otherwise, they are processed serially using the invoking thread.
        :param run_sanity_checks: if True, sanity checks are performed on the data

        :return: a DataFrame instance containing the requested data
        :raises ColumnFailedError: an error was encountered while computing the data.
        """
        # Load all data stored in persistence, or get an empty dataframe.
        # Either way, all columns in self.indices_and_columns are defined.
        loaded_table = self.load_saved_df(run_sanity_checks=run_sanity_checks)

        # Target index values are marshalled into unique strings,
        # which are the actual index used in the dataframe.
        target_locs = [indices_to_internal_loc(v) for v in target_indices]

        # If the data is already available for all target indices,
        # there is no need to run the computations for those rows.
        # This inner join efficiently queries the loaded table for existing target indices.
        # Its length may be smaller than the requested index length, meaning
        # that some rows are still to be computed.

        # filtered_df = pd.DataFrame(index=target_locs).merge(
        #     right=loaded_table,
        #     how="inner",
        #     left_index=True,
        #     right_index=True,
        #     copy=False)

        filtered_df = pd.DataFrame(data=target_locs)
        filtered_df.set_index(0, drop=True, inplace=True)

        filtered_df = filtered_df.merge(
            right=loaded_table,
            how="inner",
            left_index=True,
            right_index=True,
            copy=False)

        assert len(filtered_df) <= len(target_locs)

        # This is the case where input samples were previously processed,
        # but new columns were defined/requested.
        fill = fill and (len(filtered_df) < len(target_indices) or filtered_df.isnull().any().any())

        if fill:
            # This method may raise ColumnFailedError if a column function crashes
            # or fails to fill their associated column(s).
            self.process_all_rows(
                # By passing target_df instead of loaded_table, there is less memory (and possibly network traffic)
                # footprint.
                loaded_df=loaded_table,
                filtered_df=filtered_df,
                target_indices=target_indices,
                target_locs=target_locs,
                target_columns=target_columns,
                overwrite=overwrite,
                parallel_row_processing=parallel_row_processing)

            if self.ignored_columns:
                loaded_table = loaded_table[[c for c in loaded_table.columns
                                             if c not in self.ignored_columns]]

            # Retrieve the requested data and verify consistency if requested
            filtered_df = loaded_table.loc[target_locs]
            if run_sanity_checks:
                self.assert_df_sanity(df=filtered_df)

            # Write to persistence if configured to do so - needed only if fill was True
            if self.csv_support_path:
                os.makedirs(os.path.dirname(os.path.abspath(self.csv_support_path)),
                            exist_ok=True)
                self.write_persistence(df=filtered_df, output_csv=self.csv_support_path)

        return filtered_df

    # def get_df_one_chunk(self, target_indices, target_columns=None,
    #                      fill=True, overwrite=False, parallel_row_processing=True):
    #     """Internal implementation of the :meth:`get_df` functionality,
    #     to be applied to a single chunk of indices. It is essentially a self-contained
    #     call to meth:`enb.atable.ATable.get_df` as described in its documentation, where
    #     data are stored in memory
    #     """
    #     # It is a no-op if ray is already initialzied
    #     ray_cluster.init_ray()
    #
    #     if options.verbose > 2:
    #         print("[I]nfo: Loading data and/or defaults...")
    #     table_df = self.load_saved_df()
    #     if options.verbose > 2:
    #         print("[I]nfo: ... loaded data and/or defaults!")
    #
    #     if not options.no_new_results:
    #         # Parallel read of current and/or default (with fields set to None) rows
    #         loaded_df_id = ray.put(table_df)
    #         index_ids = [ray.put(index) for index in target_indices]
    #         index_columns_id = ray.put(tuple(self.indices))
    #         all_columns_id = ray.put(self.indices_and_columns)
    #         loaded_rows_ids = [ray_get_row_or_default.remote(
    #             loaded_df_id, index_id, index_columns_id, all_columns_id)
    #             for index_id in index_ids]
    #         assert len(index_ids) == len(target_indices)
    #         assert len(loaded_rows_ids) == len(target_indices)
    #
    #         column_fun_tuples = [(column, properties.fun)
    #                              for column, properties in self.column_to_properties.items()
    #                              if column not in self.ignored_columns]
    #
    #         if target_columns is not None:
    #             len_before = len(column_fun_tuples)
    #             column_fun_tuples = [t for t in column_fun_tuples if t[0] in target_columns]
    #             assert column_fun_tuples, (target_columns, sorted(self.column_to_properties.keys()))
    #             if options.verbose:
    #                 print(
    #                     f"[O]nly for columns {', '.join(target_columns)} ({len_before}->{len(column_fun_tuples)} cols)")
    #
    #         if not parallel_row_processing:
    #             # Serial computation, e.g., to favor accurate time measurements
    #             returned_values = []
    #             for index, row in zip(target_indices, ray.get(loaded_rows_ids)):
    #                 try:
    #                     returned_values.append(self.process_row(
    #                         index=index, column_fun_tuples=column_fun_tuples,
    #                         row=row, overwrite=overwrite, fill=fill))
    #                 except ColumnFailedError as ex:
    #                     returned_values.append(ex)
    #         else:
    #             self_id = ray.put(self)
    #             options_id = ray.put(options)
    #             overwrite_id = ray.put(overwrite)
    #             fill_id = ray.put(fill)
    #             column_fun_tuples_id = ray.put(column_fun_tuples)
    #             processed_row_ids = [ray_process_row.remote(
    #                 atable=self_id, index=index_id, row=row_id,
    #                 column_fun_tuples=column_fun_tuples_id,
    #                 overwrite=overwrite_id, fill=fill_id,
    #                 options=options_id)
    #                 for index_id, row_id in zip(index_ids, loaded_rows_ids)]
    #             time_before = time.time()
    #             while True:
    #                 ids_ready, _ = ray.wait(processed_row_ids, num_returns=len(processed_row_ids), timeout=60.0)
    #                 if len(ids_ready) == len(processed_row_ids):
    #                     break
    #                 if any(isinstance(id_ready, Exception) for id_ready in ids_ready):
    #                     break
    #
    #                 if options.verbose:
    #                     if ids_ready:
    #                         time_per_id = (time.time() - time_before) / len(ids_ready)
    #                         eta_seconds = math.ceil((len(processed_row_ids) - len(ids_ready)) * time_per_id)
    #                         hours = eta_seconds // (60 * 60)
    #                         minutes = (eta_seconds % (60 * 60)) // 60
    #                         seconds = (eta_seconds % (60 * 60)) % 60
    #                         msg = f" Approximate completion time estimation: {hours}h {minutes}min {seconds}s"
    #                     else:
    #                         msg = ""
    #
    #                     print(f"[I]nfo: {len(ids_ready)} / {len(processed_row_ids)} ready @ "
    #                           f"{datetime.datetime.now()}.{msg}")
    #             returned_values = ray.get(processed_row_ids)
    #
    #         unpacked_target_indices = list(indices_to_internal_loc(unpack_index_value(target_index))
    #                                        for target_index in target_indices)
    #         index_exception_list = []
    #         for index, row in zip(unpacked_target_indices, returned_values):
    #             if isinstance(row, Exception):
    #                 if options.verbose:
    #                     print(f"[E]rror processing index {index}: {row}")
    #                 index_exception_list.append((index, row))
    #                 try:
    #                     table_df = table_df.drop(index)
    #                 except KeyError as ex:
    #                     pass
    #             else:
    #                 table_df.loc[index] = row
    #     else:
    #         index_exception_list = []
    #
    #     table_df = table_df[[c for c in table_df.columns if c not in self.ignored_columns]]
    #
    #     # All data (new or previously loaded) is saved to persistent storage
    #     # if (a) all data were successfully obtained or
    #     #    (b) the save_partial_results options is enabled
    #     if not options.no_new_results and self.csv_support_path and \
    #             (not index_exception_list or not options.discard_partial_results):
    #         os.makedirs(os.path.dirname(os.path.abspath(self.csv_support_path)), exist_ok=True)
    #         self.write_persistence(table_df)
    #
    #     # A DataFrame is NOT returned if any error is produced
    #     if index_exception_list:
    #         raise CorruptedTableError(
    #             atable=self, ex=index_exception_list[0][1],
    #             msg=f"{len(index_exception_list)} out of"
    #                 f" {len(target_indices)} errors happened. "
    #                 f"Run with --exit_on_error to obtain a full "
    #                 f"stack trace of the first error.")
    #
    #     # Sanity checks before returning the DataFrame with only the requested indices
    #     # Verify loaded indices are ok (sanity check)
    #     check_unique_indices(table_df)
    #     for ti in target_indices:
    #         internal_index = indices_to_internal_loc(ti)
    #         if internal_index not in table_df.index:
    #             if options.no_new_results:
    #                 raise ValueError(f"[E]rror: options.no_new_results = {options.no_new_results} "
    #                                  f"but {internal_index} not found in the table. Please run again "
    #                                  f"without --no_new_results nor any of its aliases.")
    #             # It should not get to this under regular circumstances...
    #             assert internal_index in table_df.index, (internal_index, table_df.loc[internal_index])
    #     target_internal_indices = [indices_to_internal_loc(ti) for ti in target_indices]
    #     table_df = table_df.loc[target_internal_indices, self.indices_and_columns]
    #     assert len(table_df) == len(target_indices), \
    #         "Unexpected table length / requested indices " \
    #         f"{(len(table_df), len(target_indices))}"
    #
    #     return table_df

    def process_all_rows(self,
                         loaded_df,
                         filtered_df,
                         target_indices,
                         target_columns,
                         overwrite,
                         parallel_row_processing,
                         target_locs=None):
        """This method is run when the table is known to have some missing values.
        These can be:

        - missing columns of existing rows, or
        - new rows to be added (i.e., target_locs contains at least one index not
          in loaded_table).

        :param loaded_df: the full loaded dataframe read from persistence (or created anew). This reference
          is the one where values are ultimately stored.
        :param filtered_df: a dataframe with identical column structure as loaded_table,
          with the subset of loaded_table's rows that match the target indices (i.e., inner join)
        :param target_indices: list of indices to be filled
        :param target_locs: if not None, it must be the resulting list
          of applying indices_to_internal_loc to target_indices. If None,
          it is computed in the aforementioned way. Either way,
          elements must be compatible with `loaded_table.loc`
          and be present in the same order as their corresponding
          target_indices.
        :param target_columns: list of columns that are to be computed. |enb| defaults
          to all columns in the table.
        :param overwrite: if True, cell values are computed even when storage
          data was present. In that case, the newly computed results replace the old ones.
        :param parallel_row_processing: if True, computation is run in parallel
          as much as possible. Setting it to False is needed if you want execution
          in a single or if you are debugging and prefer less complex stack traces.

        :return: a |DataFrame| instance with the same column structure as loaded_df
          (i.e., following this class' column defintion). Each row corresponds to
          one element in target_indices, maintaining the same order.

        :raises ColumnFailedError: if any of the column-setting functions crashes
          or fails to set a value to their assigned table cell.
        """
        # Get a list of all (column, fun) tuples, where fun is the function that sets column for a given row
        try:
            column_fun_tuples = [(c, self.column_to_properties[c].fun) for c in target_columns]
        except KeyError as ex:
            raise ValueError("Invoked with target columns not present in self.column_to_properties. "
                             f"target_columns={repr(target_columns)}, "
                             f"column_to_properties.keys()={repr(list(self.column_to_properties.keys()))}") from ex

        # Get the list of pandas Series instances (table rows) corresponding to target_indices.
        target_locs = target_locs if target_locs is None else [indices_to_internal_loc(v) for v in target_indices]
        if not parallel_row_processing:
            computed_series = [self.process_row(filtered_df=filtered_df,
                                                index=index, loc=loc,
                                                column_fun_tuples=column_fun_tuples,
                                                overwrite=overwrite,
                                                options=enb.config.options)
                               for index, loc in zip(target_indices, target_locs)]
        else:
            filtered_df_id = ray.put(filtered_df)
            column_fun_tuples_id = ray.put(column_fun_tuples)
            overwrite_id = ray.put(overwrite)
            options_id = ray.put(enb.config.options)
            self_id = ray.put(self)

            pending_ids = [ray_process_row.remote(
                atable_instance=self_id,
                filtered_df=filtered_df_id,
                index=ray.put(index), loc=ray.put(loc),
                column_fun_tuples=column_fun_tuples_id,
                overwrite=overwrite_id,
                options=options_id)
                for index, loc in zip(target_indices, target_locs)]
            computed_series = ray.get(pending_ids)

        # Update new rows
        for loc, series in ((loc, series) for loc, series in zip(target_locs, computed_series)):
            loaded_df.loc[loc] = series

        # The result is the concatenation of all loaded series
        return pd.concat(computed_series)

    def write_persistence(self, df, output_csv=None):
        """Dump a dataframe produced by this table into persistent storage.

        :param output_csv: if None, self.csv_support_path is used as the output path.
        """
        output_csv = output_csv if output_csv is not None else self.csv_support_path
        if options.verbose > 1:
            print(f"[D]umping CSV with {len(df)} entries into {output_csv}")
        df.to_csv(output_csv, index=False)

    def get_matlab_struct_str(self, target_indices):
        """Return a string containing MATLAB code that defines a list of structs
        (one per target index), with the fields being the columns defined
        for this table.
        """
        result_df = self.get_df(target_indices=target_indices)
        struct_str_lines = []
        struct_str_lines.append("image_list = [")
        for i in range(len(result_df)):
            row = result_df.iloc[i]
            row_str = "struct(" \
                      + f"'{self.index}',{repr(row[self.index])}, " \
                      + ", ".join(f"'{c}',{repr(row[c])}" for c in self.column_to_properties.keys()) \
                      + ");"
            struct_str_lines.append("".join(row_str.replace("True", "true").replace("False", "false")))
        struct_str_lines.append("]';")
        return "\n".join(struct_str_lines)

    def process_row(self, filtered_df, index, loc, column_fun_tuples, overwrite, options):
        """Process a single row of an ATable instance, returning a Series object corresponding to that row.

        :param filtered_df: |DataFrame| retrieved from persistent storage, with index compatible with loc.
          The loc argument itself needs not be present in filtered_df, but is used to avoid recomputing
          in case overwrite is not True and columns had been set.
        :param index: index value or values corresponding to the row to
          be processed.
        :param loc: location compatible with .loc of filtered_df (although it might not be present there),
          and that will be set into the full loaded_df also using its .loc accessor.
        :param column_fun_tuples: a list of (column, fun) tuples,
           where fun is to be invoked to fill column
        :param overwrite: if True, existing values are overwriten with
          newly computed data
        :param options: a copy of the enb.config.options of the orchestrating process.

        :return: a `pandas.Series` instance corresponding to this row, with a column named
          as given by self.private_index_column set to the `loc` argument passed to this function.
        """
        try:
            row = filtered_df.loc[loc]
        except KeyError:
            row = pd.Series({k: None for k in self.column_to_properties.keys()})

        called_functions = set()
        for column, fun in column_fun_tuples:
            if fun in called_functions:
                if row[column] is None:
                    raise ValueError(
                        f"[F]unction {fun} failed to fill column {column} with a not-None value. " +
                        ("Note that functions starting with column_ should either return a value or raise an exception"
                         if fun.__name__.startwith("column_") else ""))
                if options.verbose > 2:
                    print(f"[A]lready called function {fun.__name__} <{self.__class__.__name__}>")
                continue
            if options.columns and column not in options.columns:
                if options.verbose > 2:
                    print(f"[S]kipping non-selected column {column}")
                continue

            if overwrite or column not in row or row[column] is None:
                skip = False
            else:
                try:
                    skip = not math.isnan(float(row[column]))
                except (ValueError, TypeError):
                    skip = len(str(row[column])) > 0
            if skip:
                if options.verbose > 2:
                    print(f"[S]kipping existing '{column}' for index={index} <{self.__class__.__name__}>")
                continue

            if options.verbose > 1:
                print(f"[C]alculating {column} for {index} with <{self.__class__.__name__}>{{ {fun} }}")
            try:
                result = fun(self, index, row)
                called_functions.add(fun)
                if result is not None and options.verbose > 1:
                    print(f"[W]arning: result of {fun.__name__} ignored")
                if row[column] is None:
                    raise ValueError(f"Function {fun} failed to fill "
                                     f"the associated '{column}' column ({column}:{row[column]})")
            except Exception as ex:
                ex = ColumnFailedError(atable=self, index=index, column=column, ex=ex)
                if options.verbose:
                    print(f"[E]rror while obtaining {column} with {fun}: {repr(ex)}")
                if options.exit_on_error:
                    if options.verbose:
                        print(f"{self} ------------------------------------------------- [START error stack trace]")
                        traceback.print_exc()
                        print(f"{self} ------------------------------------------------- [END error stack trace]")
                        print(f"[E]rror: Exiting because options.exit_on_error = {options.exit_on_error}")
                    sys.exit(-1)
                else:
                    return ex

        for index_name, index_value in zip(self.indices, unpack_index_value(index)):
            row[index_name] = index_value

        return row

    def load_saved_df(self, run_sanity_checks=True):
        """Load the df stored in permanent support (if any) and return it.
        If not present, an empty dataset is returned instead.

        :param run_sanity_checks: if True, data are verified to detect corruption.
          This may increase computation time, but provides an extra layer
          of data reliability.

        :return: the loaded table_df, which may be empty
        :raise CorruptedTableError: if run_run_sanity_checks is True and
          a problem is detected.
        """
        try:
            if not self.csv_support_path:
                raise FileNotFoundError(
                    f"[W]arning: csv_support_path {self.csv_support_path} not set for {self}")

            # Read CSV from disk
            loaded_df = pd.read_csv(self.csv_support_path)
            if options.verbose > 2:
                print(f"[I]nfo: loaded dataframe from persistence with {len(loaded_df)} elements.")

            # Columns defined since the last invocation are initially set to None.
            # Furthermore, the row_complete column is set to False for all elements initially.
            # This value is only reverted to True for a row after get_df is called with
            # its index in the `target_indices` parameter.
            # This avoids cell-by-cell checking and is intended to speedup overall execution.
            for column in self.indices_and_columns:
                if column not in loaded_df.columns:
                    loaded_df[column] = None

            loaded_df[self.private_index_column] = loaded_df[self.index].apply(indices_to_internal_loc)
            loaded_df.set_index(self.private_index_column, drop=True, inplace=True)

            if run_sanity_checks:
                for index_name in self.indices:
                    if loaded_df[index_name].isnull().any():
                        raise CorruptedTableError(atable=self,
                                                  msg=f"Loaded table from {self.csv_support_path} with empty "
                                                      f"values for index {index_name} (at least)")

            # Some columns may have been deleted since the first rows
            # were added to persistence. Only defined columns are selected here,
            # so that (a) no bogus data is passed to the user (b) the columns
            # whose definition is removed can be removed from persistence
            # when the df is dumped into persistence.
            loaded_df = loaded_df[self.indices_and_columns]
            for column, properties in self.column_to_properties.items():
                if column in loaded_df.columns:
                    # Column existed - parse literals if needed
                    if properties.has_ast_values:
                        loaded_df[column] = loaded_df[column].apply(ast.literal_eval)
                else:
                    # Column did not exist: create with None values
                    loaded_df[column] = None

        except (FileNotFoundError, pd.errors.EmptyDataError) as ex:
            if self.csv_support_path is None:
                if options.verbose > 2:
                    print(f"[I]nfo: no csv persistence support.")
            elif options.verbose:
                print(f"[W]arning: ATable supporting file {self.csv_support_path} could not be loaded " +
                      (f"({ex.__class__.__name__}) " if options.verbose > 1 else '') +
                      f"- creating an empty one")
            loaded_df = pd.DataFrame(columns=self.indices_and_columns + [self.private_index_column])
            for c in self.indices_and_columns:
                loaded_df[c] = None
            loaded_df.set_index(self.private_index_column, drop=True, inplace=True)

        if run_sanity_checks:
            try:
                check_unique_indices(loaded_df)
            except CorruptedTableError as ex:
                print(f"[E]rror loading table from {self.csv_support_path}")
                raise ex

        return loaded_df

    @property
    def name(self):
        return f"{self.__class__.__name__}"

    def assert_df_sanity(self, df):
        """Perform a sanity check on the df, assuming it was
        produced by enb (e.g., via `get_df` or `load_saved_df`).

        :raises CorruptedTableError: if the sanity check is not passed.
        """
        for index_name in self.indices:
            if df[index_name].isnull().any():
                raise CorruptedTableError(
                    atable=self,
                    msg=f"Loaded table from {self.csv_support_path} with empty "
                        f"values for index {index_name} (at least)")

        check_unique_indices(df)


class SummaryTable(ATable):
    """Summary tables allow to define custom group rows of dataframes, e.g., produced by ATable subclasses,
    and to define new columns (measurements) for each of those groups.

    Column functions can be defined in the same way as for any ATable. In this case, the index elements
    passed to the column functions are the group labels returned by split_groups(). Column functions can then
    access the corresponding dataframe with self.label_to_df[label].

    Note that this behaviour is not unlike the groupby() method of pandas. The main differences are:

        - Grouping can be fully customized, instead of only allowing splitting by one or more column values

        - The newly defined columns can aggregate data in the group in any arbitrary way. This is of course
          true for pandas, but SummaryTable tries to gracefully integrate that process into enb, allowing
          automatic persistence, easy plotting, etc.

    SummaryTable can be particularly useful as an intermediate step between a complex table's (or enb.Experiment's)
    get_df and the analyze_df method of analyzers en :mod:`enb.aanalysis`.
    """

    def __init__(self, reference_df, reference_column_to_properties=None, copy_df=False,
                 csv_support_path=None):
        """
        Initialize a summary table. Group splitting is not invoked until needed by calling self.get_df().

        :param reference_df: reference pandas dataframe to be summarized
        :param reference_column_to_properties: if not None, it should be the column_to_properties attribute
          of the table that produced reference_df.
        :param copy_df: if not True, a pointer to the original reference_df is used. Otherwise, a copy is made.
          Note that reference_df is typically evaluated each time split_groups() is called.
        :param csv_support_path: if not None, a CSV file is used at that for persistence
        """
        super().__init__(csv_support_path=csv_support_path, index="group_label")
        self.reference_df = reference_df if copy_df is not True else pd.DataFrame.copy(reference_df)
        self.reference_column_to_properties = reference_column_to_properties
        self.copied_df = copy_df

    def split_groups(self, reference_df=None):
        """Split the reference dataframe into an iterable of (label, dataframe) tuples. By default, no splitting is
        performed and a single group with label "all" and the full df is returned.

        Subclasses can easily overwrite this behavior.
        Labels are arbitrary, but must be unique. Dataframes are also arbitrary, but it is
        recommended that at least all columns of the reference dataframe are maintained.

        :param reference_df: if not None, a reference dataframe to split. If None, self.reference_df is employed.
        :return: an iterable of (label, dataframe) tuples.
        """
        return [("all", reference_df if reference_df is not None else self.reference_df)]

    def get_df(self, reference_df=None):
        """
        Get the summary dataframe.

        :param reference_df: if not None, the dataframe to be used as reference for the summary. If None,
          the one provided at initialization is used.

        :return: the summary dataframe
        """
        if hasattr(self, "label_to_df"):
            raise RuntimeError("self.label_to_df should not be defined externally")
        self.label_to_df = collections.OrderedDict()
        try:
            for label, df in self.split_groups(reference_df=reference_df):
                if label in self.label_to_df:
                    raise ValueError(f"[E]rror: split_groups of {self} returned label {label} at least twice. "
                                     f"Group labels must be unique.")
                self.label_to_df[label] = df
            target_indices = list(self.label_to_df.keys())
            return super().get_df(target_indices=target_indices)
        finally:
            try:
                del self.label_to_df
            except AttributeError:
                pass

    def column_group_size(self, index, row):
        return len(self.label_to_df[index])


def string_or_float(cell_value):
    """Takes the input value from an |ATable| cell and returns either
    its float value or its string value. In the latter case, one level of surrounding
    ' or " is removed from the value before returning.
    :return: the string or float value given by cell_value
    """
    try:
        v = float(cell_value)
    except ValueError:
        v = str(cell_value)
        v = v.strip()
        if (v.startswith("'") and v.endswith("'")) \
                or (v.startswith('"') and v.endswith('"')):
            v = v[1:-1]
    return v


def get_nonscalar_value(cell_value):
    """Parse a |DataFrame|'s cell value in a column declared to contain non-scalar types, i.e., dict, list or tuple.
    Return an instance of one of those types.

    If cell_value is a string, ast is employed to parse it.
    If cell_Value is a dict, list or tuple, it is returned without modification.
    Otherwise, an error is raised.

    Note that |ATable| subclasses produce dataframes with the intended data types also for non-scalar types.
    This method is provided as a convenience tool for the case when raw CSV files produced by |enb| are
    read directly, and not through |ATable|'s persistence system.
    """
    if isinstance(cell_value, dict) or isinstance(cell_value, list) or isinstance(cell_value, tuple):
        return cell_value
    elif isinstance(cell_value, str):
        return ast.literal_eval(cell_value)
    else:
        raise ValueError(f"Cannot identify non-scalar value {repr(cell_value)}")


def check_unique_indices(df):
    """Verify that df has no duplicated indices, or raise a CorruptedTableError.
    """
    # Verify consistency
    duplicated_indices = df.index.duplicated()
    if duplicated_indices.any():
        s = f"Loaded table with the following DUPLICATED indices:\n\t: "
        if options.verbose:
            s += "\n\t:: ".join(str(' , '.join(values))
                                for values in df[duplicated_indices][df.example_indices].values)
            print(s)
        raise CorruptedTableError(atable=None)


def indices_to_internal_loc(values):
    """Given an index string or list of strings, return a single index string
    that uniquely identifies those strings and can be used as an internal index.

    This is used internally to set the actual |DataFrame|'s index value to a unique
    value that represents the row's index. Note that |DataFrame|'s subindexing is
    intentionally not used to maintain a simple, flat structure of tables without nesting.

    :return: a unique string for indexing given the input values
    """
    if isinstance(values, str):
        values = [values]
    values = [os.path.abspath(v) if os.path.exists(v) else v for v in values]
    return str(tuple(values))


def unpack_index_value(input):
    """Unpack an enb-created |DataFrame| index and return its elements.
    This can be useful to iterate homogeneously regardless of whether single or multiple indices are used.

    :return: If input is a string, it returns a list with that column name.
      If input is a list, it returns self.index.
    """
    if isinstance(input, str):
        return [input]
    else:
        return list(input)


@ray.remote
def ray_get_row_or_default(df, index, index_columns, all_columns):
    """Get an existing row of df, or a newly created row (not added to df)
    containing keys in index_columns set to the values given by index
    (which must match in number of items based on unpack_index_value()
    and all other defined columns set to None
    """
    if isinstance(index, str):
        index = [index]
    assert len(index) == len(index_columns), (index, index_columns)
    try:
        internal_index = str(tuple(index))
        row = df.loc[internal_index]
    except KeyError:
        initial_dict = {column: None for column in all_columns}
        initial_dict.update({index_name: index_value
                             for index_name, index_value
                             in zip(index_columns, index)})
        row = pd.Series(initial_dict)
    return row


@ray.remote
@config.propagates_options
def ray_process_row(atable_instance, filtered_df, index, loc, column_fun_tuples, overwrite, options):
    """Ray wrapper for :meth:`ATable.process_row`
    """
    return atable_instance.process_row(
        filtered_df=filtered_df,
        index=index,
        loc=loc,
        column_fun_tuples=column_fun_tuples,
        overwrite=overwrite,
        options=options)


def column_function(*column_property_list, **kwargs):
    """New columns can be added to |ATable| subclasses by decorating them with @enb.atable.column_function,
    e.g., with code similar to the following::

        class TableA(enb.atable.ATable):
        @enb.atable.column_function("uppercase", label="Uppercase version of the index")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()

    The `column_property_list` argument can be one of the following options:

    - one or more strings, which are interpreted as the new column(s)' name(s). For example::

        class TableC(enb.atable.ATable):
        @enb.atable.column_function("uppercase", "lowercase")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()
            row["lowercase"] = index.lower()


    - one or more |ColumnProperties| instances, one for each defined column.
    - a list of |ColumnProperties| instances, e.g., by invoking `@column_function([cp1,cp2])`
          where `cp1` and `cp2` are |ColumnProperties| instances.
          This option is deprecated and provided for backwards compatibility only.
          If `properties=[cp1,cp2]`, then `@column_function(l)` (deprecated) and `@column_function(*l)`
          should result in identical column definitions.


    Decorator to allow definition of table columns for
    still undefined classes. To do so, MetaTable keeps track of |column_function|-decorated methods
    while the class is being defined.
    Then, when the class is created, MetaTable adds the columns defined by the decorated functions.

    :param column_property_list: list of column property definitions, as described above.
    :return: the wrapper that actually decorates the function using the column_property_list and kwargs parameters.
    """
    kwargs = dict(kwargs)

    column_property_list = list(column_property_list)

    def inner_wrapper(decorated_method):
        try:
            cls_name = get_defining_class_name(decorated_method)
        except IndexError:
            raise SyntaxError(f"Detected a non-class method decorated with @enb.atable.column_function, "
                              f"which is not supported.")

        # Normalize arguments and add to the list of functions pending to be registered.
        normalized_list = ATable.normalize_column_function_arguments(
            column_property_list=column_property_list, fun=decorated_method, **kwargs)

        MetaTable.pendingdefs_classname_fun_columnpropertylist_kwargs.append(
            (cls_name, decorated_method, normalized_list, kwargs))

        return decorated_method

    return inner_wrapper


def redefines_column(f):
    """When an |ATable| subclass defines a method with the same name as any of the
    parent classes, and when that method defines a column, it must be decorated with this.

    Otherwise, a SyntaxError is raised. This is to prevent hard-to-find bugs where a parent
    class' definition of the method is used when filling a row's column, but calling that method
    on the child's instance runs the child's code.

    Functions decorated with this method acquire a _redefines_column attribute, that is then identified by
    :meth:`enb.atable.ATable.add_column_function`, i.e., the method responsible for creating columns.

    Note that _redefines_column attributes for non-column and non-overwritting methods are not employed
    by |enb| thereafter.

    :param f: rewriting function being decorated
    """
    f._redefines_column = True
    return f


def get_class_that_defined_method(meth):
    """From the great answer at
    https://stackoverflow.com/questions/3589311/get-defining-class-of-unbound-method-object-in-python-3/25959545#25959545
    """
    if inspect.ismethod(meth):
        for cls in inspect.getmro(meth.__self__.__class__):
            if cls.__dict__.get(meth.__name__) is meth:
                return cls
        meth = meth.__func__  # fallback to __qualname__ parsing
    if inspect.isfunction(meth):
        cls = getattr(inspect.getmodule(meth),
                      meth.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0])
        if isinstance(cls, type):
            return cls
    return getattr(meth, '__objclass__', None)


def get_all_input_files(ext=None, base_dataset_dir=None):
    """Get a list of all input files (recursively) contained in base_dataset_dir.

    :param ext: if not None, only files with names ending with ext will be
    :param base_dataset_dir: if not None, the dir where test files are searched
      for recursively. If None, options.base_dataset_dir is used instead.
    :return: the sorted list of canonical paths to the found input files.
    """
    # Set the input dataset dir
    base_dataset_dir = base_dataset_dir if base_dataset_dir is not None else options.base_dataset_dir
    if base_dataset_dir is None or not os.path.isdir(base_dataset_dir):
        raise ValueError(f"Cannot get input samples from {base_dataset_dir} (path not found or not a dir).")

    # Recursively get all files, filtering only those that match the extension, if provided.
    sorted_path_list = sorted(
        (get_canonical_path(p) for p in glob.glob(
            os.path.join(base_dataset_dir, "**", f"*{ext}" if ext else "*"),
            recursive=True)
         if os.path.isfile(p)),
        key=lambda p: get_canonical_path(p).lower())

    # If quick is selected, return at most as many paths as the quick parameter count
    return sorted_path_list if not options.quick else sorted_path_list[:options.quick]


def get_canonical_path(file_path):
    """
    :return: the canonical version of a path to be stored in the database, to make sure
      indexing is consistent across code using |ATable| and its subclasses.
    """
    return os.path.abspath(os.path.realpath(file_path))
