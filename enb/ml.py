import time
import torch
import torch.nn as nn
import numpy as np

import enb
from enb import experiment


class Model(nn.Module, experiment.ExperimentTask):
    def __init__(self, criterion=nn.CrossEntropyLoss(), param_dict=None):
        param_dict['criterion'] = criterion
        super().__init__(param_dict=param_dict)

    def test(self, test_loader):
        self.eval()
        test_loss = 0
        correct = 0
        totals = 0
        all_preds = []
        all_targets = []

        with torch.no_grad():
            for data, target in test_loader:
                data, target = data, target
                output = self.parm_dict['model'].forward(data)
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
        def __init__(self, testing_dataset_path, model, row):
            self.testing_dataset_path = testing_dataset_path
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
                self._testing_results = self.model.test(self.testing_dataset_path)
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
    def __init__(self, models):
        self.models = models
