#!/usr/bin/env python3
"""Tools to run compression experiments
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/09/19"

import os
import collections
import itertools
import inspect
import time
import datetime

import enb.atable
import enb.sets
from enb.config import options


class ExperimentTask:
    """Identify an :py:class:`Experiment`'s task and its configuration.
    """

    def __init__(self, param_dict=None):
        """
        :param param_dict: dictionary of configuration parameters used
          for this task. By default, they are part of the task's name.
        """
        self.param_dict = dict(param_dict) if param_dict is not None else {}

    def apply(self, experiment, index, row):
        """This method is called for all combinations of input indices and tasks
        before computing any additional column.

        :param experiment: experiment invoking this method
        :param index: index being processed by the experiment. Consider
          experiment.index_to_path_task(index).
        :param row: row being currently processed by the experiment
        """

    @property
    def name(self):
        """Unique name that uniquely identifies a task and its configuration.
        It is not intended to be displayed as much as to be used as an index.
        """
        name = f"{self.__class__.__name__}"
        if self.param_dict:
            name += "__" + "_".join(
                f"{k}={v}" for k, v in sorted(self.param_dict.items()))
        return name

    @property
    def label(self):
        """Label to be displayed for the task in output reports.
        May not be strictly unique nor fully informative.
        By default, the task's name is returned.
        """
        return self.name

    def __eq__(self, other):
        try:
            # pylint: disable=unidiomatic-typecheck
            return all(v == other.param_dict[k]
                       for k, v in self.param_dict.items()) \
                and all(self.param_dict[k] == v
                        for k, v in other.param_dict.items()) \
                and type(self) == type(other)
        except (KeyError, AttributeError):
            return False

    def __hash__(self):
        return tuple(sorted(self.param_dict.items())).__hash__()

    def __repr__(self):
        return f"<{self.__class__.__name__} (" \
            + ', '.join(repr(param) + '=' + repr(value)
                        for param, value in self.param_dict.items()) \
            + ")>"


class Experiment(enb.atable.ATable):
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
    task_apply_time_column = "task_apply_time"
    default_file_properties_table_class = enb.sets.FilePropertiesTable
    no_family_label = "No family"

    def __init__(self, tasks,
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table=None,
                 overwrite_file_properties=False,
                 task_families=None):
        """
        :param tasks: an iterable of :py:class:`ExperimentTask` instances.
          Each test file is processed by all defined tasks. For each (file,
          task) combination, a row is included in the table returned by
          :py:meth:`~get_df()`.
        :param dataset_paths: list of paths to the files to be used as input.
          If it is None, this list is obtained automatically calling
          `enb.sets.get_all_test_file()`
        :param csv_experiment_path: if not None, path to the CSV file giving
          persistence support to this experiment. If None, it is automatically
          determined within options.persistence_dir.
        :param csv_dataset_path: if not None, path to the CSV file given
          persistence support to the dataset file properties. If None,
          it is automatically determined within options.persistence_dir.
        :param dataset_info_table: if not None, it must be a
          enb.sets.FilePropertiesTable instance or subclass instance that can
          be used to obtain dataset file metainformation, and/or gather it from
          csv_dataset_path. If None, a new enb.sets.FilePropertiesTable
          instance is created and used for this purpose. This parameter can
          also be a class (instead of an instance). In this case, it the
          initializer is asumed to accept a csv_support_path argument and be
          compatible with the enb.sets.FilePropertiesTable interface.
        :param overwrite_file_properties: if True, file properties are
          necessarily computed before starting the experiment. This can be
          useful for temporary and/or random datasets. If False,
          file properties are loaded from the persistent storage when
          available. Note that this parameter does not affect whether
          experiment results are retrieved from persistent storage if
          available. This is controlled via the parameters passed to get_df()
        :param task_families: if not None, it must be a list of TaskFamily
          instances. It is used to set the "family_label" column for each row.
          If the codec is not found within the families, a default label is set
          indicating so.
        """
        # pylint: disable=too-many-arguments
        overwrite_file_properties = overwrite_file_properties \
            if overwrite_file_properties is not None else options.force

        self.tasks = list(tasks)
        self.tasks_by_name = collections.OrderedDict(
            {str(task.name): task for task in self.tasks})
        self.task_families = task_families
        self.task_name_to_family_label = {}
        try:
            for task_family in task_families:
                for task_name in task_family.task_names:
                    if task_name in self.task_name_to_family_label:
                        raise ValueError(
                            f"Found task_name {repr(task_name)} "
                            f"in family {task_family.label} "
                            "that was already present in family "
                            f"{self.task_name_to_family_label[task_name]}. "
                            "No duplicates are allowed.")
                    assert task_name not in self.task_name_to_family_label, \
                        self.task_name_to_family_label[task_name]
                    self.task_name_to_family_label[
                        task_name] = task_family.label
        except TypeError:
            pass

        if dataset_paths is not None:
            dataset_paths = [enb.atable.get_canonical_path(p) for p in
                             dataset_paths]
        else:
            dataset_paths = enb.atable.get_all_input_files(
                ext=self.dataset_files_extension)

        if csv_dataset_path is None:
            csv_dataset_path = os.path.join(
                options.persistence_dir,
                f"{self.__class__.__name__}_dataset_persistence.csv")
        os.makedirs(os.path.dirname(csv_dataset_path), exist_ok=True)

        if dataset_info_table is None:
            dataset_info_table = self.default_file_properties_table_class(
                csv_support_path=csv_dataset_path)
        else:
            if inspect.isclass(dataset_info_table):
                dataset_info_table = dataset_info_table(
                    csv_support_path=csv_dataset_path)
        self.dataset_info_table = dataset_info_table

        self.dataset_info_table.ignored_columns = \
            set(self.dataset_info_table.ignored_columns + self.ignored_columns)

        assert len(self.dataset_info_table.indices) == 1, \
            "dataset_info_table is expected to have a single index"

        enb.logger.debug(f"[{self.__class__.__name__}] ", end="")
        enb.logger.info(f"Obtaining dataset properties table for {self.__class__.__name__}...")
        self.dataset_table_df = self.dataset_info_table.get_df(
            target_indices=dataset_paths,
            overwrite=overwrite_file_properties,
            fill=True)

        self.target_file_paths = dataset_paths

        if csv_experiment_path is None:
            csv_experiment_path = os.path.join(
                options.persistence_dir,
                f"{self.__class__.__name__}_persistence.csv")

        os.makedirs(os.path.dirname(csv_experiment_path), exist_ok=True)

        super().__init__(csv_support_path=csv_experiment_path,
                         index=self.dataset_info_table.indices + [
                             self.task_name_column])

    def get_df(self, target_indices=None, target_columns=None,
               fill=True, overwrite=None, chunk_size=None):
        """Get a DataFrame with the results of the experiment. The produced
        DataFrame contains the columns from the dataset info table (but they
        are not stored in the experiment's persistence file).

        :param target_indices: list of file paths to be processed. If None,
          self.target_file_paths is used instead.
        :param chunk_size: if not None, a positive integer that determines
          the number of table rows that are processed before made persistent.
        :param overwrite: if not None, a flag determining whether existing
          values should be calculated again. If none, options
        """
        # pylint: disable=too-many-arguments,too-many-locals
        target_indices = self.target_file_paths \
            if target_indices is None else target_indices
        overwrite = overwrite if overwrite is not None else options.force

        if not self.tasks:
            raise ValueError(
                f"No tasks were defined for {self.__class__.__name__}.")

        target_task_names = [str(t.name) for t in self.tasks]
        target_indices = tuple(itertools.product(
            sorted(set(target_indices)), sorted(set(target_task_names))))

        enb.logger.info(f"Computing {self.__class__.__name__} ({len(self.column_to_properties)} columns)...")
        enb.logger.debug(f"({len(self.tasks)} tasks, {len(target_indices)} indices)")

        chunk_size = chunk_size if chunk_size is not None \
            else options.chunk_size
        chunk_size = chunk_size if chunk_size is not None \
            else len(target_indices)

        chunks = [target_indices[i:i + chunk_size]
                  for i in range(0, len(target_indices), chunk_size)]

        if enb.progress.is_progress_enabled():
            progress_tracker = enb.progress.ProgressTracker(atable=self,
                                                            row_count=len(target_indices),
                                                            chunk_size=chunk_size).__enter__()
        else:
            progress_tracker = False
        try:
            for chunk_index, chunk in enumerate(chunks):
                with enb.logger.debug_context(
                        f"Computing experiment chunk "
                        f"{chunk_index}/{len(chunks) - 1} "
                        f"({100 * chunk_index / len(chunks):.2f}%-"
                        f"{min(100, 100 * (chunk_index + 1) / len(chunks)):.2f}%) "
                        f"@ {datetime.datetime.now()}",
                        sep="...\n",
                        msg_after=f"Completed {self.__class__.__name__} "
                                  f"chunk #{chunk_index}/{len(chunks) - 1}"):
                    try:
                        old_tasks = list(self.tasks)
                        old_tasks_by_name = dict(self.tasks_by_name)
                        task_names = list(set(task_name for _, task_name in chunk))
                        self.tasks = [old_tasks_by_name[name] for name in task_names]
                        self.tasks_by_name = {name: old_tasks_by_name[name]
                                              for name in task_names}
                        _ = super().get_df(target_indices=chunk,
                                           fill=fill,
                                           overwrite=overwrite,
                                           chunk_size=-1,
                                           progress_tracker=progress_tracker)
                    finally:
                        self.tasks = old_tasks
                        self.tasks_by_name = old_tasks_by_name

                if progress_tracker:
                    progress_tracker.complete_chunk()
        finally:
            if progress_tracker:
                progress_tracker.__exit__(None, None, None)

        # Get all dfs (single chunk)
        df = super().get_df(target_indices=target_indices, fill=fill,
                            overwrite=overwrite,
                            chunk_size=len(target_indices),
                            progress_tracker=False)

        # Add dataset columns
        with enb.logger.debug_context(
                "Merging dataset and experiment results"):
            rsuffix = "__redundant__index"
            df = df.join(
                self.dataset_table_df.set_index(self.dataset_info_table.index),
                on=self.dataset_info_table.index, rsuffix=rsuffix)
            redundant_columns = [c.replace(rsuffix, "")
                                 for c in df.columns
                                 if c.endswith(rsuffix)
                                 and not c.startswith("row_created")
                                 and not c.startswith("row_updated")]
            if redundant_columns:
                enb.logger.warn(
                    f"Found redundant dataset/experiment column(s): "
                    f"{', '.join(redundant_columns)}.")

        enb.logger.info("")

        return df[(c for c in df.columns if not c.endswith(rsuffix))]

    def index_to_path_task(self, index):
        """Given an Experiment's row index, return `(path, task)`, where
        `path` is the canonical path of the row's dataset element,
        and `task` is the task instance corresponding to that row.
        """
        return index[0], self.tasks_by_name[index[1]]

    def get_dataset_info_row(self, file_path):
        """Get the dataset info table row for the file path given as argument.
        """
        return self.get_dataset_df().loc[
            enb.atable.indices_to_internal_loc(file_path)]

    def get_dataset_df(self):
        """Get the DataFrame of the employed dataset.
        """
        return self.dataset_table_df

    @property
    def joined_column_to_properties(self):
        """Get the combined dictionary of :class:`enb.atable.ColumnProperties`
        indexed by column name. This dictionary contains the dataset
        properties columns and the experiment columns.

        Note that :py:attr:`~enb.Experiment.column_to_properties` returns
        only the experiment columns.
        """
        property_dict = dict(self.dataset_info_table.column_to_properties)
        property_dict.update(self.column_to_properties)
        return property_dict

    @enb.atable.column_function(task_apply_time_column)
    def set_task_apply_time(self, index, row):
        """Run the `task.apply()` method and store its process time.
        """
        _, task = self.index_to_path_task(index)
        time_before = time.process_time()
        task.apply(self, index, row)
        row[_column_name] = max(0.0, time.process_time() - time_before)

    @enb.atable.column_function(task_name_column)
    def set_task_name(self, index, row):
        """Set the name of the task for this row.
        """
        _, task = self.index_to_path_task(index)
        row[_column_name] = task.name

    @enb.atable.column_function(task_label_column)
    def set_task_label(self, index, row):
        """Set the label of the task for this row.
        """
        _, task = self.index_to_path_task(index)
        row[_column_name] = task.label

    @enb.atable.column_function(
        enb.atable.ColumnProperties("param_dict", has_dict_values=True))
    def set_param_dict(self, index, row):
        """Store the task's param dict for easy reference and access to the
        param values.
        """
        _, task = self.index_to_path_task(index)
        row[_column_name] = task.param_dict

    @enb.atable.column_function("family_label")
    def set_family_label(self, index, row):
        """Set the label of the family to which this row's task belong,
        or set it to self.no_family_label
        """
        _, task = self.index_to_path_task(index)
        try:
            row[_column_name] = self.task_name_to_family_label[task.name]
        except KeyError:
            row[_column_name] = self.no_family_label


class TaskFamily:
    """Describe a sorted list of task names that identify a family of related
    results within a DataFrame. Typically, this family will be constructed
    using task workers (e.g., :class:`enb.icompression.AbstractCodec`
    instances) that share all configuration values except for a parameter.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, label, task_names=None, name_to_label=None):
        """
        :param label: Printable name that identifies the family
        :param task_names: if not None, it must be a list of task names (
          strings) that are expected to be found in an ATable's DataFrame when
          analyzing it.
        :param name_to_label: if not None, it must be a dictionary indexed by
          task name that contains a displayable version of it.
        """
        self.label = label
        self.task_names = task_names if task_names is not None else []
        self.name_to_label = name_to_label if name_to_label is not None else {}

    def add_task(self, task_name, task_label=None):
        """
        Add a new task name to the family (it becomes the last element in
        self.task_names)

        :param task_name: A new not previously included in the Family
        """
        # Any ExperimentTask-like object can also be passed, and its name is
        # automatically extracted
        try:
            task_name = task_name.name
        except (TypeError, AttributeError):
            pass

        assert task_name not in self.task_names
        self.task_names.append(task_name)
        if task_label:
            self.name_to_label[task_name] = task_label
