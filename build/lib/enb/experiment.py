#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tools to run compression experiments
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "19/09/2019"

import os
import collections
import itertools
import inspect

from enb import atable
from enb import sets
from enb.config import get_options

options = get_options()


class ExperimentTask:
    """Identify an :py:class:`Experiment`'s task and its configuration.
    """

    def __init__(self, param_dict=None):
        """
        :param param_dict: dictionary of configuration parameters used
          for this task. By default, they are part of the task's name.
        """
        self.param_dict = dict(param_dict) if param_dict is not None else {}

    @property
    def name(self):
        """Unique name that uniquely identifies a task and its configuration.
        It is not intended to be displayed as much as to be used as an index.
        """
        name = f"{self.__class__.__name__}"
        if self.param_dict:
            name += "__" + "_".join(f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name

    @property
    def label(self):
        """Label to be displayed for the task in output reports.
        May not be strictly unique nor fully informative.
        By default, the task's name is returned.
        """
        return self.name

    def __repr__(self):
        return f"<{self.__class__.__name__} (" \
               + ', '.join(repr(param) + '=' + repr(value)
                           for param, value in self.param_dict.items()) \
               + ")>"


class Experiment(atable.ATable):
    """An Experiment allows seamless execution of one or more tasks upon a
    corpus of test files. Tasks are identified by a file index and a
    :py:class:`ExperimentTask`'s (unique) name.

    For each task, any number of table columns can be defined to gather
    results of interest. This allows easy extension to highly complex and/or
    specific experiments. See :func:`set_task_name` for an example.

    Automatic persistence of the obtained results is provided, to allow faster
    experiment development and result replication.

    Internally, an Experiment consists of an ATable containing the properties
    of the test corpus, and is itself another ATable that contains the
    results of an experiment with as many user-defined columns as needed.
    When the :meth:`~Experiment.get_df` method is called, a joint DataFrame
    instance is returned that contains both the experiment results, and the
    associated metainformation columns for each corpus element.
    """
    task_name_column = "task_name"
    task_label_column = "task_label"
    default_file_properties_table_class = sets.FilePropertiesTable

    def __init__(self, tasks,
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table=None,
                 overwrite_file_properties=False,
                 parallel_dataset_property_processing=None):
        """
        :param tasks: an iterable of :py:class:`ExperimentTask` instances. Each test file
          is processed by all defined tasks. For each (file, task) combination,
          a row is included in the table returned by :py:meth:`~get_df()`.
        :param dataset_paths: list of paths to the files to be used as input.
          If it is None, this list is obtained automatically calling sets.get_all_test_file()
        :param csv_experiment_path: if not None, path to the CSV file giving persistence
          support to this experiment.
          If None, it is automatically determined within options.persistence_dir.
        :param csv_dataset_path: if not None, path to the CSV file given persistence
          support to the dataset file properties.
          If None, it is automatically determined within options.persistence_dir.
        :param dataset_info_table: if not None, it must be a sets.FilePropertiesTable instance or
          subclass instance that can be used to obtain dataset file metainformation,
          and/or gather it from csv_dataset_path. If None, a new sets.FilePropertiesTable
          instance is created and used for this purpose.
          This parameter can also be a class (instead of an instance). In this case, it
          the initializer is asumed to accept a csv_support_path argument and be compatible
          with the sets.FilePropertiesTable interface.
        :param overwrite_file_properties: if True, file properties are necessarily
          computed before starting the experiment. This can be useful for temporary
          and/or random datasets. If False, file properties are loaded from the
          persistent storage when available. Note that this parameter does not
          affect whether experiment results are retrieved from persistent storage if available.
          This is controlled via the parameters passed to get_df()
        :param parallel_row_processing: if not None, it determines whether file properties
          are to be obtained in parallel. If None, it is given by not options.sequential.
        """
        self.tasks = list(tasks)

        dataset_paths = dataset_paths if dataset_paths is not None \
            else sets.get_all_test_files()

        if csv_dataset_path is None:
            csv_dataset_path = os.path.join(options.persistence_dir,
                                            f"{dataset_info_table.__class__.__name__}_persistence.csv")
        os.makedirs(os.path.dirname(csv_dataset_path), exist_ok=True)

        if dataset_info_table is None:
            dataset_info_table = self.default_file_properties_table_class(csv_support_path=csv_dataset_path)
        else:
            if inspect.isclass(dataset_info_table):
                dataset_info_table = dataset_info_table(csv_support_path=csv_dataset_path)
        self.dataset_info_table = dataset_info_table

        self.dataset_info_table.ignored_columns = \
            set(self.dataset_info_table.ignored_columns + self.ignored_columns)

        assert len(self.dataset_info_table.indices) == 1, \
            f"dataset_info_table is expected to have a single index"

        if options.verbose:
            print(f"Obtaining properties of {len(dataset_paths)} files... "
                  f"[dataset info: {type(self.dataset_info_table).__name__}]")
        self.dataset_table_df = self.dataset_info_table.get_df(
            target_indices=dataset_paths,
            parallel_row_processing=(parallel_dataset_property_processing
                                     if parallel_dataset_property_processing is not None
                                     else not options.sequential),
            overwrite=overwrite_file_properties)

        self.target_file_paths = dataset_paths

        if csv_experiment_path is None:
            csv_experiment_path = os.path.join(options.persistence_dir,
                                               f"{self.__class__.__name__}_persistence.csv")
        os.makedirs(os.path.dirname(csv_experiment_path), exist_ok=True)
        super().__init__(csv_support_path=csv_experiment_path,
                         index=self.dataset_info_table.indices + [self.task_name_column])

    def get_df(self, target_indices=None, fill=True, overwrite=False,
               parallel_row_processing=True, target_tasks=None,
               chunk_size=None):
        """Get a DataFrame with the results of the experiment. The produced DataFrame
        contains the columns from the dataset info table (but they are not stored
        in the experiment's persistence file).

        :param parallel_row_processing: if True, parallel computation is used to fill the df,
          including compression
        :param target_indices: list of file paths to be processed. If None, self.target_file_paths
          is used instead.  
        :param target_tasks: list of tasks to be applied to each file. If None, self.codecs
          is used instead.
        :param chunk_size: if not None, a positive integer that determines the number of table
          rows that are processed before made persistent.
        """
        target_indices = self.target_file_paths if target_indices is None else target_indices
        target_tasks = self.tasks if target_tasks is None else target_tasks

        self.tasks_by_name = collections.OrderedDict({task.name: task for task in target_tasks})
        target_task_names = [t.name for t in target_tasks]
        df = super().get_df(target_indices=tuple(itertools.product(
            sorted(set(target_indices)), sorted(set(target_task_names)))),
            parallel_row_processing=parallel_row_processing,
            fill=fill, overwrite=overwrite, chunk_size=chunk_size)
        
        # Add dataset columns
        rsuffix = "__redundant__index"
        df = df.join(self.dataset_table_df.set_index(self.dataset_info_table.index),
                     on=self.dataset_info_table.index, rsuffix=rsuffix)
        if options.verbose:
            redundant_columns = [c.replace(rsuffix, "")
                                 for c in df.columns if c.endswith(rsuffix)]
            if redundant_columns:
                print("[W]arning: redundant dataset/experiment column(s): " +
                      ', '.join(redundant_columns) + ".")
                
        
        # Add columns based on task parameters
        if len(df) > 0:
            task_param_names = set()
            for task in self.tasks_by_name.values():
                for k in task.param_dict.keys():
                    task_param_names.add(k)
            for param_name in task_param_names:
                def get_param_row(row):
                    file_path, task_name = row[self.index]
                    task = self.tasks_by_name[task_name]
                    try:
                        return task.param_dict[param_name]
                    except KeyError as ex:
                        return None
                df[param_name] = df.apply(get_param_row, axis=1)
                
        return df[(c for c in df.columns if not c.endswith(rsuffix))]

    def get_dataset_info_row(self, file_path):
        """Get the dataset info table row for the file path given as argument.
        """
        return self.dataset_table_df.loc[atable.indices_to_internal_loc(file_path)]

    @property
    def joined_column_to_properties(self):
        """Get the combined dictionary of :class:`atable.ColumnProperties`
        indexed by column name. This dictionary contains the dataset properties
        columns and the experiment columns.

        Note that :py:attr:`~enb.Experiment.column_to_properties` returns only the experiment
        columns.
        """
        property_dict = dict(self.dataset_info_table.column_to_properties)
        property_dict.update(self.column_to_properties)
        return property_dict

    @atable.column_function(task_name_column)
    def set_task_name(self, index, row):
        file_path, task_name = index
        row[_column_name] = self.tasks_by_name[task_name].name

    @atable.column_function(task_label_column)
    def set_task_label(self, index, row):
        file_path, task_name = index
        row[_column_name] = self.tasks_by_name[task_name].label

    @atable.column_function("param_dict")
    def set_param_dict(self, index, row):
        file_path, task_name = index
        row[_column_name] = self.tasks_by_name[task_name].param_dict
