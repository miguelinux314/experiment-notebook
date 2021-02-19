#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Automatic tables with implicit column definition.

* Tables are created by specifying the index columns (one or more),
  and optionally a path to a file where precomputed values are stored.

* Table columns are defined via the @YourATableSubclass.column_function
  decorator. Decorated functions implicitly define the table, since they
  are called to fill the corresponding cells for each index.

* The ATable.get_df method can be invoked to obtain the df for any given set of indices


* For example

  ::

        import ray
        from enb import atable

        class Subclass(atable.ATable):
            @atable.column_function("index_length")
            def set_index_length(self, index, row):
                row["index_length"] = len(index)

        ray.init()
        sc = Subclass(index="index")
        df = sc.get_df(target_indices=["a"*i for i in range(10)])
        print(df.head())

  Should return:

  ::

                           index index_length
        __atable_index
        ('',)                           0
        ('a',)             a            1
        ('aa',)           aa            2
        ('aaa',)         aaa            3
        ('aaaa',)       aaaa            4


  * See ScalarDistributionAnalyzer for automatic reports using ATable
"""
from builtins import hasattr

__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "19/09/2019"

import os
import sys
import itertools
import collections
import pandas as pd
import math
import copy
import functools
import time
import datetime
import inspect
import traceback
import ray

from enb.config import get_options
from enb import config
from enb import ray_cluster

options = get_options()


class CorruptedTableError(Exception):
    """Raised when a table is Corrupted, e.g., when loading a
    CSV with missing indices
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
    """Raised when a function failed to fill a column
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
    """Static properties of a table's column. Use this class to provide metainformation
    about rendering options.
    """

    def __init__(self, name, fun=None, label=None, plot_min=None, plot_max=None,
                 semilog_x=False, semilog_y=False,
                 semilog_x_base=10, semilog_y_base=10,
                 hist_label=None, hist_min=None, hist_max=None,
                 hist_bin_width=None, has_dict_values=False, hist_label_dict=None,
                 **extra_attributes):
        """
        Main parameters:
        :param name: unique name that identifies a column. Column names can be overwritten
          in subclasses with the @ATable.column_function decorator.
        :param fun: function to be invoked to fill a column value. It should be none when
          passed to the @ATable.column_function decorator.
        :param label: main version of the column's name, to be displayed in labels.
        :param has_dict_values: True only if the column cells contain value mappings (i.e., dicts),
          as opposed to scalar values.


        Plot rendering hints:
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

        :param **extra_extra_attributes: any parameters passed are set as attributes
        """
        self.name = name
        self.fun = fun
        self.label = label
        self.plot_min = plot_min
        self.plot_max = plot_max
        self.semilog_x = semilog_x
        self.semilog_y = semilog_y
        self.semilog_x_base = semilog_x_base
        self.semilog_y_base = semilog_y_base
        self.hist_bin_width = hist_bin_width
        self.has_dict_values = has_dict_values or self.hist_bin_width is not None
        self.hist_label_dict = hist_label_dict
        self.hist_label = hist_label
        self.hist_min = hist_min
        self.hist_max = hist_max
        for k, v in extra_attributes.items():
            self.__setattr__(k, v)

    def __repr__(self):
        args = ", ".join(f"{k}={v}" for k, v in self.__dict__.items() if v is not None)
        return f"{self.__class__.__name__}({args})"


class MetaTable(type):
    """Metaclass for ATable and all subclasses, which
    guarantees that the column_to_properties is a static OrderedDict,
    different from other classes' column_to_properties. This way,
    @column_function and all subclasses can access and update
    the dict separately for each class (as logically intended).

    Note: Table clases should inherit from ATable, not MetaTable
    """
    pendingdefs_classname_fun_columnproperties_kwargs = []

    def __new__(cls, name, bases, dct):
        assert MetaTable not in bases, f"Use ATable, not MetaTable, for subclassing"
        for base in bases:
            try:
                _ = base.column_to_properties
            except AttributeError:
                base.column_to_properties = collections.OrderedDict()
        dct.setdefault("column_to_properties", collections.OrderedDict())
        subclass = super().__new__(cls, name, bases, dct)

        for base in bases:
            try:
                # It is ok to update keys later decorated in the
                # subclasses. That happens after metracreation,
                # therefore overwrites the following updates
                subclass.column_to_properties.update(base.column_to_properties)
            except AttributeError:
                pass

        # Make sure that subclasses do not re-use a base class column
        # function name without it being decorated as column function
        # (unexpected behavior)
        for column, properties in subclass.column_to_properties.items():
            defining_class_name = get_class_that_defined_method(properties.fun).__name__
            if defining_class_name != subclass.__name__:
                ctp_fun = properties.fun
                sc_fun = getattr(subclass, properties.fun.__name__)
                if ctp_fun != sc_fun:
                    if get_defining_class_name(ctp_fun) != get_defining_class_name(sc_fun):
                        if hasattr(sc_fun, "_redefines_column"):
                            properties = copy.copy(properties)
                            properties.fun = ATable.build_column_name_wrapper(fun=sc_fun, column_properties=properties)
                            subclass.column_to_properties[column] = properties
                        else:
                            print(f"[W]arning: {defining_class_name}'s subclass {subclass.__name__} "
                                  f"overwrites method {properties.fun.__name__}, "
                                  f"but it does not decorate it with @atable.column_function "
                                  f"for column {column}. "
                                  f"The method from class {defining_class_name} will be used to fill "
                                  f"the table's column {column}. Consider decorating the function "
                                  f"with the same @atable.column_function as the base class, "
                                  f"or simply with @atable.redefines_column to maintain the same "
                                  f"difinition")

        # Add pending methods (declared as columns before subclass existed)
        for classname, fun, cp, kwargs in cls.pendingdefs_classname_fun_columnproperties_kwargs:
            if classname != name:
                raise SyntaxError(f"Not expected to find a decorated function {fun.__name__}, "
                                  f"classname={classname} when defining {name}.")
            ATable.add_column_function(cls=subclass, column_properties=cp, fun=fun, **kwargs)
        cls.pendingdefs_classname_fun_columnproperties_kwargs.clear()

        return subclass


class ATable(metaclass=MetaTable):
    """Automatic table, that allows decorating functions to fill dependent variable
    columns
    """
    # Name of the index used internally
    private_index_column = "__atable_index"
    # Column names in this list are not retrieved nor saved to file
    ignored_columns = []

    def __init__(self, index="file_path", csv_support_path=None, column_to_properties=None):
        """
        :param index: column name or list of column names that will be
          used for indexing. Indices provided to self.get_df must be
          either one instance (when a single column name is given)
          or a list of as many instances as elemnts are contained in self.index.
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

    @classmethod
    def column_function(cls, column_properties, **kwargs):
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

        :param column_properties: one of the following options:

          * a string with the column's name to be used in the table
          * a list of strings of length at least one, defining len(column_properties) columns
          * a ColumnProperties instance, or a list thereof, defining 1 and len(column_properties) column, respectively

          All columns defined this way must be set in the row instance received by the decorated function
        """

        def decorator_wrapper(fun):
            return ATable.add_column_function(cls=cls, column_properties=column_properties,
                                              fun=fun, **kwargs)

        return decorator_wrapper

    @classmethod
    def redefines_column(cls, fun):
        """Decorator to be applied on overwriting methods that are meant to fill
        the same columns as the base class' homonymous method.
        """
        fun._redefines_column = True
        return fun

    @staticmethod
    def normalize_column_properties(column_properties, fun):
        """Helper method to transform the arguments of add_column_function into
        a nonempty list of valid ColumnProperties instances.

        :param column_properties: the column_properties parameter to add_column_function()
        :param fun: the function being decorated
        """

        def normalize_one_element(element):
            """:return: a ColumnProperties instance
            """
            if isinstance(element, str):
                cp = ColumnProperties(name=element, fun=fun)
            elif isinstance(element, ColumnProperties):
                cp = copy.copy(element)
                cp.fun = fun if cp.fun is None else cp.fun
                if not hasattr(fun, "_redefines_column"):
                    assert cp.fun is None or cp.fun is fun, f"{cp.fun}, {fun}"
            else:
                raise TypeError(type(element))
            return cp

        try:
            if isinstance(column_properties, str):
                raise TypeError
            column_properties = list(column_properties)
        except TypeError:
            column_properties = [column_properties]
        for i in range(len(column_properties)):
            column_properties[i] = normalize_one_element(column_properties[i])
        return column_properties

    @staticmethod
    def add_column_function(cls, column_properties, fun, **kwargs):
        """Static implementation of @column_function. Subclasses may call
        this method directly when overwriting @column_function.
        """
        column_properties = cls.normalize_column_properties(
            column_properties=column_properties, fun=fun)
        for cp in column_properties:
            for k, v in kwargs.items():
                cp.__setattr__(k, v)

        assert all(cp.fun is None or cp.fun is fun
                   for cp in column_properties), (id(fun), [id(cp.fun) for cp in column_properties])

        fun_wrapper = cls.build_column_name_wrapper(fun=fun, column_properties=column_properties)

        column_to_properties_dict = cls.column_to_properties
        for cp in column_properties:
            cp.fun = fun_wrapper
            column_to_properties_dict[cp.name] = cp

        return fun_wrapper

    @classmethod
    def build_column_name_wrapper(cls, fun, column_properties):
        column_properties = cls.normalize_column_properties(column_properties=column_properties, fun=fun)

        @functools.wraps(fun)
        def fun_wrapper(*args, **kwargs):
            if isinstance(fun, functools.partial):
                globals = fun.func.__globals__
            else:
                globals = fun.__globals__

            old_globals = dict(globals)
            globals.update(_column_name=column_properties[0].name if len(column_properties) == 1 else None,
                           _column_properties=column_properties)
            try:
                return fun(*args, **kwargs)
            finally:
                globals.clear()
                globals.update(old_globals)

        return fun_wrapper

    @property
    def indices(self):
        """If self.index is a string, it returns a list with that column name.
        If self.index is a list, it returns self.index.
        Useful to iterate homogeneously regardless of whether single or multiple indices are used.
        """
        return unpack_index_value(self.index)

    @property
    def indices_and_columns(self):
        """
        :return: a list of all defined columns, i.e., those for which
          a function has been defined
        """
        return self.indices + list(k for k in self.column_to_properties.keys()
                                   if k not in itertools.chain(self.indices, self.ignored_columns))

    def get_df(self, target_indices, target_columns=None,
               fill=True, overwrite=False, parallel_row_processing=True,
               chunk_size=None):
        """Return a pandas DataFrame containing all given indices and defined columns.
        If fill is True, missing values will be computed.
        If fill and overwrite are True, all values will be computed, regardless of
        whether they are previously present in the table.

        :param target_indices: list of indices that are to be contained in the table
        :param target_columns: if not None, it must be a list of column names that
          are to be obtained for the specified indices. If not None, only those
          columns are computed.
        :param fill: values are computed for the selected indices only if fill is True
        :param overwrite: values selected for filling are computed even if they are present
          in permanent storage. Otherwise, existing values are skipped from the computation.
        :param parallel_row_processing: if True, processing of rows is performed in a parallel,
           possibly distributed fashion. Otherwise, they are processed serially using the invoking thread.
        :param chunk_size: If None, its value is assigned from options.chunk_size. After this, 
           if not None, the list of target indices is split in 
           chunks of size at most chunk_size elements. Results are made persistent every time
           one of these chunks is completed. If None, a single chunk is defined with all
           indices, and results are made persistent only once. 

        :return: a DataFrame instance containing the requested data
        :raises: CorrupedTableError, ColumnFailedError, when an error is encountered
          processing the data.
        """
        target_indices = list(target_indices)
        assert len(target_indices) > 0, "At least one index must be provided"

        chunk_size = chunk_size if chunk_size is not None else options.chunk_size
        chunk_size = chunk_size if chunk_size is not None else len(target_indices)
        chunk_size = chunk_size if not options.quick else len(target_indices)
        assert chunk_size > 0, f"Invalid chunk size {chunk_size}"
        chunk_list = [target_indices[i:i + chunk_size] for i in range(0, len(target_indices), chunk_size)]
        assert len(chunk_list) > 0
        for i, chunk in enumerate(chunk_list):
            if options.verbose:
                print(f"[{self.__class__.__name__}:get_df] Starting chunk {i + 1}/{len(chunk_list)} "
                      f"@@ {100 * i * chunk_size / len(target_indices):.1f}"
                      f"-{min(100, 100 * ((i+1)*chunk_size) / len(target_indices)):.1f}% "
                      f"({datetime.datetime.now()})")
            df = self.get_df_one_chunk(
                target_indices=chunk, target_columns=target_columns, fill=fill,
                overwrite=overwrite, parallel_row_processing=parallel_row_processing)

        if len(chunk_list) > 1:
            # Get the full df if more thank one chunk is requested
            df = self.get_df_one_chunk(
                target_indices=target_indices, target_columns=target_columns, fill=fill,
                overwrite=overwrite, parallel_row_processing=parallel_row_processing)

        return df

    def get_df_one_chunk(self, target_indices, target_columns=None,
                         fill=True, overwrite=False, parallel_row_processing=True):
        """Implementation the :meth:`get_df` for one chunk of indices
        """
        ray_cluster.init_ray()

        if options.verbose > 2:
            print("Loading data and/or defaults...")
        table_df = self._load_saved_df()
        if options.verbose > 2:
            print("... loaded data and/or defaults!")

        if not options.no_new_results:
            # Parallel read of current and/or default (with fields set to None) rows
            loaded_df_id = ray.put(table_df)
            index_ids = [ray.put(index) for index in target_indices]
            index_columns_id = ray.put(tuple(self.indices))
            all_columns_id = ray.put(self.indices_and_columns)
            loaded_rows_ids = [ray_get_row_or_default.remote(
                loaded_df_id, index_id, index_columns_id, all_columns_id)
                for index_id in index_ids]
            assert len(index_ids) == len(target_indices)
            assert len(loaded_rows_ids) == len(target_indices)

            column_fun_tuples = [(column, properties.fun)
                                 for column, properties in self.column_to_properties.items()
                                 if column not in self.ignored_columns]

            if target_columns is not None:
                len_before = len(column_fun_tuples)
                column_fun_tuples = [t for t in column_fun_tuples if t[0] in target_columns]
                assert column_fun_tuples, (target_columns, sorted(self.column_to_properties.keys()))
                if options.verbose:
                    print(
                        f"[O]nly for columns {', '.join(target_columns)} ({len_before}->{len(column_fun_tuples)} cols)")

            if not parallel_row_processing:
                # Serial computation, e.g., to favor accurate time measurements
                returned_values = []
                for index, row in zip(target_indices, ray.get(loaded_rows_ids)):
                    try:
                        returned_values.append(self.process_row(
                            index=index, column_fun_tuples=column_fun_tuples,
                            row=row, overwrite=overwrite, fill=fill))
                    except ColumnFailedError as ex:
                        returned_values.append(ex)
            else:
                self_id = ray.put(self)
                options_id = ray.put(options)
                overwrite_id = ray.put(overwrite)
                fill_id = ray.put(fill)
                column_fun_tuples_id = ray.put(column_fun_tuples)
                processed_row_ids = [ray_process_row.remote(
                    atable=self_id, index=index_id, row=row_id,
                    column_fun_tuples=column_fun_tuples_id,
                    overwrite=overwrite_id, fill=fill_id,
                    options=options_id)
                    for index_id, row_id in zip(index_ids, loaded_rows_ids)]
                time_before = time.time()
                while True:
                    ids_ready, _ = ray.wait(processed_row_ids, num_returns=len(processed_row_ids), timeout=60.0)
                    if len(ids_ready) == len(processed_row_ids):
                        break
                    if any(isinstance(id_ready, Exception) for id_ready in ids_ready):
                        break

                    if options.verbose:
                        if ids_ready:
                            time_per_id = (time.time() - time_before) / len(ids_ready)
                            eta = (len(processed_row_ids) - len(ids_ready)) * time_per_id
                            msg = f"ETA: {eta} s"
                        else:
                            msg = "No ETA available"

                        print(f"{len(ids_ready)} / {len(processed_row_ids)} ready @ {datetime.datetime.now()}. {msg}")
                returned_values = ray.get(processed_row_ids)

            unpacked_target_indices = list(indices_to_internal_loc(unpack_index_value(target_index))
                                           for target_index in target_indices)
            index_exception_list = []
            for index, row in zip(unpacked_target_indices, returned_values):
                if isinstance(row, Exception):
                    if options.verbose:
                        print(f"[E]rror processing index {index}: {row}")
                    index_exception_list.append((index, row))
                    try:
                        table_df = table_df.drop(index)
                    except KeyError as ex:
                        pass
                else:
                    table_df.loc[index] = row
        else:
            index_exception_list = []

        table_df = table_df[[c for c in table_df.columns if c not in self.ignored_columns]]

        # All data (new or previously loaded) is saved to persistent storage
        # if (a) all data were successfully obtained or
        #    (b) the save_partial_results options is enabled
        if not options.no_new_results and self.csv_support_path and \
                (not index_exception_list or not options.discard_partial_results):
            os.makedirs(os.path.dirname(os.path.abspath(self.csv_support_path)), exist_ok=True)
            table_df.to_csv(self.csv_support_path, index=False)

        # A DataFrame is NOT returned if any error is produced
        if index_exception_list:
            raise CorruptedTableError(
                atable=self, ex=index_exception_list[0][1],
                msg=f"{len(index_exception_list)} out of"
                    f" {len(target_indices)} errors happened. "
                    f"Run with --exit_on_error to obtain a full "
                    f"stack trace of the first error.")

        # Sanity checks before returning the DataFrame with only the requested indices
        # Verify loaded indices are ok (sanity check)
        check_unique_indices(table_df)
        for ti in target_indices:
            internal_index = indices_to_internal_loc(ti)
            assert internal_index in table_df.index, (internal_index, table_df.loc[internal_index])
        target_internal_indices = [indices_to_internal_loc(ti) for ti in target_indices]
        table_df = table_df.loc[target_internal_indices, self.indices_and_columns]
        assert len(table_df) == len(target_indices), \
            "Unexpected table length / requested indices " \
            f"{(len(table_df), len(target_indices))}"

        return table_df

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

    def process_row(self, index, column_fun_tuples, row, overwrite, fill):
        """Process a single row of an ATable instance, filling
        values in row.

        :param index: index value or values corresponding to the row to
          be processed
        :param column_fun_tuples: a list of (column, fun) tuples,
           where fun is to be invoked to fill column
        :param row: dict-like object containing loaded information, and
          where the column keys are to be set
        :param overwrite: if True, existing values are overwriten with
          newly computed data
        :param fill: if False, the row is not processed, it is returned as read instead
        :param options: runtime options

        :return: row, after filling its contents
        """
        if not fill:
            return row

        called_functions = set()
        for column, fun in column_fun_tuples:
            if fun in called_functions:
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
                if options.verbose:
                    print(repr(ex))
                ex = ColumnFailedError(atable=self, index=index, column=column, ex=ex)
                if options.exit_on_error:
                    traceback.print_exc()
                    print()
                    print(f"Exiting because options.exit_on_error = {options.exit_on_error}")
                    sys.exit(-1)
                else:
                    return ex

        return row

    def _load_saved_df(self):
        """Load the df stored in permanent support (if any), otherwise an empty dataset,
        verifying that no duplicated indices exist based on atable.indices_to_internal_loc.

        :return: the loaded table_df, which may be empty
        """
        try:
            if not self.csv_support_path:
                raise FileNotFoundError(self.csv_support_path)
            loaded_df = pd.read_csv(self.csv_support_path)
            # for column in (c for c in self.indices_and_columns if c not in self.indices):
            for column in self.indices_and_columns:
                if column not in loaded_df.columns:
                    loaded_df[column] = None
            for index_name in self.indices:
                if loaded_df[index_name].isnull().any():
                    raise CorruptedTableError(atable=self,
                                              msg=f"Loaded table from {self.csv_support_path} with empty "
                                                  f"values for index {index_name} (at least)")
            loaded_df = loaded_df[self.indices_and_columns]
            for column, properties in self.column_to_properties.items():
                if properties.has_dict_values:
                    loaded_df[column] = loaded_df[column].apply(parse_dict_string)
        except FileNotFoundError as ex:
            if self.csv_support_path is None:
                if options.verbose > 2:
                    print(f"[I]nfo: no csv persistence support.")
            elif options.verbose:
                print(f"ATable supporting file {self.csv_support_path} could not be loaded " +
                      (f"({ex.__class__.__name__}) " if options.verbose > 1 else '') +
                      f"- creating an empty one")
            loaded_df = pd.DataFrame(columns=self.indices_and_columns)

        # Add private index column if necessary
        if len(loaded_df) > 0:
            loaded_df[self.private_index_column] = loaded_df.apply(
                lambda row: indices_to_internal_loc(row[self.indices].values), axis=1)
        else:
            loaded_df[self.private_index_column] = None
        loaded_df = loaded_df.set_index(self.private_index_column, drop=True)
        try:
            check_unique_indices(loaded_df)
        except CorruptedTableError as ex:
            print(f"Error loading table from {self.csv_support_path}")
            raise ex
        return loaded_df

def string_or_float(cell_value):
    """Takes the input value from an ATable cell and returns either
    its float value or its string value. In the latter case, one level of surrounding
    ' or " is removed from the value before returning.
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

def parse_dict_string(cell_value, key_type=string_or_float, value_type=float):
    """Parse a cell value for a string describing a dictionary.
    Some checks are performed based on ATable cell contents, i.e.,

      * if a dict is found it is returned directly
      * a Nan (empty cell) is also returned directly
      * otherwise a string starting by '{' and ending by '}' with 'key:value' pairs
        separated by ',' (and possibly spaces) is returned

    :param key_type: if not None, the key is substituted by a instantiation
      of that type with the key as argument
    :param value_type: if not None, the value is substituted by a instantiation
      of that type with the value as argument
    """
    if isinstance(cell_value, dict):
        return cell_value
    try:
        assert cell_value[0] == "{", (cell_value[0], f">>{cell_value}<<")
        assert cell_value[-1] == "}", (cell_value[-1], f">>{cell_value}<<")
    except TypeError as ex:
        if cell_value is None or math.isnan(cell_value):
            return cell_value
        raise TypeError(f"Trying to parse a dict string '{cell_value}', "
                        f"wrong type {type(cell_value)} found instead. "
                        f"Double check the has_dict_values column property.") from ex
    cell_value = cell_value[1:-1].strip()
    column_dict = dict()
    for pair in (cell_value.split(",") if cell_value else []):
        a, b = [s.strip() for s in pair.split(":")]
        if key_type is not None:
            a = key_type(a)
        if value_type is not None:
            b = value_type(b)
        assert a not in column_dict, f"A non-unique-key ({a}) dictionary string was found {cell_value}"
        column_dict[a] = b
    return column_dict


def check_unique_indices(df: pd.DataFrame):
    """Verify that df has no duplicated indices
    """
    # Verify consistency
    duplicated_indices = df.index.duplicated()
    if duplicated_indices.any():
        s = f"Loaded table with the following duplicated indices:\n\t: "
        duplicated_df = df[duplicated_indices]
        for i in range(len(duplicated_df)):
            print("[watch] duplicated_df.iloc[i] = {}".format(duplicated_df.iloc[i]))

        if options.verbose:
            print("[watch] df[duplicated_indices] = {}".format(df[duplicated_indices]))
            s += "\n\t:: ".join(str(' , '.join(values))
                            for values in df[duplicated_indices][df.indices].values)
            print(s)
        raise CorruptedTableError(atable=None)


def indices_to_internal_loc(values):
    """Given an index string or list of strings, return a single index string
    that uniquely identifies those strings and can be used as an internal index

    """
    if isinstance(values, str):
        values = [values]
    values = [os.path.abspath(v) if os.path.exists(v) else v for v in values]
    return str(tuple(values))


def unpack_index_value(input):
    """If input is a string, it returns a list with that column name.
    If input is a list, it returns self.index.
    Useful to iterate homogeneously regardless of whether single or multiple indices are used.
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
def ray_process_row(atable, index, column_fun_tuples, row, overwrite, fill, options):
    """Ray wrapper for :meth:`ATable.process_row`
    """
    return atable.process_row(index=index, column_fun_tuples=column_fun_tuples,
                              row=row, overwrite=overwrite, fill=fill)


def column_function(column_properties, **kwargs):
    """Decorator to allow definition of table columns for
    still undefined classes.

    Arguments follow the semantics defined in :meth:`ATable.column_function`.
    """

    def inner_wrapper(f):
        try:
            cls_name = get_defining_class_name(f)
        except IndexError:
            raise Exception(f"Are you decorating a non-method function {f.__name__}? Not allowed")

        MetaTable.pendingdefs_classname_fun_columnproperties_kwargs.append(
            (cls_name, f, column_properties, dict(kwargs))
        )

        return f

    return inner_wrapper


def redefines_column(f):
    """Decorator to mark a function as a column_function for all
    columns associated with functions with the same name as f.
    """
    f._redefines_column = True
    return f


def get_defining_class_name(f):
    return f.__qualname__.split('.<locals>', 1)[0].rsplit('.')[-2]


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
