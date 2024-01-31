#!/usr/bin/env python3
"""
.. include:: ../tag_definition.rst

:mod:`enb.atable`: Automatic tables with implicit column definition
-------------------------------------------------------------------

|ATable| produces |DataFrame| instances
=======================================

This module defines the |ATable| class,
which is the base for all automatic tables in |enb|.

All |ATable| subclasses generate a |DataFrame| instance when their `get_df`
method is successfully called. These are powerful dynamic tables that can be
used directly, and/or passed to some of the tools in the |aanalysis| module
to easily produce figures and tables.

|ATable| provides automatic persistence
=======================================

The produced tables are automatically stored into persistent disk storage in
CSV format. This offers several key advantages:

- It avoids recalculating already known values. This speeds up subsequent
  calls to `get_df` for the same inputs.

- It allows sharing your raw results in a convenient way.

- It can help you reuse results from different projects.

This is best supported for numeric, string, and boolean types,
which are assumed by default.
You can also use non-scalar types, e.g., list, tuple and dict types,
by setting the `has_iterable_values`
and `has_dict_values` for |ColumnProperties|'s constructor (more on that later).

Finally, you can use any python object that can be pickled and unpickled. For
this to work for a given column, the `has_object_values` needs to be set to
True it the aforementioned constructor.

The only restriction is not to use None nor any other value detected as null
by pandas, because these are used to efficiently signal the absence of data.


Using existing |ATable| columns
===============================

|enb| implements several |ATable| subclasses that can be directly used in your code.
All |ATable| subclasses work as follows:

1. They accept an iterable (e.g., a list) of *indices* as an input. An
   *index* is often a string, e.g., a path to an element of your test dataset.
   Note that |enb| is capable of creating that list of indices if you point it
   to your dataset folder.

2. For each row, the set of defined data *columns*
   (e.g., the dependent/independent variables of an experiment)
   is computed and stored to disk along with the row's index.
   You can reuse existing ATable subclasses directly and/or create new subclasses.

Consider the following toy example::

        import enb

        class TableA(enb.atable.ATable):
            def column_index_length(self, index, row):
                return len(index)

Our `TableA` class accepts list-like values (e.g., strings) as indices,
and defines the `index_length` column as the number of elements (e.g.,
characters) in the index.

One can then use the `get_df` method to obtain a |DataFrame| instance as follows::

        table_a = TableA(index="my_index_name")
        example_indices = ["ab c" * i for i in range(10)]  # List of iterables
        df = table_a.get_df(target_indices=example_indices)
        print(df.head())

The previous code should produce the following output
(automatic timestamping columns now shown)::

                                  my_index_name index_length
        __atable_index
        ('',)                                              0
        ('ab c',)                          ab c            4
        ('ab cab c',)                  ab cab c            8
        ('ab cab cab c',)          ab cab cab c           12
        ('ab cab cab cab c',)  ab cab cab cab c           16


Note that the `__atable_index` is the dataframe's index, which is set and
used by ATable subclasses internally. This internal index is not included in
the persistence data (i.e., it is not part of the CSV tables output to disk).
Notwithstanding, the column values needed to build back this index are stored
in the CSV

New columns: defining and composing |ATable| subclasses
=======================================================

|enb| defines many columns in their core and plugin classes. If you need
more, you can easily create new |ATable| subclasses with custom columns,
as explained next.

You can use string, number and boolean types for scalar columns,
and dict-like and list-like (mappings and iterables) for non-scalar columns.

Basic column definition
+++++++++++++++++++++++

The fastest way of defining a column is to subclass |ATable| and to create
methods with names that start with `column_`. The value returned by these
methods is automatically stored in the appropriate cell of the dataframe.

An example of this approach is copied from `TableA` above::

        import enb

        class TableA(enb.atable.ATable):
            def column_index_length(self, index, row):
                return len(index)

which defines the `index_length` column in that table.

Advanced column definition
++++++++++++++++++++++++++

To further customize your new columns, you can use the |column_function| decorator.

1.  You can add column metainformation on how |aanalysis| plots the data by
    default, e.g., labels, ranges, logarithmic axes, etc. An example column with
    descriptive label can be defined as follows::

        @enb.atable.column_function("uppercase", label="Uppercase version of the index")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()

    See the |ColumnProperties| class for all available plotting cues.

2.  You can set two or more columns with a single function. To do so, you can
    pass a list of |ColumnProperties| instances to the |column_function|
    decorator. Each instance describes one column, which can be independently
    customized.

3.  You can define columns to contain non-scalar data. The following default
    types are supported: tuples, lists, dicts. Note that using non-scalar data is
    generally slower than using scalar types, but allows easy aggregation and
    combination of variables.

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
`print(TableB().get_df(target_indices=example_indices).head())`
to obtain simething similar to::

                                      file_path index_length         uppercase               first_and_last space_count constant_zero
    __atable_index
    ('',)                                              0                      {'first': '', 'last': ''}           0             0
    ('ab c',)                          ab c            4              AB C  {'first': 'a', 'last': 'c'}           1             0
    ('ab cab c',)                  ab cab c            8          AB CAB C  {'first': 'a', 'last': 'c'}           2             0
    ('ab cab cab c',)          ab cab cab c           12      AB CAB CAB C  {'first': 'a', 'last': 'c'}           3             0
    ('ab cab cab cab c',)  ab cab cab cab c           16  AB CAB CAB CAB C  {'first': 'a', 'last': 'c'}           4             0
"""  # pylint: disable=line-too-long
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/09/19"

import numbers
from builtins import hasattr
import ast
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
import pickle
import shutil
import traceback
import pandas as pd
import rich.progress

import enb.config
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
        super().__init__()
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

    def __init__(self, atable=None, index=None, column=None, msg=None, ex=None,
                 exception_list=None):
        """
        :param atable: atable instance that originated the problem
        :param column: column where the problem happened
        :param ex: main exception that lead to the problem, or None
        :param exception_list: a list of exceptions related to this one, e.g., all failing columns
        :param msg: message describing the problem, or None
        """
        # pylint: disable=too-many-arguments
        exception_list = exception_list if exception_list is not None else []
        super().__init__(atable=atable, msg=msg, ex=ex)
        self.index = index
        self.column = column
        self.exception_list = list(exception_list)

    def __str__(self):
        parts = []
        if self.exception_list:
            parts.append(f"{len(self.exception_list)} related exceptions")
        if self.index:
            parts.append(f"index={self.index}")
        if self.column:
            parts.append(f"column={self.column}")
        if self.msg:
            parts.append(
                f"msg='{repr(self.msg[:25])[1:-1]}{'...' if len(self.msg) > 25 else ''}'")

        failing_columns = set()
        for ex in itertools.chain((self.ex,), self.exception_list):
            try:
                if ex.column:
                    failing_columns.add(ex.column)
            except AttributeError:
                pass
        if failing_columns:
            parts.append(
                f"failing columns: {', '.join(repr(c) for c in failing_columns)}")

        return f"{self.__class__.__name__}({', '.join(parts)})" \
               f"{': ' + repr(self.ex) if self.ex else ''}"


class ColumnProperties:
    """All columns defined in an |ATable| subclass have a corresponding
    |ColumnProperties| instance, which provides metainformation about it. Its
    main uses are providing plotting cues and to allow non-scalar data (
    tuples, lists and dicts). Once an |ATable| subclass c is defined,
    `c.column_to_properties` contains a mapping from a column's name to its
    ColumnProperties instance. It is possible to change attributes of column
    properties instances, and to replace the ColumnProperties instances in
    `column_to_properties`. For instance, one may want to plot a column with
    its original cues first, and then create a second version with
    semi-logarithmic axes. Then it would suffice to use |aanalysis| tools
    with the |ATable| subclass default `column_to_properties` first,
    then modify one or more ColumnProperties instances, and finally apply the
    same tools again.
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(self, name, fun=None, label=None,
                 plot_min=None, plot_max=None,
                 semilog_x=False, semilog_y=False,
                 semilog_x_base=10, semilog_y_base=10,
                 hist_label=None, hist_min=None, hist_max=None,
                 hist_bin_width=None,
                 has_dict_values=False,
                 has_iterable_values=False,
                 has_object_values=False,
                 hist_label_dict=None,
                 **extra_attributes):
        """
        Column-function linking:

        :param name: unique name that identifies a column.
        :param fun: function to be invoked to fill a column value.
          If None, |enb| will set this for you
          when you define columns with `column_` or |column_function|.

        Type specification (mutually exclusive).

        :param has_dict_values: set to True if and only if the column cells
          contain value mappings (i.e., dicts),
          as opposed to scalar values. Both keys and values should be valid scalar values
          (numeric, string or boolean).
          It cannot be True if any other type is specified.
        :param has_iterable_values: set to True if and only if the column cells contain iterables,
          i.e., tuples or lists. It cannot be True if any other type is specified.
        :param has_object_values: set to True if and only if the column cells contain
          general python objects that can be pickled an unpickled.

        .. note:: The `has_ast_values` property of the ColumnProperties instance
          will return true if and only if iterable or dict values are used.

        Plot rendering hints:

        :param label: descriptive label of the column,
          intended to be displayed in plot (e.g., axes) labels
        :param plot_min: minimum value to be plotted for the column. For histograms,
          this refers to the range of key (X-axis) values.
        :param plot_max: minimum value to be plotted for the column. For histograms,
          this refers to the range of key (X-axis) values.
        :param semilog_x: True if a log scale should be used in the X axis.
        :param semilog_y: True if a log scale should be used in the Y axis.
        :param semilog_x_base: log base to use if semilog_x is true.
        :param semilog_y_base: log base to use if semilog_y is true.

        Parameters specific to histograms, only applicable when has_dict_values is True.

        :param hist_bin_width: histogram bin used when calculating distributions
        :param hist_label_dict: None, or a dictionary with x-value to label dict
        :param secondary_label: secondary label for the column, i.e., the Y axis
          of an histogram column.
        :param hist_min: if not None, the minimum value to be plotted in histograms.
          If None, the Analyzer instance decides the range (typically (0,1)).
        :param hist_max: if not None, the maximum value to be plotted in histograms.
          If None, the Analyzer instance decides the range (typically (0,1)).
        :param hist_label: if not None, the label to be shown globally in the Y axis.

        User-defined attributes:

        :param extra_attributes: any parameters passed are set as attributes of the created
          instance (with __setattr__). These attributes are not directly used by |enb|'s core,
          but can be safely used by client code.
        """
        # pylint: disable=too-many-arguments,too-many-locals
        self.name = name
        self.fun = fun
        self.label = label if label is not None else clean_column_name(name)
        self.plot_min = plot_min
        self.plot_max = plot_max
        self.semilog_x = semilog_x
        self.semilog_y = semilog_y
        self.semilog_x_base = semilog_x_base
        self.semilog_y_base = semilog_y_base
        self.hist_bin_width = hist_bin_width
        self.has_dict_values = has_dict_values or self.hist_bin_width is not None
        self.has_iterable_values = has_iterable_values
        self.has_object_values = has_object_values
        if sum(1 for flag in (self.has_iterable_values,
                              self.has_dict_values,
                              self.has_object_values) if flag is True) > 1:
            raise ValueError(
                "At most one of iterable, dict or object types can be specified.")
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
        args = ", ".join(
            f"{repr(k)}={repr(v)}" for k, v in self.__dict__.items() if
            v is not None)
        return f"{self.__class__.__name__}({args})"


class MetaTable(type):
    """Metaclass for |ATable| and all subclasses, which guarantees that the
    column_to_properties is a static OrderedDict instance different from
    other classes' column_to_properties. This way, |ATable| and all
    subclasses can access and update their dicts separately for each class,
    effectively allowing to split the definition of columns across multiple
    |ATable| instances.

    Note: Table classes should inherit from |ATable|, not |MetaTable|.
    You probably don't ever need to use this class directly.
    """
    # pylint: disable=too-many-locals,too-many-branches
    automatic_column_function_prefix = "column_"
    pendingdefs_classname_fun_columnpropertylist = []

    def __new__(cls, name, bases, dct):
        if MetaTable in bases:
            raise SyntaxError(
                "Please use ATable, not MetaTable, for subclassing.")

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
        MetaTable.set_column_mro(subclass)

        # Add pending decorated and column_* methods
        # (declared as columns before subclass existed),
        # in the order they were declared
        # (needed when there are data dependencies between columns).
        inheritedclassname_fun_columnproperties_kwargs = [
            t for t in cls.pendingdefs_classname_fun_columnpropertylist
            if t[0] != subclass.__name__]
        decorated_classname_fun_columnproperties_kwargs = [
            t for t in cls.pendingdefs_classname_fun_columnpropertylist
            if t[0] == subclass.__name__]
        for _, fun, column_properties \
                in inheritedclassname_fun_columnproperties_kwargs:
            if isinstance(column_properties, collections.abc.Iterable):
                # Passed a list of instances:
                # make sure they are all ColumnProperties
                for cp in column_properties:
                    if not isinstance(cp, ColumnProperties):
                        raise SyntaxError(
                            f"Found {repr(cp)} not a ColumnProperties instance.")
                    ATable.add_column_function(target_class=subclass,
                                               fun=fun,
                                               column_properties=cp)
            else:
                ATable.add_column_function(target_class=subclass,
                                           fun=fun,
                                           column_properties=column_properties)

        # Column functions are added to a list while the class is being defined.
        # After that, the subclass' column_to_properties attribute is updated according
        # to the column definitions.
        funname_to_class_fun_columnproperties = {
            t[1].__name__: t for t in
            decorated_classname_fun_columnproperties_kwargs}

        for fun in (f for f in subclass.__dict__.values()
                    if inspect.isfunction(f)):
            try:
                # Decorated function: the column properties are already present
                _, fun, cp_list = \
                    funname_to_class_fun_columnproperties[fun.__name__]
                for column_properties in cp_list:
                    if column_properties.label == column_properties.name:
                        column_properties.label = clean_column_name(
                            column_properties.name)
                    ATable.add_column_function(target_class=subclass,
                                               fun=fun,
                                               column_properties=column_properties)
                del funname_to_class_fun_columnproperties[fun.__name__]
            except KeyError as ex:
                # Non decorated function: decorate automatically if it starts with 'column_*'
                assert all(cp.fun is not fun
                           for cp in subclass.column_to_properties.values())
                if not fun.__name__.startswith(
                        MetaTable.automatic_column_function_prefix):
                    continue
                column_name = fun.__name__[
                              len(MetaTable.automatic_column_function_prefix):]
                if not column_name:
                    raise SyntaxError(
                        f"Function name '{fun.__name__}' "
                        f"not allowed in ATable subclasses") from ex
                wrapper = MetaTable.get_auto_column_wrapper(fun=fun)
                ATable.add_column_function(
                    target_class=subclass,
                    fun=wrapper,
                    column_properties=ColumnProperties(
                        name=column_name,
                        label=clean_column_name(column_name),
                        fun=wrapper))

        assert len(funname_to_class_fun_columnproperties) == 0, \
            ("Did not process all pending columndefinitions:",
             subclass, funname_to_class_fun_columnproperties)
        cls.pendingdefs_classname_fun_columnpropertylist.clear()

        return subclass

    @staticmethod
    def set_column_mro(subclass):
        """
        Redefine column properties that have been defined in the child class,
        making sure the expected method resolution order (MRO) is maintained.

        This method prevents the parent's method be invoked to fill in the |DataFrame|,
        following intuitive OOP definition.
        """
        for column, properties in subclass.column_to_properties.items():
            try:
                defining_class_name = get_class_that_defined_method(
                    properties.fun).__name__
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
                    if get_defining_class_name(ctp_fun) \
                            != get_defining_class_name(sc_fun):
                        enb.logger.debug(f"Redefining column {ctp_fun}. "
                                         f"It now becomes {sc_fun}")
                        properties = copy.copy(properties)
                        properties.fun = ATable.build_column_function_wrapper(
                            fun=sc_fun, column_properties=properties)
                        subclass.column_to_properties[column] = properties

    @staticmethod
    def get_auto_column_wrapper(fun):
        """Create a wrapper for a function with a signature compatible with
        column-setting functions, so that its returned value is assigned to
        the row's column.
        """

        @functools.wraps(fun)
        def wrapper(self, index, row):
            row[_column_name] = fun(self, index, row)

        try:
            # pylint: disable=protected-access
            wrapper._redefines_column = fun._redefines_column
        except AttributeError:
            pass

        return wrapper


def clean_column_name(column_name):
    """Return a cleaned version of the column name, more indicated for display.
    """
    column_name = str(column_name).replace("_", " ").strip()
    column_name = column_name[:1].upper() + column_name[1:]
    return column_name


class ATable(metaclass=MetaTable):
    """Automatic table with implicit column definition.

    ATable subclasses have the `get_df` method, which returns a |DataFrame|
    instance with the requested data. You can use (multiple) inheritance
    using one or more ATable subclasses to combine the columns of those
    subclasses into the newly defined one. You can then define methods with
    names that begin with `column_`, or using the
    `@enb.atable.column_function` decorator on them.

    See |atable| for more detailed help and examples.
    """
    #: Default input sample extension.
    #: If affects the result of `enb.atable.get_all_test_files`,
    dataset_files_extension = ""
    #: Name of the index used internally.
    private_index_column = "__atable_index"
    #: Column names in this list are not retrieved nor saved to persistence,
    #: even if they are defined.
    ignored_columns = []

    def __init__(self, index="index", csv_support_path=None,
                 column_to_properties=None,
                 progress_report_period=None):
        """
        :param index: string with column name or list of column names that will be
          used for indexing. Indices provided to self.get_df must be
          either one instance (when a single column name is given)
          or a list of as many instances as elements are contained in self.index.
          See `self.indices.
        :param csv_support_path: path to a file where this ATable contents
          are to be stored and retrieved. If None, persistence is disabled.
        :param column_to_properties: if not None, it is a mapping from strings to callables
          that defines the columns of the table and how to obtain the cell values
        :param progress_report_period: if not None, it must be a positive number of seconds
          that are waited between progress report messages (if applicable).
        """
        # Set up the index, column properties and persistence CSV file for this table
        self.index = index
        self.csv_support_path = csv_support_path
        if column_to_properties is not None:
            #: The `column_properties` attribute keeps track of what columns
            #: have been defined, and the methods that need to be called to computed them.
            #: The keys of this attribute can be used to determine the columns defined in a given
            #: class or instance. The values are |ColumnProperties| instances, which can be set
            #: manually after definition and before calling |Analyzer| subclasses' `get_df`.
            self.column_to_properties = collections.OrderedDict(
                column_to_properties)

        # Add the row_created and row_updated columns. The latter is updated by enb
        # everytime a row is modified.
        self.add_column_function(self.__class__,
                                 fun=lambda self, index,
                                            row: datetime.datetime.now().isoformat(),
                                 column_properties=ColumnProperties(
                                     "row_created"))
        self.add_column_function(self.__class__,
                                 fun=lambda self, index,
                                            row: datetime.datetime.now().isoformat(),
                                 column_properties=ColumnProperties(
                                     "row_updated"))

        # Initialize the periodicity with which progress is reported when -v is specified
        # in the CLI.
        progress_report_period = progress_report_period if progress_report_period is not None \
            else enb.config.options.progress_report_period
        if progress_report_period < 0:
            raise ValueError(
                f"Invalid progress_report_period {progress_report_period}")
        self.progress_report_period = progress_report_period

        # ATable instances are intended to be instantiated and their get_df method called.
        # This variable helps send a user-friendly message if an ATable subclass is instantiated
        # but that method is not called.
        self._was_get_df_called = False

    # Methods related to defining columns and retrieving them afterwards

    @classmethod
    def column_function(cls, *column_properties, **kwargs):
        """Decorator for functions that produce values for column_name when
        given the current index and current column values.

        Decorated functions are expected to have signature (atable, index,
        row), where atable is an ATable instance, index is a tuple of index
        values (corresponding to self.index), and row is a dict-like instance
        to be filled in by f.

        Columns are sorted by the order in which they are defined, i.e., when
        a function is decorated for the corresponding column.
        Redefinitions are not allowed.

        A variable _column is added to the decorated function's scope, e.g.,
        to assign values to the intended column of the row object.

        :param column_properties: a list of one or more of the following types of elements:

          * a string with the column's name to be used in the table.
            A new |ColumnProperties| instance
            is then created, passing `**kwargs` to the initializer.

          * a ColumnProperties instance. In this case `**kwargs` is ignored.
        """

        def decorator_wrapper(fun):
            return ATable.add_column_function(
                *column_properties, target_class=cls, fun=fun, **kwargs)

        return decorator_wrapper

    @classmethod
    def redefines_column(cls, fun):
        """Decorator to be applied on overwriting methods that are meant to fill
        the same columns as the base class' homonym method.
        """
        # pylint: disable=protected-access
        fun._redefines_column = True
        return fun

    @staticmethod
    def add_column_function(target_class, fun, column_properties):
        """Main entry point for column definition in |ATable| subclasses.

        Methods decorated with |column_function|, or with a name beginning
        with `column_` are automatically "registered" using this function. It
        can be invoked directly to add columns manually, although it is not
        recommended in most scenarios.

        :param target_class: the |ATable| subclass to which a new column
          is to be added.
        :param column_properties: a |ColumnProperties| instance describing
          the column to be created. This list may also contain strings,
          which are interpreted as column names, creating the corresponding
          columns.
        :param fun: column-setting function. It must have a signature
          compatible with a call `(self, index, row)`, where `index` is the
          row's index and `row` is a dict-like object where the new column is
          to be stored. Previously set columns can also be read from `row`.
          When a column-setting method is decorated, fun is automatically set
          so that the decorated method is called, but it is not guaranteed that
          fun is the decorated method.
        """
        if isinstance(target_class, type) \
                and not issubclass(target_class, ATable) \
                and not isinstance(target_class, ATable):
            raise SyntaxError(
                "Column definition is only supported for classes that inherit from ATable, "
                f"but {target_class} was found.")
        if not isinstance(column_properties, ColumnProperties):
            raise SyntaxError(
                "Only subclasses of ColumnProperties are allowed "
                "for the column_properties argument "
                f"(found type {type(column_properties)} -- {column_properties})")

        # Effectively register the column function into the class
        fun_wrapper = target_class.build_column_function_wrapper(
            fun=fun, column_properties=column_properties)
        column_properties.fun = fun_wrapper
        target_class.column_to_properties[
            column_properties.name] = column_properties

        return fun_wrapper

    @staticmethod
    def normalize_column_function_arguments(column_property_list, fun,
                                            **kwargs):
        """Helper method to verify and normalize the `column_property_list`
        varargs passed to add_column_function.
        Each element of that list is passed as the `column_properties`
        argument to this function.

        - If the element is a string, it is interpreted as a column name,
          and a new ColumnProperties object is is created with that name and
          the `fun` argument to this function. The kwargs argument is passed to
          that initializer.

        - If the element is a |ColumnProperties| instance,
          it is returned without modification.
          The kwargs argument is ignored in this case.

        - Otherwise, a SyntaxError is raised.

        :param column_property_list: one of the elements of the
          `*column_property_list` parameter to add_column_function.
        :param fun:
          the function being decorated.
        :return: a nonempty list of valid ColumnProperties instances
        """
        normalized_cp_list = []
        for column_properties in column_property_list:
            if isinstance(column_properties, str):
                normalized_cp_list.append(
                    ColumnProperties(name=column_properties, fun=fun, **kwargs))
            elif isinstance(column_properties, ColumnProperties):
                normalized_cp_list.append(column_properties)
            elif isinstance(column_properties, collections.abc.Iterable):
                normalized_cp_list.extend(
                    ATable.normalize_column_function_arguments(
                        column_property_list=column_properties, fun=fun))
            else:
                raise SyntaxError(
                    "Invalid arguments passed to add_column_function: "
                    f"{column_properties} "
                    f"(type {type(column_properties)}), {fun}, {kwargs} ")

        return normalized_cp_list

    @classmethod
    def build_column_function_wrapper(cls, fun, column_properties):
        """Build the wrapper function applied to all column-setting functions given
        a column properties instance.

        |ATable|'s implementation of `build_column_function_wrapper` adds two variables
        to the column-setting function's scope: `_column_name` and `_column_properties`,
        in addition to verifying the column-setting function's signature.

        Notwithstanding, this behavior can be altered in |ATable| subclasses,
        affecting only the wrappers for that class' column-setting functions.

        :param fun: function to be called by the wrapper.
        :param column_properties: |ColumnProperties| instance with properties associated
          to the column.
        :return: a function that wraps fun adding `_column_name`
          and `_column_properties` to its scope.
        """
        # Match fun's signature with the expected one (self, index, row).
        # Variable names are not checked.
        fun_spec = inspect.getfullargspec(fun)
        if len(fun_spec.args) != 3 and fun_spec.varargs is None and fun_spec.varkw is None:
            raise SyntaxError(
                f"Trying to add a column-setting method {fun} to {cls.__name__}, "
                f"but an invalid signature was found. "
                f"Column-setting methods should have a (self, index, row) signature. "
                f"Instead, the following signature was provided: {fun_spec}.")

        # Create a wrapper that adds some temporary globals
        @functools.wraps(fun)
        def column_function_wrapper(self, index, row):
            # The _column_name and _column_properties globals are
            # defined to help define more concise column functions.
            if isinstance(fun, functools.partial):
                global_variables = fun.func.__globals__
            else:
                global_variables = fun.__globals__
            old_globals = dict(global_variables)
            global_variables.update(_column_name=column_properties.name,
                                    _column_properties=column_properties)

            # The current working dir is updated for remote processes
            # in the head or the remote nodes
            try:
                enb.parallel_ray.chdir_project_root()
                returned_value = fun(self, index, row)
                if returned_value is not None:
                    row[column_properties.name] = returned_value
            finally:
                global_variables.clear()
                global_variables.update(old_globals)

        try:
            # pylint: disable=protected-access
            column_function_wrapper._redefines_column = fun._redefines_column
        except AttributeError:
            pass

        return column_function_wrapper

    @property
    def indices(self):
        """If `self.index` is a string, it returns a list with that column
        name. If self.index is a list, it returns `self.index`. Useful to
        iterate homogeneously regardless of whether single or multiple
        indices are used.
        """
        return unpack_index_value(self.index)

    @property
    def indices_and_columns(self):
        """
        :return: a list of all defined columns, i.e., those for which a function has been defined.
        """
        return self.indices + list(
            k for k in self.column_to_properties.keys()
            if k not in itertools.chain(self.indices, self.ignored_columns))

    # Methods to generate a DataFrame instance with the requested data
    def get_df(self, target_indices=None, target_columns=None,
               fill=None, overwrite=None, chunk_size=None,
               progress_tracker=None):
        """Core method for all |ATable| subclasses to obtain the table's content.
        The following principles guide the way `get_df` works:

        - This method returns a |DataFrame| containing one row per element in
          `target_indices`, and as many columns as there are defined in
          self.column_to_properties. If `target_indices` is None, all files in
          enb.config.options.base_dataset_dir are used (after filtering by
          self.dataset_files_extension) by default.

        - Any persistence data already present is loaded, and only new
          indices or columns are added. This way, each column-setting function
          needs to be called only once per index for any given |ATable| subclass.

        - Results are returned only for `target_indices`, even if you
          previously computed other rows. Thus, only not-already-present
          indices and new columns require actual computation. Any new result
          produced by this call is appended to the already existing persistence
          data.

        - Rows computed in a previous call to this `get_df` are not deleted
          from persistent data storage, even if `target_indices` contains fewer
          or different indices than in previous calls.

        - Beware that if you remove a column definition from this |ATable|
          subclass and run `get_df`, that column will be removed from
          persistent storage. If you add a new column, that value will be
          computed for all rows in `target_indices`,

        - You can safely select new and/or different `target_indices`. New data
          are stored, and existent rows are not removed. If you add new column
          definitions, those are computed for `target_indices` only. If there
          are other previously existing rows, they are flagged as incomplete,
          and those new columns will be computed only when those rows' indices
          are included in `target_indices`.

        Recall that table cell values are restricted to be
        numeric, string, boolean or non-scalar, i.e., list, tuple or dict.

        :param target_indices: list of indices that are to be contained in
          the table, or None to infer automatically from the dataset.
        :param target_columns: if not None, it must be a list of column names
          (defined for this class) that are to be obtained for the specified
          indices. If None, all columns are used.
        :param fill: If True or False, it determines whether values are
          computed for the selected indices. If None, values are only computed
          if enb.config.options.no_new_results is False.
        :param overwrite: values selected for filling are computed even if
          they are present in permanent storage. Otherwise, existing values are
          skipped from the computation.
        :param chunk_size: If None, its value is assigned from
          options.chunk_size. After this, if not None, the list of target
          indices is split in chunks of size at most chunk_size elements (each
          one corresponding to one row in the table). Results are made
          persistent every time one of these chunks is completed.
          Setting chunk_size to -1 is functionally identical to setting it
          to None (or to the number of target indices), but it does not
          display "Starting chunk 1/1..." (useful if the chunk partitioning
          is performed outside, i.e., by an Experiment class).
        :param progress_tracker: if not None, the enb.progress.ProgressTracker
          instance being used to keep track of an ATable instance at an upper level.

        :return: a DataFrame instance containing the requested data
        :raises: CorruptedTableError, ColumnFailedError, when an error is
          encountered processing the data.
        """
        # Avoid sending a false warning of not having invoked self.get_df
        self._was_get_df_called = True

        # pylint: disable=too-many-arguments
        # Parallelization with ray is only used if it is enabled at this point,
        # i.e., if ray is installed, the current platform is supported, and
        # a cluster configuration file was found. Otherwise, the multiprocessing
        # library is employed. See the parallel_decorator and parallel_ray
        # modules for more information.
        enb.parallel.init()

        target_columns = target_columns if target_columns is not None else list(
            self.column_to_properties.keys())

        overwrite = overwrite if overwrite is not None else options.force
        fill = fill if fill is not None else not options.no_new_results

        # Use the provided target indices or discover automatically from the dataset folder
        target_indices = list(target_indices) if target_indices is not None \
            else self.get_all_input_indices(ext=self.dataset_files_extension)

        if not target_indices:
            raise ValueError(
                f"No target indices could be found at {repr(options.base_dataset_dir)}. "
                f"Please double check that:\n"
                f"(a) the base_dataset_dir={repr(options.base_dataset_dir)} "
                f"is correctly set, and it contains the expected samples;\n"
                f"(b) you are passing the right value to the "
                f"`target_indices` argument of get_df() if not using the default;\n"
                f"(c) the experiment class you are using has the intended "
                f"`dataset_files_extension` attribute set. It is currently "
                f"{repr(self.dataset_files_extension)}. If empty, all files under "
                f"the dataset folder should be obtained by default.")

        # Split the work into one or more chunks, which are completed before
        # moving on to the next one.
        negative_chunk_size = chunk_size is not None and chunk_size < 0
        chunk_size = None if chunk_size is not None and chunk_size < 0 else chunk_size
        chunk_size = chunk_size if chunk_size is not None \
            else options.chunk_size
        chunk_size = chunk_size if chunk_size is not None \
            else len(target_indices)
        if chunk_size <= 0:
            raise SyntaxError(
                f"Invalid chunk_size {chunk_size}. "
                f"Re-run with -h for syntax help.")
        chunk_list = [target_indices[i:i + chunk_size]
                      for i in range(0, len(target_indices), chunk_size)]
        assert len(chunk_list) > 0

        # Split in chunks and add/update the persistent storage
        df = None
        if fill or overwrite:
            if progress_tracker is None and enb.progress.is_progress_enabled():
                with enb.progress.ProgressTracker(self, len(target_indices), chunk_size) as tracker:
                    for i, chunk in enumerate(chunk_list):
                        df = self.get_df_one_chunk(
                            target_indices=chunk, target_columns=target_columns,
                            fill_needed=True,
                            overwrite=overwrite,
                            run_sanity_checks=False,
                            progress_tracker=tracker)
                        tracker.complete_chunk()
            else:
                for i, chunk in enumerate(chunk_list):
                    if not negative_chunk_size:
                        enb.logger.debug(
                            f"[{self.__class__.__name__}:get_df] Starting chunk "
                            f"{i + 1}/{len(chunk_list)} "
                            f"(chunk_size={chunk_size}, "
                            f"{100 * i * chunk_size / len(target_indices):.1f}"
                            f"-{min(100, 100 * ((i + 1) * chunk_size) / len(target_indices)):.1f}% "
                            f"of {len(target_indices)} total rows) "
                            f"@ {datetime.datetime.now()}")

                    df = self.get_df_one_chunk(
                        target_indices=chunk, target_columns=target_columns,
                        fill_needed=True,
                        overwrite=overwrite,
                        run_sanity_checks=False,
                        progress_tracker=progress_tracker if enb.progress.is_progress_enabled() else False)

        # Get the target df again
        if len(chunk_list) > 1 or df is None:
            df = self.get_df_one_chunk(
                target_indices=target_indices,
                target_columns=target_columns,
                fill_needed=fill or overwrite,
                overwrite=False,
                run_sanity_checks=enb.config.options.force_sanity_checks,
                progress_tracker=False)

        if fill or overwrite:
            assert len(df) == len(target_indices), (
                len(df), len(target_indices), target_indices, df)
            enb.logger.debug(
                f"[{self.__class__.__name__}:get_df] "
                f"Retrieved filled dataframe with {len(df)} rows.")
        else:
            enb.logger.debug(
                f"[{self.__class__.__name__}:get_df] "
                f"Retrieved unfilled dataframe with {len(df)} rows.")

        return df

    def get_all_input_indices(self, ext=None, base_dataset_dir=None):
        """Get a list of all input indices (recursively) contained in base_dataset_dir.
        By default, the global function enb.atable.get_all_input_files is called.
        """
        # pylint: disable=no-self-use
        return get_all_input_files(ext=ext, base_dataset_dir=base_dataset_dir)

    def get_df_one_chunk(self, target_indices, target_columns, fill_needed,
                         overwrite, run_sanity_checks,
                         progress_tracker=None):
        """Internal implementation of the :meth:`get_df` functionality,
        to be applied to a single chunk of indices. It is essentially a
        self-contained call to meth:`enb.atable.ATable.get_df` as described
        in its documentation, where data are stored in memory until all
        computations are done, and then the persistent storage is updated if
        needed.

        :param target_columns: list of indices for this chunk
        :param target_columns: list of column names to be filled in this call
        :param fill_needed: if False, results are not computed (they default to None).
          Instead, only data in persistent storage is used.
        :param overwrite: values selected for filling are computed even if they are present
          in permanent storage. Otherwise, existing values are skipped from the computation.
        :param run_sanity_checks: if True, sanity checks are performed on the data
        :param progress_tracker: the ProgressTracker instance being used to track progress
          of this call, or None if None is being used, or False if no progress tracker is
          to be employed.

        :return: a DataFrame instance containing the requested data
        :raises ColumnFailedError: an error was encountered while computing the data.
        """
        # pylint: disable=too-many-arguments
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
        target_df = pd.DataFrame(target_locs,
                                 columns=[self.private_index_column])
        target_df.set_index(self.private_index_column, drop=True, inplace=True)
        target_df = target_df.merge(
            right=loaded_table,
            how="inner",
            left_index=True,
            right_index=True,
            copy=False)

        assert len(target_df) <= len(target_locs), f"Error: Duplicated indices? " \
                                                   f"|target_df| = {len(target_df)}, |target_locs| = {len(target_locs)}"

        # This is the case where input samples were previously processed,
        # but new columns were defined/requested.
        fill_needed = (fill_needed
                       and (len(target_df) < len(target_indices)
                            or target_df[target_columns].isnull().any().any()))

        if fill_needed or overwrite:
            # Needed locs are those of the rows that require an update or do not exist in the loaded df
            if overwrite:
                needed_indices = target_indices
            else:
                needed_indices = [
                    index
                    for index in target_df[target_columns].isnull().any(axis=1).index
                    if index in target_indices]
                needed_indices.extend(
                    index
                    for index in target_indices
                    if indices_to_internal_loc(index) not in target_df.index)

            # Process only columns that need an update and rows that did not exist.
            computed_df = self.compute_target_rows(
                # By passing target_df instead of loaded_table,
                # there is less memory (and possibly network traffic) footprint.
                loaded_df=loaded_table,
                target_df=target_df,
                target_indices=needed_indices,
                target_columns=target_columns,
                overwrite=overwrite,
                progress_tracker=progress_tracker)

            # Insert or update rows
            target_df = pd.concat([target_df, computed_df])
            target_df = target_df[~target_df.index.duplicated(keep="last")]
            assert len(target_df) == len(target_indices), (len(target_df), len(target_indices))

            # Not all columns might have been requested
            if self.ignored_columns:
                target_df = target_df[[c for c in loaded_table.columns
                                       if c not in self.ignored_columns]]

            # The new df is available. Store data into persistence if one is configured
            if self.csv_support_path:
                loaded_table = pd.concat([loaded_table, target_df])
                loaded_table = loaded_table[~loaded_table.index.duplicated(keep="last")]
                os.makedirs(os.path.dirname(os.path.abspath(self.csv_support_path)), exist_ok=True)
                self.write_persistence(df=loaded_table, output_csv=self.csv_support_path)

        if progress_tracker:
            progress_tracker.update_chunk_completed_rows(len(target_indices))

        return target_df

    def load_saved_df(self, csv_support_path=None, run_sanity_checks=True):
        """Load the df stored in permanent support (if any) and return it.
        If not present, an empty dataset is returned instead.

        :param run_sanity_checks: if True, data are verified to detect corruption.
          This may increase computation time, but provides an extra layer
          of data reliability.

        :return: the loaded table_df, which may be empty
        :raise CorruptedTableError: if run_run_sanity_checks is True and
          a problem is detected.
        """
        # pylint: disable=too-many-branches
        csv_support_path = csv_support_path \
            if csv_support_path is not None else self.csv_support_path

        try:
            if not csv_support_path:
                raise FileNotFoundError(
                    f"[W]arning: csv_support_path {csv_support_path} not set for {self}")

            # Read CSV from disk
            with enb.logger.debug_context(
                    f"Loading dataframe from persistence at {csv_support_path}",
                    sep="... "):
                loaded_df = pd.read_csv(csv_support_path)
                enb.logger.debug(f"Loaded df with {len(loaded_df)} rows")
            loaded_columns = list(loaded_df.columns)

            # Columns defined since the last invocation are initially set to
            # None for all previously
            # existing data.
            # pylint: disable=no-member
            for column in (c for c in self.indices_and_columns
                           if c not in loaded_df.columns):
                loaded_df[column] = None

            if run_sanity_checks:
                with enb.logger.debug_context(
                        "Verifying that no null data is stored in the CSV..."):
                    for index_name in self.indices:
                        if loaded_df[index_name].isnull().any():
                            raise CorruptedTableError(
                                atable=self,
                                msg=f"Loaded table from {csv_support_path} with empty "
                                    f"values for index {index_name} (at least)")

            # Some columns may have been deleted since the first rows
            # were added to persistence. Only defined columns are selected here,
            # so that (a) no bogus data is passed to the user (b) the columns
            # whose definition is removed can be removed from persistence
            # when the df is dumped into persistence.
            with enb.logger.debug_context("Loading serialized objects"):
                loaded_df = loaded_df[
                    self.indices_and_columns + [self.private_index_column]]
                for column, properties in self.column_to_properties.items():
                    if column in loaded_columns:
                        # Column existed - parse literals if needed
                        if properties.has_ast_values:
                            loaded_df[column] = loaded_df[column].apply(
                                ast.literal_eval)
                        elif properties.has_object_values:
                            loaded_df[column] = loaded_df[column].apply(
                                lambda v: pickle.loads(ast.literal_eval(v)))
                    else:
                        # Column did not exist: create with None values
                        loaded_df[column] = None

        except (FileNotFoundError, pd.errors.EmptyDataError):
            with enb.logger.debug_context(
                    f"No CSV persistence found for {self.__class__.__name__} "
                    f"at {csv_support_path}. Creating an empty one"):
                loaded_df = pd.DataFrame(
                    columns=self.indices_and_columns + [
                        self.private_index_column])
                for column in self.indices_and_columns:
                    loaded_df[column] = None

        loaded_df.set_index(self.private_index_column, drop=True, inplace=True)

        if run_sanity_checks:
            with enb.logger.debug_context("Verifying index unity"):
                try:
                    check_unique_indices(loaded_df)
                except CorruptedTableError as ex:
                    raise CorruptedTableError(
                        f"Error loading table from {csv_support_path}") from ex

        return loaded_df

    def compute_target_rows(self,
                            loaded_df,
                            target_df,
                            target_indices,
                            target_columns,
                            overwrite,
                            progress_tracker=None):
        """Generate and return a |DataFrame| with as many rows as given by
        `target_indices`, with the columns given in `target_columns`, using this table's column-setting functions.

        This method is run when there are one or more known missing values in the
        requested df, e.g., there are:

        - missing columns of existing rows, and/or
        - new rows to be added (i.e., `target_locs` contains at least one index not
          in `loaded_df`).

        The calling function must choose target_indices to be the list of needed indices (not locs).

        Note that this method does not modify `loaded_df`.

        :param loaded_df: the full loaded dataframe read from persistence (or
          created anew). It is used to avoid recomputation of existing columns,
          but it is not modified by this method.

        :param target_df: a dataframe with identical column structure as
          loaded_table, with the subset of loaded_table's rows that match the
          target indices (i.e., inner join)

        :param target_indices: list of indices to be filled

        :param target_columns: list of columns that are to be computed. |enb|
          defaults to calling this function with all columns in the table.

        :param overwrite: if True, all cell values are computed even when storage
          data was present. In that case, the newly computed results replace the old ones.

        :param progress_tracker: if not None, an enb.progress.ProgressTracker instance
          currently being used to keep track of this ATable's get_df call.

        :return: a |DataFrame| instance with the same column structure as loaded_df
          (i.e., following this class' column defintion). Each row corresponds to
          one element in target_indices, maintaining the same order.

        :raises ColumnFailedError: if any of the column-setting functions crashes
          or fails to set a value to their assigned table cell.
        """
        # pylint: disable=too-many-arguments
        # Get a list of all (column, fun) tuples,
        # where fun is the function that sets column for a given row
        try:
            column_fun_tuples = [(c, self.column_to_properties[c].fun) for c in
                                 target_columns]
            missing_fun_tuples = [fun_tuple for fun_tuple in column_fun_tuples
                                  if fun_tuple[1] is None]
            if missing_fun_tuples:
                enb.logger.debug(f"Wrong target_columns for {self}. "
                                 "It has None associated functions for the following columns:")
                enb.logger.debug("\n\t-".join(
                    cft[0] for cft in column_fun_tuples if cft[1] is None))
                enb.logger.debug("These will be ignored")
                column_fun_tuples = [cft for cft in column_fun_tuples if
                                     cft[1] is not None]
        except KeyError as ex:
            raise ValueError(
                "Invoked with target columns not present in self.column_to_properties. "
                f"target_columns={repr(target_columns)}, "
                f"column_to_properties.keys()="
                f"{repr(list(self.column_to_properties.keys()))}") from ex

        enb.logger.debug(
            f"Filling {len(target_indices)} rows, {len(target_columns)} columns...")

        # Start computation of new and updated rows in parallel_decorator
        pending_ids = [parallel_compute_one_row.start(
            atable_instance=self,
            filtered_df=target_df,
            index=index, loc=indices_to_internal_loc(index),
            column_fun_tuples=column_fun_tuples,
            overwrite=overwrite)
            for index in target_indices]

        # Iterating a progressive getter continues until all rows are obtained
        with enb.logger.debug_context(
                f"Parallel computation of {len(pending_ids)} "
                f"rows using {self.__class__.__name__} [CPU limit: {enb.config.options.cpu_limit}]",
                sep="...\n"):
            progressive_getter = enb.parallel.ProgressiveGetter(
                id_list=pending_ids,
                iteration_period=self.progress_report_period,
                alive_bar=None)
            for _ in progressive_getter:
                if not progress_tracker:
                    enb.logger.debug(progressive_getter.report())
                else:
                    progress_tracker.update_chunk_completed_rows(len(progressive_getter.completed_ids))
            computed_series = enb.parallel.get(pending_ids)

        # Verify that everything went well
        found_exceptions = [e for e in computed_series if
                            isinstance(e, Exception)]
        if found_exceptions:
            raise ColumnFailedError(
                f"Error setting {len(found_exceptions)}/{len(target_indices)} indices"
                f" with {self.__class__.__name__}",
                exception_list=found_exceptions)

        # Return the dataframe with the requested rows and columns, without attempting to updated
        # the loaded dataframe (that is done by methods calling this one)
        with enb.logger.debug_context(msg="Merging requested rows"):
            target_df = pd.DataFrame(
                computed_series,
                columns=[self.private_index_column] + list(loaded_df.columns))
            target_df.set_index(self.private_index_column, inplace=True)

        return target_df

    def compute_one_row(self, filtered_df, index, loc, column_fun_tuples,
                        overwrite):
        """Process a single row of an ATable instance, returning a Series
        object corresponding to that row. If an error is detected,
        an exception is returned instead of a Series. Note that the exception
        is not raised here, but intended to be detected by the
        compute_target_rows(), i.e., the dispatcher function.

        :param filtered_df: |DataFrame| retrieved from persistent storage,
          with index compatible with loc. The loc argument itself needs not be
          present in filtered_df, but is used to avoid recomputing in case
          overwrite is not True and columns had been set.
        :param index: index value or values corresponding to the row to
          be processed.
        :param loc: location compatible with .loc of filtered_df (although it
          might not be present there), and that will be set into the full
          loaded_df also using its .loc accessor.
        :param column_fun_tuples: a list of (column, fun) tuples,
           where fun is to be invoked to fill column
        :param overwrite: if True, existing values are overwritten with
          newly computed data

        :return: a `pandas.Series` instance corresponding to this row,
          with a column named as given by self.private_index_column set to the
          `loc` argument passed to this function.
        """
        # pylint: disable=too-many-arguments,too-many-branches,too-many-locals
        try:
            row = filtered_df.loc[loc].copy()
        except KeyError:
            row = pd.Series({k: None for k in self.column_to_properties.keys()})

        with enb.logger.debug_context(
                f"Computing {self.__class__.__name__}'s row for index {index}"):
            called_functions = set()
            for column, fun in column_fun_tuples:
                if fun in called_functions:
                    if row[column] is None:
                        raise ValueError(
                            f"{self.__class__.__name__} failed to fill column {column} "
                            f"with a not-None value. " + (
                                "Note that functions starting with column_ should either "
                                "return a value or raise an exception"
                                if fun.__name__.startwith(
                                    MetaTable.automatic_column_function_prefix) else ""))
                    enb.logger.debug(
                        f"Already called function {fun.__name__} "
                        f"<{self.__class__.__name__}>")
                    continue
                if options.selected_columns and column not in options.selected_columns:
                    enb.logger.debug(f"Skipping non-selected column {column}")
                    continue

                if overwrite or column not in row or row[column] is None:
                    skip = False
                else:
                    try:
                        skip = not math.isnan(float(row[column]))
                    except (ValueError, TypeError):
                        skip = len(str(row[column])) > 0
                if skip:
                    enb.logger.debug(
                        f"Skipping existing value for column {repr(column)},  "
                        f"index={repr(index)} <{self.__class__.__name__}>")
                    continue

                enb.logger.debug(f"Calculating {repr(column)} for "
                                f"index={repr(index)}, fun={fun}, "
                                f"<{self.__class__.__name__}>")
                try:
                    result = fun(self, index, row)
                    called_functions.add(fun)

                    if row[column] is None:
                        raise ValueError(
                            f"{self.__class__.__name__} failed to fill "
                            f"column {repr(column)}, index {repr(index)}")

                    if result is not None \
                            and enb.logger.level_active(enb.logger.info.name) \
                            and not fun.__name__.startswith(
                        MetaTable.automatic_column_function_prefix):
                        enb.logger.warn(
                            f"Function {fun.__name__} returned a non-None value "
                            f"({repr(result)} "
                            f"when setting column {repr(column)}. "
                            f"This value is ignored, and row['{column}'] is used instead.")

                # pylint: disable=broad-except
                except Exception as ex:
                    stack_start_message = \
                        "-" * (shutil.get_terminal_size()[0] // 5) + \
                        f" [START stack trace @ {enb.misc.get_node_name()}" \
                        f"#{os.getpid()} " \
                        f"({ex.__class__.__name__}) <{self.__class__.__name__}>]"
                    stack_end_message = \
                        "-" * (shutil.get_terminal_size()[0] // 5) + \
                        f" [END stack trace @ {enb.misc.get_node_name()}" \
                        f"#{os.getpid()} " \
                        f"({ex.__class__.__name__}) <{self.__class__.__name__}>]"
                    stack_format = f"{{msg:->{shutil.get_terminal_size()[0]}s}}"
                    msg = f"{self.__class__.__name__}: " \
                          f"Error computing column {repr(column)}:" \
                          f"\n\t- Node: {enb.misc.get_node_name()}. " \
                          f"PID: {os.getpid()}" \
                          f"\n\t- Failing function: {fun.__qualname__}" \
                          f"\n\t- Failing index: {repr(index)}" \
                          f"\n\t- Caught exception: {repr(ex)}. " \
                          f"Showing stack trace next:\n" \
                          + stack_format.format(
                        msg=stack_start_message) + "\n" + \
                          f"{traceback.format_exc().strip()}\n" \
                          + stack_format.format(msg=stack_end_message)
                    if isinstance(ex,
                                  OSError) and ex.errno == 28:  # pylint: disable=no-member
                        msg += \
                            "NOTE: It seems to be an out-of-space error. " \
                            "If your disks have enough space, " \
                            "you might be running out of space in /dev/shm " \
                            "(or the equivalent in-memory " \
                            "file used for temporary execution in the " \
                            "experiments by default). If this is the case, " \
                            "you might need to change " \
                            "enb.config.options.base_tmp_dir to an existing dir in " \
                            "a partition with enough space, " \
                            "e.g., running with --base_tmp_dir=./tmp.\n"
                    cfe = ColumnFailedError(atable=self, index=index,
                                            column=column, ex=ex, msg=msg)

                    if enb.config.options.verbose >= 0:
                        # Tests can set the verbose level to less than 0
                        # to avoid showing errors on
                        # specific points of their code
                        enb.logger.error(f"\n{msg}\n")

                    return cfe

            for index_name, index_value in zip(self.indices, unpack_index_value(index)):
                row[index_name] = index_value

            row["row_updated"] = datetime.datetime.now().isoformat()
            row[self.private_index_column] = loc

        return row

    def write_persistence(self, df, output_csv=None):
        """Dump a dataframe produced by this table into persistent storage.

        :param output_csv: if None, self.csv_support_path is used as the output path.
        """
        with enb.logger.debug_context(
                msg=f"Dumping CSV with {len(df)} entries into {output_csv}",
                msg_after=" dumped"):
            if any(p.has_object_values for p in
                   self.column_to_properties.values()):
                # If pickling is needed, a copy of the df is made so as not to modify the original.
                df = df.copy()
                for column, properties in self.column_to_properties.items():
                    if properties.has_object_values:
                        df[column] = df[column].apply(pickle.dumps)
            output_csv = output_csv if output_csv is not None else self.csv_support_path
            df.to_csv(output_csv, index=True)

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
                      + ", ".join(f"'{c}',{repr(row[c])}" for c in
                                  self.column_to_properties.keys()) \
                      + ");"
            struct_str_lines.append("".join(
                row_str.replace("True", "true").replace("False", "false")))
        struct_str_lines.append("]';")
        return "\n".join(struct_str_lines)

    @property
    def name(self):
        """Return the name of the table. Defaults to the table class name.
        """
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

    def __del__(self):
        """Upon deletion of an ATable instance, if the get_df method had not been called at
        some point, then a warning message is shown. This is to help new users realize
        a potential bug in their scripts that prevent the actual utilities of enb to be employed.
        """
        try:
            if not self._was_get_df_called:
                msg = f"\nWARNING: Instance {self} was initialized " \
                      f"but its get_df() method was never called.\nThis is not the expected " \
                      f"behaviour. Please check the documentation in case of doubt."
                try:
                    enb.logger.warn(msg)
                except:
                    # The enb.logger subsystem is not available anymore
                    print(msg)
        except AttributeError:
            pass


class SummaryTable(ATable):
    """Summary tables allow to define custom group rows of dataframes,
    e.g., produced by ATable subclasses,
    and to define new columns (measurements) for each of those groups.

    Column functions can be defined in the same way as for any ATable. In
    this case, the index elements passed to the column functions are the
    group labels returned by split_groups(). Column functions can then access
    the corresponding dataframe with self.label_to_df[label].

    Note that this behaviour is not unlike the groupby() method of pandas.
    The main differences are:

    - Grouping can be fully customized, instead of only allowing splitting
      by one or more column values

    - The newly defined columns can aggregate data in the group in any
      arbitrary way. This is of course true for pandas, but SummaryTable
      tries to gracefully integrate that process into enb, allowing
      automatic persistence, easy plotting, etc.

    SummaryTable can be particularly useful as an intermediate step between a
    complex table's (or enb.Experiment's) get_df and the analyze_df method of
    analyzers en :mod:`enb.aanalysis`.
    """

    def __init__(self, full_df, column_to_properties=None, copy_df=False,
                 csv_support_path=None, group_by=None, include_all_group=False):
        """
        Initialize a summary table.
         Group splitting is not invoked until needed by calling self.get_df().

        Column-setting columns are given the group label and the row to be
        completed. They can access self.label_to_df to get the dataframe
        corresponding to the row's group.

        :param full_df: reference pandas dataframe to be summarized.
        :param column_to_properties: if not None,
        it should be the column_to_properties attribute
          of the table that produced reference_df.
        :param copy_df: if not True, a pointer to the original reference_df is used.
          Otherwise, a copy is made.
          Note that reference_df is typically evaluated each time split_groups() is called.
        :param csv_support_path: if not None, a CSV file is used at that for persistence.
        :param include_all_group: if True, a group "All" with all
          samples is included in the summary.
        """
        # pylint: disable=too-many-arguments
        super().__init__(csv_support_path=csv_support_path, index="group_label")
        self.reference_df = full_df if copy_df is not True else pd.DataFrame.copy(
            full_df)
        self.reference_column_to_properties = dict(
            column_to_properties) if column_to_properties is not None else None
        self.group_by = group_by
        self.include_all_group = include_all_group

    def split_groups(self, reference_df=None, include_all_group=None):
        """Split the reference_df |DataFrame| into an iterable of (label, dataframe) tuples.
        This splitting is performed based on the value of self.group_by:

        - If it is None, a single group labelled "all" is created, associated to reference_df.
        - If it is not None:
            - It can be a |DataFrame| column index, e.g., a column name or a list of column names.
              In this case, the result pandas' groupby is returned.
            - It can be a callable with a single argument reference_df.
              In this case, the result of calling that method with reference_df as argument
              is returned by the call to split_groups().


        Subclasses can easily implement grouping custom grouping methods,
        which must adhere to the following constraints:
        - It must return an iterable of group_label, group_df tuples.
        - Unique group_label values must be returned.

        Also note that:

        - It is NOT needed that the union of all group_df tuples yield
          reference_df.
        - It is NOT needed that the intersection of the any two group_df elements is empty.
        - The group_df dataframes normally contain all columns in reference_df, but
          it is NOT mandatory to maintain this behavior.


        :param reference_df: if not None, a reference dataframe to split.
          If None, self.reference_df is employed instead.
        :param include_all_group: if True, an "All" group is added, containing all input samples,
          regardless of the groups produced based on groupby. If None, self's class is queried
          for that attribute.
        :return: an iterable of (label, dataframe) tuples.
        """
        reference_df = reference_df if reference_df is not None else self.reference_df
        all_group_iterable = [("All", reference_df)]
        include_all_group = include_all_group \
            if include_all_group is not None else self.include_all_group

        if self.group_by is None:
            return all_group_iterable
        try:
            return itertools.chain(sorted(self.group_by(reference_df)),
                                   all_group_iterable if include_all_group else [])
        except TypeError:
            groups = list(
                itertools.chain(sorted(reference_df.groupby(self.group_by)),
                                all_group_iterable if include_all_group else []))
            return groups

    def get_df(self, *args, reference_df=None, include_all_group=None,
               **kwargs):
        """Get the summary dataframe. This class only defines the
        'group_size' column for the output dataframe. Subclasses may add as
        many columns to the summary as desired.

        :param reference_df: if not None, the dataframe to be used as
          reference for the summary. If None, the one provided at
          initialization is used.

        :return: the summary dataframe with all columns defined for self's class.
        """
        # pylint: disable=arguments-differ
        if hasattr(self, "label_to_df"):
            raise RuntimeError(
                "self.label_to_df should not be defined externally")
        # pylint: disable=attribute-defined-outside-init
        self.label_to_df = collections.OrderedDict()
        try:
            for label, df in self.split_groups(reference_df=reference_df,
                                               include_all_group=include_all_group):
                label = str(
                    label)  # Needed to force labels being displayable strings
                if label in self.label_to_df:
                    raise ValueError(
                        f"[E]rror: split_groups of {self} returned label "
                        f"{label} at least twice. "
                        f"Group labels must be unique.")
                self.label_to_df[label] = df
            target_indices = list(self.label_to_df.keys())
            return super().get_df(target_indices=target_indices, *args,
                                  **kwargs)
        finally:
            try:
                del self.label_to_df
            except AttributeError:
                pass

    def column_group_size(self, index, row):
        """Number of elements (rows from full_df) in the group.
        """
        # pylint: disable=unused-argument
        return len(self.label_to_df[index])

    def column_group_label(self, index, row):
        """Set the name of the group in a column.
        """
        # pylint: disable=unused-argument,no-self-use
        return index


def string_or_float(cell_value):
    """Takes the input value from an |ATable| cell and returns either its
    float value or its string value. In the latter case, one level of
    surrounding ' or " is removed from the value before returning. :return:
    the string or float value given by cell_value
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
    """Parse a |DataFrame|'s cell value in a column declared to contain
    non-scalar types, i.e., dict, list or tuple.
    Return an instance of one of those types.

    If cell_value is a string, ast is employed to parse it.
    If cell_Value is a dict, list or tuple, it is returned without modification.
    Otherwise, an error is raised.

    Note that |ATable| subclasses produce dataframes with the intended data
    types also for non-scalar types. This method is provided as a convenience
    tool for the case when raw CSV files produced by |enb| are read directly,
    and not through |ATable|'s persistence system.
    """
    if isinstance(cell_value, (dict, list, tuple)):
        return cell_value
    if isinstance(cell_value, str):
        return ast.literal_eval(cell_value)
    raise ValueError(f"Cannot identify non-scalar value {repr(cell_value)}")


def check_unique_indices(df):
    """Verify that df has no duplicated indices, or raise a CorruptedTableError.
    """
    # Verify consistency
    duplicated_indices = df.index.duplicated()
    if duplicated_indices.any():
        msg = "Loaded table with the following DUPLICATED indices:\n\t: "
        msg += "\n\t:: ".join(str(' , '.join(values))
                              for values in
                              df[duplicated_indices][df.example_indices].values)
        raise CorruptedTableError(atable=None, msg=msg)


def indices_to_internal_loc(values):
    """Given an index string or list of strings, return a single index string
    that uniquely identifies those strings and can be used as an internal index.

    This is used internally to set the actual |DataFrame|'s index value to a unique
    value that represents the row's index. Note that |DataFrame|'s subindexing is
    intentionally not used to maintain a simple, flat structure of tables without nesting.

    :return: a unique string for indexing given the input values
    """
    if isinstance(values, (str, numbers.Number)):
        values = [values]

    values = [
        get_canonical_path(v) if isinstance(v, str) and os.path.exists(v) else v
        for v in values]

    return str(tuple(values))


def unpack_index_value(index):
    """Unpack an enb-created |DataFrame| index and return its elements.
    This can be useful to iterate homogeneously regardless of whether single
    or multiple indices are used.

    :return: If input is a string, it returns a list with that column name.
      If input is a list, it returns self.index.
    """
    if isinstance(index, (str, numbers.Number)):
        return [index]
    return list(index)


@enb.parallel.parallel()
def parallel_compute_one_row(atable_instance, filtered_df, index, loc,
                             column_fun_tuples, overwrite):
    """Ray wrapper for :meth:`ATable.process_row`
    """
    # pylint: disable=too-many-arguments
    return atable_instance.compute_one_row(
        filtered_df=filtered_df,
        index=index,
        loc=loc,
        column_fun_tuples=column_fun_tuples,
        overwrite=overwrite)


def column_function(*column_property_list, **kwargs):
    """New columns can be added to |ATable| subclasses by decorating them with
    @enb.atable.column_function,
    e.g., with code similar to the following::

        class TableA(enb.atable.ATable):
        @enb.atable.column_function("uppercase", label="Uppercase version of the index")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()

    The `column_property_list` argument can be one of the following options:

    - one or more strings, which are interpreted as the new column(s)' name(s).
      For example::

        class TableC(enb.atable.ATable):
        @enb.atable.column_function("uppercase", "lowercase")
        def set_character_sum(self, index, row):
            row["uppercase"] = index.upper()
            row["lowercase"] = index.lower()


    - one or more |ColumnProperties| instances, one for each defined column.
    - a list of |ColumnProperties| instances, e.g., by invoking
      `@column_function([cp1,cp2])`,
      where `cp1` and `cp2` are |ColumnProperties| instances.
      This option is deprecated and provided for backwards compatibility only.
      If `properties=[cp1,cp2]`, then `@column_function(l)` (deprecated)
      and `@column_function(*l)`
      should result in identical column definitions.


    Decorator to allow definition of table columns for still undefined
    classes. To do so, MetaTable keeps track of |column_function|-decorated
    methods while the class is being defined. Then, when the class is
    created, MetaTable adds the columns defined by the decorated functions.

    :param column_property_list: list of column property definitions, as described above.
    :return: the wrapper that actually decorates the function using the
      column_property_list and kwargs parameters.
    """
    kwargs = dict(kwargs)

    column_property_list = list(column_property_list)

    def inner_wrapper(decorated_method):
        try:
            cls_name = get_defining_class_name(decorated_method)
        except IndexError as ex:
            raise SyntaxError(
                "Detected a non-class method decorated with @enb.atable.column_function, "
                "which is not supported.") from ex

        # Normalize arguments and add to the list of functions pending to be registered.
        normalized_list = ATable.normalize_column_function_arguments(
            column_property_list=column_property_list, fun=decorated_method,
            **kwargs)

        MetaTable.pendingdefs_classname_fun_columnpropertylist.append(
            (cls_name, decorated_method, normalized_list))

        return decorated_method

    return inner_wrapper


def redefines_column(fun):
    """When an |ATable| subclass defines a method with the same name as any of the
    parent classes, and when that method defines a column, it must be decorated with this.

    Otherwise, a SyntaxError is raised. This is to prevent hard-to-find bugs
    where a parent class' definition of the method is used when filling a
    row's column, but calling that method on the child's instance runs the
    child's code.

    Functions decorated with this method acquire a _redefines_column attribute,
    that is then identified by
    :meth:`enb.atable.ATable.add_column_function`, i.e., the method responsible
    for creating columns.

    Note that _redefines_column attributes for non-column and non-overwritting
    methods are not employed by |enb| thereafter.

    :param fun: rewriting function being decorated
    """
    # pylint: disable=protected-access
    fun._redefines_column = True
    return fun


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
        cls = getattr(
            inspect.getmodule(meth),
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
    base_dataset_dir = base_dataset_dir \
        if base_dataset_dir is not None else options.base_dataset_dir
    if base_dataset_dir is None or not os.path.isdir(base_dataset_dir):
        enb.logger.debug(
            f"Cannot get input samples from {base_dataset_dir} "
            f"(path not found or not a dir). "
            f"Using [sys.argv[0]] = [{os.path.basename(sys.argv[0])}] instead.")
        return [os.path.basename(sys.argv[0])]

    # Recursively get all files, filtering only those that match the extension, if provided.
    sorted_path_list = sorted(
        (get_canonical_path(p) for p in glob.glob(
            os.path.join(base_dataset_dir, "**", f"*{ext}" if ext else "*"),
            recursive=True)
         if os.path.isfile(p)),
        key=lambda p: get_canonical_path(p).lower())

    # If quick is selected, return at most as many paths as the quick parameter count
    all_input_files = sorted_path_list if not options.quick else sorted_path_list[
                                                                 :options.quick]

    return all_input_files


def get_canonical_path(file_path):
    """
    :return: the canonical version of a path to be stored in the database, to make sure
      indexing is consistent across code using |ATable| and its subclasses.
    """
    if enb.parallel_ray.is_remote_node():
        return os.path.relpath(file_path, enb.parallel_ray.RemoteNode.remote_project_mount_path)
    return os.path.relpath(file_path, options.project_root)
