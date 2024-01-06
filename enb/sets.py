#!/usr/bin/env python3
"""Locate, analyze, expose and catalogue dataset entries.

The FilePropertiesTable class contains the minimal information about the file
as well as basic statistical measurements.

Subclasses of this table can be created adding extra columns.

The `experiment.CompressionExperiment` class takes an instance of
`FilePropertiesTable` to know what files the experiment should be run on.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2019/09/18"

import collections
import os
import hashlib
import time

import enb
from enb import atable
from enb.atable import get_canonical_path

options = enb.config.options

# Hash algorithm used to verify file integrity
HASH_ALGORITHM = "sha256"


# pylint: disable=no-self-use

class FilePropertiesTable(atable.ATable):
    """Table describing basic file properties (see decorated methods below).
    """
    version_name = "original"
    hash_field_name = f"{HASH_ALGORITHM}"
    index_name = "file_path"
    base_dir = None
    dataset_files_extension = "raw"

    def __init__(self, csv_support_path=None, base_dir=None):
        if csv_support_path is None and options.persistence_dir is not None:
            csv_support_path = os.path.join(
                options.persistence_dir,
                f"persistence_{self.__class__.__name__}.csv")
        super().__init__(index=FilePropertiesTable.index_name,
                         csv_support_path=csv_support_path)
        self.base_dir = base_dir if base_dir is not None \
            else options.base_dataset_dir

    def get_df(self, target_indices=None, target_columns=None, fill=True,
               overwrite=None, chunk_size=None):
        # pylint: disable=too-many-arguments
        if target_indices is None:
            target_indices = enb.atable.get_all_input_files(
                ext=self.dataset_files_extension,
                base_dataset_dir=self.base_dir)
        else:
            target_indices = [enb.atable.get_canonical_path(p)
                              for p in target_indices]

        return super().get_df(target_indices=target_indices,
                              target_columns=target_columns,
                              fill=fill, overwrite=overwrite,
                              chunk_size=chunk_size)

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
        """Store the corpus name of a data sample.
        By default, it is the name of the folder in which the sample is stored.
        """
        file_path = os.path.abspath(os.path.realpath(file_path))
        if options.base_dataset_dir is not None \
                and os.path.dirname(file_path) != os.path.abspath(os.path.realpath(options.base_dataset_dir)):
            file_dir = os.path.dirname(file_path)
            if self.base_dir is not None:
                file_dir = file_dir.replace(self.base_dir, "")
            while file_dir and file_dir[0] == os.sep:
                file_dir = file_dir[1:]
        else:
            file_dir = os.path.basename(
                os.path.dirname(file_path))

        if not file_dir:
            file_dir = os.path.basename(
                os.path.dirname(file_path))

        row[_column_name] = os.path.basename(os.path.abspath(file_dir))

    @atable.column_function("size_bytes", label="File size (bytes)")
    def set_file_size(self, file_path, row):
        """Store the original file size in row.
        :param file_path: path to the file to analyze
        :param row: dictionary of previously computed values for this file_path
          (to speed up derived values).
        """
        row[_column_name] = os.path.getsize(file_path)

    @atable.column_function(hash_field_name,
                            label=f"{hash_field_name} hex digest")
    def set_hash_digest(self, file_path, row):
        """Store the hexdigest of file_path's contents, using hash_algorithm as configured.
        :param file_path: path to the file to analyze.
        :param row: dictionary of previously computed values for this file_path (to speed up derived values).
        """
        hasher = hashlib.new(HASH_ALGORITHM)
        with open(file_path, "rb") as file:
            hasher.update(file.read())
        row[_column_name] = hasher.hexdigest()


class FileVersionTable(FilePropertiesTable):
    """Table with the purpose of converting an input dataset into a
    destination folder. This is accomplished by calling the version() method
    for all input files. Subclasses may be defined so that they inherit from
    other classes and can apply more complex versioning.
    """

    def __init__(self, version_base_dir, version_name="",
                 original_properties_table=None,
                 original_base_dir=None,
                 csv_support_path=None,
                 check_generated_files=True):
        """
        :param version_base_dir: path to the versioned base directory
          (versioned directories preserve names and structure within
          the base dir)
        :param version_name: arbitrary name of this file version
        :param original_base_dir: path to the original directory
          (it must contain all indices requested later with self.get_df()).
          If None, `enb.config.options.base_dataset_dir` is used
        :param original_properties_table: instance of the file properties
          subclass to be used when reading the original data to be versioned.
          If None, a FilePropertiesTable is instanced automatically.
        :param csv_support_path: path to the file where results (of the
          versioned data) are to be long-term stored. If None, one is assigned
          by default based on options.persistence_dir.
        :param check_generated_files: if True, the table checks that each
          call to version() produces a file to output_path. Set to false to
          create arbitrarily named output files.
        """
        # pylint: disable=too-many-arguments
        FilePropertiesTable.__init__(self, csv_support_path=csv_support_path,
                                     base_dir=version_base_dir)

        self.original_base_dir = os.path.abspath(
            os.path.realpath(original_base_dir)) \
            if original_base_dir is not None else options.base_dataset_dir
        self.original_properties_table = FilePropertiesTable(
            base_dir=self.original_base_dir) \
            if original_properties_table is None else original_properties_table
        self.version_base_dir = os.path.abspath(
            os.path.realpath(version_base_dir))
        self.version_name = version_name
        self.current_run_version_times = {}
        self.check_generated_files = check_generated_files

        assert self.version_base_dir is not None
        os.makedirs(self.version_base_dir, exist_ok=True)

        # The versioning column is moved to the back so that all other
        # columns are available when versioning
        column_to_properties = collections.OrderedDict()
        for k, v in self.column_to_properties.items():
            if k != "version_time":
                column_to_properties[k] = v
        column_to_properties["version_time"] = self.column_to_properties[
            "version_time"]
        self.column_to_properties = column_to_properties

    def version(self, input_path, output_path, row):
        """Create a version of input_path and write it into output_path.

        :param input_path: path to the file to be versioned
        :param output_path: path where the version should be saved
        :param row: metainformation available using super().get_df
          for input_path

        :return: if not None, the time in seconds it took to perform the (
          forward) versioning.
        """
        raise NotImplementedError

    def get_default_target_indices(self):
        """Get the list of samples in self.original_base_dir and its
        subdirs that have extension `self.dataset_files_extension`.
        """
        return enb.atable.get_all_input_files(
            base_dataset_dir=self.original_base_dir,
            ext=self.dataset_files_extension)

    def original_to_versioned_path(self, original_path):
        """Get the path of the versioned file corresponding to original_path.
        This function will replicate the folder structure within
        self.original_base_dir.
        """
        versioned_path = os.path.abspath(original_path).replace(
            os.path.abspath(self.original_base_dir),
            os.path.abspath(self.version_base_dir))

        # If the dataset was linking to a dataset somewhere else in the
        # filesystem, its relative path in the output dir is attempted to be
        # discovered by inspecting self.original_base_dir and see if any
        # matches are found.
        if not os.path.abspath(original_path).startswith(
                os.path.abspath(self.original_base_dir)):
            parts = os.path.abspath(original_path).split(os.sep)[1:]
            for used_parts in range(1, len(parts) + 1):
                if os.path.exists(os.path.join(self.original_base_dir,
                                               *parts[-used_parts:])):
                    versioned_path = os.path.join(self.version_base_dir,
                                                  *parts[-used_parts:])
                    break
            else:
                raise Exception(
                    f"Original path {original_path} not found "
                    f"in {self.original_base_dir}")

        enb.logger.info(
            f"Transformed original path {original_path} "
            f"into versioned path {versioned_path}")

        return versioned_path

    def get_df(self, target_indices=None, fill=True, overwrite=None,
               target_columns=None):
        """Create a version of target_indices (which must all be contained in
        self.original_base_dir) into self.version_base_dir. Then return a
        pandas DataFrame containing all given indices and defined columns. If
        fill is True, missing values will be computed. If fill and overwrite
        are True, all values will be computed, regardless of whether they are
        previously present in the table.

        :param overwrite: if True, version files are written even if they exist
        :param target_indices: list of indices that are to be contained in
          the table, or None to use the list of files returned by
          enb.atable.get_all_test_files()
        :param target_columns: if not None, the list of columns that are
          considered for computation
        """
        # pylint: disable=too-many-arguments,arguments-differ
        target_indices = target_indices if target_indices is not None \
            else self.get_default_target_indices()
        overwrite = overwrite if overwrite is not None else options.force

        assert all(index == enb.atable.get_canonical_path(index) for index in
                   target_indices)

        _ = self.original_properties_table.get_df(
            target_indices=target_indices, target_columns=target_columns)

        return FilePropertiesTable.get_df(
            self,
            target_indices=target_indices,
            target_columns=target_columns, overwrite=overwrite)

    @atable.column_function("original_file_path")
    def set_original_file_path(self, file_path, row):
        """Store the path of the original path being versioned.
        """
        row[_column_name] = get_canonical_path(
            file_path.replace(self.version_base_dir, self.original_base_dir))

    @atable.column_function("version_time", label="Versioning time (s)")
    def set_version_time(self, file_path, row):
        """Run `self.version()` and store the wall version time.
        """
        time_before = time.time_ns()
        self.version(
            input_path=file_path,
            output_path=self.original_to_versioned_path(
                original_path=file_path),
            row=row)
        row[_column_name] = (time.time_ns() - time_before) / 1e9

    def column_version_name(self, file_path, row):
        """Automatically add the version name as a column
        """
        # pylint: disable=unused-argument
        return self.version_name

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
            file_dir = os.path.basename(
                os.path.dirname(os.path.abspath(os.path.realpath(file_path))))
        if not file_dir:
            file_dir = os.path.basename(
                os.path.dirname(os.path.abspath(os.path.realpath(file_path))))
        row[_column_name] = file_dir


@enb.parallel.parallel()
def parallel_version_one_path(version_fun, input_path, output_path, overwrite,
                              original_info_df, check_generated_files):
    """Run the versioning of one path.
    """
    # pylint: disable=too-many-arguments
    return version_one_path_local(version_fun=version_fun,
                                  input_path=input_path,
                                  output_path=output_path,
                                  overwrite=overwrite,
                                  original_info_df=original_info_df,
                                  check_generated_files=check_generated_files)


def version_one_path_local(version_fun, input_path, output_path, overwrite,
                           original_info_df, check_generated_files):
    """Version input_path into output_path using version_fun.

    :param version_fun: function with signature like FileVersionTable.version
    :param input_path: path of the file to be versioned
    :param output_path: path where the versioned file is to be stored
    :param overwrite: if True, the version is calculated even if output_path
      already exists
    :param original_info_df: DataFrame produced by a FilePropertiesTable
      instance that contains an entry for :meth:`atable.indices_to_internal_loc`.
    :param check_generated_files: flag indicating whether failing to produce
      output_path must raise an exception.

    :return: a tuple ``(output_path, l)``, where output_path is the selected
      otuput path and l is a list with the obtained versioning time. The list l
      shall contain options.repetitions elements. NOTE: If the subclass version
      method returns a value, that value is taken as the time measurement.
    """
    # pylint: disable=too-many-arguments
    time_measurements = []

    output_path = get_canonical_path(output_path)
    if os.path.exists(output_path) and not overwrite:
        enb.logger.debug(f"[S]kipping versioning of {input_path}->{output_path}")
        return output_path, [-1]

    enb.logger.verbose(
        f"Versioning {input_path} -> {output_path} "
        f"(overwrite={overwrite}) <{version_fun}>")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    row = original_info_df.loc[atable.indices_to_internal_loc(input_path)]
    for repetition_index in range(options.repetitions):
        try:
            time_before = time.time()
            versioning_time = version_fun(
                input_path=input_path, output_path=output_path, row=row)
            if check_generated_files and \
                    (not os.path.exists(output_path) or os.path.getsize(
                        output_path) == 0):
                raise Exception(
                    f"Function {version_fun} did not produce a "
                    f"versioned path {input_path}->{output_path}")
            versioning_time = versioning_time if versioning_time is not None \
                else time.time() - time_before
            if versioning_time < 0:
                if options.verbose:
                    print(
                        f"[W]arning: versioning_time = "
                        f"{versioning_time} < 0 for {input_path}")
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
