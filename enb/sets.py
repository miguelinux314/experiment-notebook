#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate, analyze, expose and catalogue dataset entries.

The FilePropertiesTable class contains the minimal information about the file
as well as basic statistical measurements.

Subclasses of this table can be created adding extra columns.

The experiment.CompressionExperiment class takes an instance of FilePropertiesTable
to know what files the experiment should be run on.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "18/09/2019"

import os
import glob
import hashlib
import ray
import time

import enb
from enb import atable
from enb import config

options = enb.config.options

# -------------------------- Begin configurable part

# Hash algorithm used to verify file integrity
hash_algorithm = "sha256"


# -------------------------- End configurable part

def get_all_test_files(ext="raw", base_dataset_dir=None):
    """Get a list of all set files contained in the data dir.

    :param ext: if not None, only files with that extension (without dot)
      are returned by this method.
    :param base_dataset_dir: if not None, the dir where test files are searched
      for recursively. If None, options.base_dataset_dir is used instead.
    """
    base_dataset_dir = base_dataset_dir if base_dataset_dir is not None else options.base_dataset_dir
    assert os.path.isdir(base_dataset_dir), \
        f"Nonexistent dataset dir {base_dataset_dir}"
    sorted_path_list = sorted(
        (get_canonical_path(p) for p in glob.glob(
            os.path.join(base_dataset_dir, "**", f"*.{ext}" if ext else "*"),
            recursive=True)
         if os.path.isfile(p)),
        # key=lambda p: os.path.getsize(p))
        key=lambda p: get_canonical_path(p).lower())
    return sorted_path_list if not options.quick else sorted_path_list[:options.quick]


def get_canonical_path(file_path):
    """:return: the canonical path to be stored in the database.
    """
    file_path = os.path.abspath(os.path.realpath(file_path))
    return file_path


class UnkownPropertiesException(Exception):
    pass


class VersioningFailedException(Exception):
    pass


class FilePropertiesTable(atable.ATable):
    """Table describing basic file properties (see decorated methods below).
    """
    version_name = "original"
    hash_field_name = f"{hash_algorithm}"
    index_name = "file_path"
    base_dir = None

    def __init__(self, csv_support_path=None, base_dir=None):
        super().__init__(index=FilePropertiesTable.index_name, csv_support_path=csv_support_path)
        self.base_dir = base_dir if base_dir is not None else options.base_dataset_dir

    def get_relative_path(self, file_path):
        """Get the relative path. Overwritten to handle the versioned path.
        """
        file_path = os.path.abspath(file_path)
        if self.base_dir is not None:
            file_path = file_path.replace(os.path.abspath(self.base_dir), "")
        assert file_path[0] == "/"
        file_path = file_path[1:]
        return file_path

    @atable.column_function("corpus", label="Corpus name")
    def set_corpus(self, file_path, row):
        file_path = os.path.abspath(os.path.realpath(file_path))
        if options.base_dataset_dir is not None:
            file_dir = os.path.dirname(file_path)
            if self.base_dir is not None:
                file_dir = file_dir.replace(self.base_dir, "")
            while file_dir and file_dir[0] == os.sep:
                file_dir = file_dir[1:]
        else:
            file_dir = os.path.basename(os.path.dirname(os.path.abspath(os.path.realpath(file_path))))
        if not file_dir:
            file_dir = os.path.basename(os.path.dirname(os.path.abspath(os.path.realpath(file_path))))
        row[_column_name] = os.path.basename(os.path.abspath(file_dir))

    @atable.column_function("size_bytes", label="File size (bytes)")
    def set_file_size(self, file_path, row):
        """Store the original file size in row
        :param file_path: path to the file to analyze
        :param row: dictionary of previously computed values for this file_path (to speed up derived values)
        """
        row[_column_name] = os.path.getsize(file_path)

    @atable.column_function(hash_field_name, label=f"{hash_field_name} hex digest")
    def set_hash_digest(self, file_path, row):
        """Store the hexdigest of file_path's contents, using hash_algorithm as configured.
        :param file_path: path to the file to analyze
        :param row: dictionary of previously computed values for this file_path (to speed up derived values)
        """
        hasher = hashlib.new(hash_algorithm)
        with open(file_path, "rb") as f:
            hasher.update(f.read())
        row[_column_name] = hasher.hexdigest()


class FileVersionTable(FilePropertiesTable):
    """Table to gather FilePropertiesTable information from a
    version of the original files.

    IMPORTANT: FileVersionTable is intended to be defined as parent class
    _before_ the table class to be versioned, e.g.:

    ::
          class MyVersion(FileVersionTable, FilePropertiesTable):
            pass
    """

    def __init__(self, original_base_dir, version_base_dir,
                 original_properties_table, version_name,
                 csv_support_path=None):
        """
        :param original_base_dir: path to the original directory
          (it must contain all indices requested later with self.get_df())
        :param version_base_dir: path to the versioned base directory
          (versioned directories preserve names and structure within
          the base dir)
        :param version_name: name of this file version
        :param original_properties_table: instance of the file properties table (or subclass)
          to be used.
        :param csv_support_path: path to the file where results (of the versioned data) are to be
          long-term stored
        """
        super().__init__(csv_support_path=csv_support_path, base_dir=version_base_dir)
        self.original_base_dir = os.path.abspath(os.path.realpath(original_base_dir))
        self.original_properties_table = original_properties_table
        self.version_base_dir = os.path.abspath(os.path.realpath(version_base_dir))
        self.version_name = version_name
        self.current_run_version_times = {}

    def version(self, input_path, output_path, row):
        """Create a version of input_path and write it into output_path.

        :param input_path: path to the file to be versioned
        :param output_path: path where the version should be saved
        :param row: metainformation available using super().get_df
          for input_path

        :return: if not None, the time in seconds it took to perform the (forward) versioning.
        """
        raise NotImplementedError()

    def get_df(self, target_indices=None, fill=True, overwrite=False,
               parallel_versioning=True, parallel_row_processing=True,
               target_columns=None):
        """Create a version of target_indices (which must all be contained
        in self.original_base_dir) into self.version_base_dir.
        Then return a pandas DataFrame containing all given indices and defined columns.
        If fill is True, missing values will be computed.
        If fill and overwrite are True, all values will be computed, regardless of
        whether they are previously present in the table.

        :param overwrite: if True, version files are written even if they exist
        :param target_indices: list of indices that are to be contained in the table,
            or None to use the list of files returned by sets.get_all_test_files()
        :param parallel_versioning: if True, files are versioned in parallel if needed
        :param parallel_row_processing: if True, file properties are gathered in parallel
        :param target_columns: if not None, the list of columns that are considered for computation
        """
        target_indices = target_indices if target_indices is not None else get_all_test_files()
        assert all(index == get_canonical_path(index) for index in target_indices)
        original_df = self.original_properties_table.get_df(
            target_indices=target_indices,
            target_columns=target_columns)

        base_path = os.path.abspath(self.original_base_dir)
        version_path = os.path.abspath(self.version_base_dir)
        target_indices = [get_canonical_path(index)
                          for index in target_indices]
        version_indices = [index.replace(base_path, version_path)
                           for index in target_indices]

        if parallel_versioning:
            version_fun_id = ray.put(self.version)
            overwrite_id = ray.put(overwrite)
            original_df_id = ray.put(original_df)
            options_id = ray.put(options)
            versioning_result_ids = []
            for original_path, version_path in zip(target_indices, version_indices):
                input_path_id = ray.put(original_path)
                output_path_id = ray.put(version_path)
                versioning_result_ids.append(ray_version_one_path.remote(
                    version_fun=version_fun_id, input_path=input_path_id,
                    output_path=output_path_id, overwrite=overwrite_id,
                    original_info_df=original_df_id, options=options_id))
            for output_file_path, time_list in ray.get(versioning_result_ids):
                self.current_run_version_times[output_file_path] = time_list
        else:
            for original_path, version_path in zip(target_indices, version_indices):
                reported_index, self.current_run_version_times[version_path] = \
                    version_one_path_local(
                        version_fun=self.version, input_path=original_path,
                        output_path=version_path, overwrite=overwrite,
                        original_info_df=original_df,
                        options=options)
                assert reported_index == version_path, (reported_index, version_path)

        # Get the parent classes that define get_df methods different from this
        base_classes = self.__class__.__bases__
        previous_base_classes = []
        while True:
            filtered_classes = []
            for b in base_classes:
                if b is FileVersionTable:
                    continue
                try:
                    if b.get_df == FileVersionTable.get_df:
                        filtered_classes.extend(b.__bases__)
                    else:
                        filtered_classes.append(b)
                except AttributeError:
                    pass
            if filtered_classes == previous_base_classes:
                break
            previous_base_classes = filtered_classes
            base_classes = filtered_classes
        filtered_type = type(f"filtered_{self.__class__.__name__}", tuple(base_classes), {})

        return filtered_type.get_df(
            self, target_indices=version_indices, parallel_row_processing=parallel_row_processing,
            target_columns=target_columns, overwrite=overwrite)

    @atable.column_function("original_file_path")
    def set_original_file_path(self, file_path, row):
        row[_column_name] = get_canonical_path(file_path.replace(self.version_base_dir, self.original_base_dir))

    @atable.column_function("version_time", label="Versioning time (s)")
    def set_version_time(self, file_path, row):
        version_time_list = self.current_run_version_times[file_path]

        if any(t < 0 for t in version_time_list):
            raise atable.CorruptedTableError("A negative versioning time measurement was found "
                                             f"for {file_path}. Most likely, the transformed version "
                                             f"already existed, the table did not contain {_column_name}, "
                                             f"and options.force(={options.force}) is not set to True")

        if not version_time_list:
            raise atable.CorruptedTableError(f"{_column_name} was not set for {file_path}, "
                                             f"but it was not versioned in this run.")
        row[_column_name] = sum(version_time_list) / len(version_time_list)

    @atable.column_function("version_time_repetitions", label="Repetitions for obtaining versioning time")
    def set_version_repetitions(self, file_path, row):
        version_time_list = self.current_run_version_times[file_path]
        if not version_time_list:
            raise atable.CorruptedTableError(f"{_column_name} was not set for {file_path}, "
                                             f"but it was not versioned in this run.")
        row[_column_name] = len(version_time_list)

    @atable.redefines_column
    def set_corpus(self, file_path, row):
        file_path = os.path.abspath(os.path.realpath(file_path))
        if options.base_dataset_dir is not None:
            file_dir = os.path.dirname(file_path)
            base_dir = os.path.abspath(os.path.realpath(self.version_base_dir))
            file_dir = file_dir.replace(base_dir, "")
            while file_dir and file_dir[0] == os.sep:
                file_dir = file_dir[1:]
        else:
            file_dir = os.path.basename(os.path.dirname(os.path.abspath(os.path.realpath(file_path))))
        if not file_dir:
            file_dir = os.path.basename(os.path.dirname(os.path.abspath(os.path.realpath(file_path))))
        row[_column_name] = file_dir


@ray.remote
@config.propagates_options
def ray_version_one_path(version_fun, input_path, output_path, overwrite, original_info_df, options):
    """Run the versioning of one path.
    """
    return version_one_path_local(version_fun=version_fun, input_path=input_path, output_path=output_path,
                                  overwrite=overwrite, original_info_df=original_info_df, options=options)


def version_one_path_local(version_fun, input_path, output_path, overwrite, original_info_df, options):
    """Version input_path into output_path using version_fun.
    
    :return: a tuple ``(output_path, l)``, where output_path is the selected otuput path and
      l is a list with the obtained versioning time. The list l shall contain options.repetitions elements.
      NOTE: If the subclass version method returns a value, that value is taken
      as the time measurement.
    
    :param version_fun: function with signature like FileVersionTable.version
    :param input_path: path of the file to be versioned
    :param output_path: path where the versioned file is to be stored
    :param overwrite: if True, the version is calculated even if output_path already exists
    :param options: additional runtime options
    :param original_info_df: DataFrame produced by a FilePropertiesTable instance that contains
      an entry for :meth:`atable.indices_to_internal_loc`.
    """
    time_measurements = []

    output_path = get_canonical_path(output_path)
    if os.path.exists(output_path) and not overwrite:
        if options.verbose > 2:
            print(f"[S]kipping versioning of {input_path}->{output_path}")
        return output_path, [-1]

    if options.verbose > 1:
        print(f"[V]ersioning {input_path} -> {output_path} (overwrite={overwrite}) <{version_fun}>")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    row = original_info_df.loc[atable.indices_to_internal_loc(input_path)]
    for repetition_index in range(options.repetitions):
        try:
            time_before = time.time()
            versioning_time = version_fun(
                input_path=input_path, output_path=output_path, row=row)
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise VersioningFailedException(
                    f"Function {version_fun} did not produce a versioned path {input_path}->{output_path}")
            versioning_time = versioning_time if versioning_time is not None \
                else time.time() - time_before
            if versioning_time < 0:
                if options.verbose:
                    print(f"[W]arning: versioning_time = {versioning_time} < 0 for "
                          f"{self.__class__.__name__} on {input_path}")
                versioning_time = 0
            time_measurements.append(versioning_time)
            if repetition_index < options.repetitions - 1:
                os.remove(output_path)
        except Exception as ex:
            try:
                os.remove(output_path)
            except FileNotFoundError:
                pass
            raise ex

    return output_path, time_measurements
