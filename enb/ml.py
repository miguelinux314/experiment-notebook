#!/usr/bin/env python3
"""Project module for ML
"""
__author__ = "Natalia Blasco, Ester Jara, Artur Llabrés and Miguel Hernández-Cabronero"
__since__ = "2021/09/01"

import inspect
import os
import time
import torch
import torch.nn as nn
import numpy as np

import enb
import enb.atable
from enb import experiment
from enb.config import get_options
from enb.atable import indices_to_internal_loc

options = get_options()


class Model(experiment.ExperimentTask):
    def __init__(self, criterion=nn.CrossEntropyLoss(), param_dict=None):
        param_dict['criterion'] = criterion
        super().__init__(param_dict=param_dict)

    def test(self, test_loader):  # need a way to add custom data_loaders
        self.param_dict['model'].eval()
        test_loss = 0
        correct = 0
        totals = 0
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for data, target in test_loader:
                data, target = data, target
                output = self.param_dict['model'].forward(data)
                test_loss += self.param_dict['criterion'](output, target).item() * data.shape[0]  # sum up batch loss
                pred = output.argmax(dim=1, keepdim=True)  # get the index of the max log-probability
                correct += pred.eq(target.view_as(pred)).sum().item()
                totals += len(target)
                all_preds.extend(np.asarray(pred))
                all_targets.extend(np.asarray(target))

        test_loss /= len(test_loader.dataset)
        accuracy = 100. * correct / len(test_loader.dataset)

        print('\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.2f}%)\n'.format(
            test_loss, correct, len(test_loader.dataset), accuracy))

        testing_results = {'test_loss': test_loss,
                           'accuracy': accuracy,
                           'correct': correct,
                           'predictions': all_preds,
                           'targets': all_targets}

        return testing_results


class MachineLearningExperiment(experiment.Experiment):
    class RowWrapper:
        def __init__(self, testing_dataset_path, test_loader, model, row):
            self.testing_dataset_path = testing_dataset_path
            self.test_loader = test_loader
            self.model = model
            self.row = row
            self._training_results = None
            self._testing_results = None

        @property
        def testing_results(self):
            """Perform the actual testing experiment for the selected row.
            """
            if self._testing_results is None:
                time_before = time.time()
                self._testing_results = self.model.test(self.test_loader)
                wall_testing_time = time.time() - time_before

            return self._testing_results

        def __getitem__(self, item):
            return self.row[item]

        def __setitem__(self, key, value):
            self.row[key] = value

        def __delitem__(self, key):
            del self.row[key]

        def __contains__(self, item):
            return item in self.row

    def __init__(self, models,
                 test_set,
                 dataset_paths=None,
                 csv_experiment_path=None,
                 csv_dataset_path=None,
                 dataset_info_table=None,
                 overwrite_file_properties=False):
        """
        :param codecs: list of :py:class:`AbstractCodec` instances. Note that
          codecs are compatible with the interface of :py:class:`ExperimentTask`.
        :param dataset_paths: list of paths to the files to be used as input for compression.
          If it is None, this list is obtained automatically from the configured
          base dataset dir.
        :param csv_experiment_path: if not None, path to the CSV file giving persistence
          support to this experiment.
          If None, it is automatically determined within options.persistence_dir.
        :param csv_dataset_path: if not None, path to the CSV file given persistence
          support to the dataset file properties.
          If None, it is automatically determined within options.persistence_dir.
        :param dataset_info_table: if not None, it must be a ImagePropertiesTable instance or
          subclass instance that can be used to obtain dataset file metainformation,
          and/or gather it from csv_dataset_path. If None, a new ImagePropertiesTable
          instance is created and used for this purpose.
        :param overwrite_file_properties: if True, file properties are recomputed before starting
          the experiment. Useful for temporary and/or random datasets. Note that overwrite
          control for the experiment results themselves is controlled in the call
          to get_df
        """
        self.test_set = test_set
        # TODO: if no dataset object use default dataset class using the provided path
        table_class = type(dataset_info_table) if dataset_info_table is not None \
            else self.default_file_properties_table_class
        csv_dataset_path = csv_dataset_path if csv_dataset_path is not None \
            else os.path.join(options.persistence_dir, f"{table_class.__name__}_persistence.csv")
        imageinfo_table = dataset_info_table if dataset_info_table is not None \
            else table_class(csv_support_path=csv_dataset_path)

        csv_dataset_path = csv_dataset_path if csv_dataset_path is not None \
            else f"{dataset_info_table.__class__.__name__}_persistence.csv"
        # super().__init__(tasks=models,
        #                  dataset_paths=dataset_paths,
        #                  csv_experiment_path=csv_experiment_path,
        #                  csv_dataset_path=csv_dataset_path,
        #                  dataset_info_table=imageinfo_table,
        #                  overwrite_file_properties=overwrite_file_properties)

        overwrite_file_properties = overwrite_file_properties \
            if overwrite_file_properties is not None else options.force

        self.tasks = list(models)

        dataset_paths = dataset_paths if dataset_paths is not None \
            else enb.atable.get_all_input_files()

        self.dataset_paths = dataset_paths  # TODO: remove this

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

        # if options.verbose > 1:
        #     print(f"Obtaining properties of {len(dataset_paths)} files... "
        #           f"[dataset info: {type(self.dataset_info_table).__name__}]")
        # self.dataset_table_df = self.dataset_info_table.get_df(target_indices=dataset_paths,
        #                                                        overwrite=overwrite_file_properties)

        self.target_file_paths = dataset_paths

        if csv_experiment_path is None:
            csv_experiment_path = os.path.join(options.persistence_dir,
                                               f"{self.__class__.__name__}_persistence.csv")

        os.makedirs(os.path.dirname(csv_experiment_path), exist_ok=True)
        # super().__init__(csv_support_path=csv_experiment_path,
        #                  index=self.dataset_info_table.indices + [self.task_name_column])

    def get_df(self, target_indices=None, target_columns=None,
               fill=True, overwrite=None, chunk_size=None):
        print("Testing...")

        test_loader = torch.utils.data.DataLoader(self.test_set, batch_size=512, shuffle=False, num_workers=2)

        for model in self.tasks:
            row_wrapper = self.RowWrapper(testing_dataset_path=self.dataset_paths, test_loader=test_loader,
                                          model=model, row="1")
            print(row_wrapper.testing_results())

    # @property
    # def models_by_name(self):
    #     """Alias for :py:attr:`tasks_by_name`
    #     """
    #     return self.tasks_by_name

    def compute_one_row(self, index, column_fun_tuples, row, overwrite, fill):
        # Right now we are using file_path as testing_dataset_path maybe we will need to also add training_dataset_path
        file_path, model_name = index
        model = self.models_by_name[model_name]
        image_info_row = self.dataset_table_df.loc[indices_to_internal_loc(file_path)]
        row_wrapper = self.RowWrapper(file_path, model, row)
        result = super().compute_one_row(index=index, column_fun_tuples=column_fun_tuples,
                                         row=row_wrapper, overwrite=overwrite, fill=fill)

        if isinstance(result, Exception):
            return result

        print(result.__dict__)
        return row
