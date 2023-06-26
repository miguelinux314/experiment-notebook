#!/usr/bin/env python3
"""Example showing the definition of a basic expeirment with `enb`.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/11/11"

import glob
import socket
import enb


class CheckPort(enb.experiment.ExperimentTask):
    """Experiment task that can perform a check based on
    the selected port.
    """

    def __init__(self, port):
        assert 0 <= port <= 65353
        super().__init__(param_dict=dict(port=port))

    def check_one_port(self, url_file_path):
        """Check whether a given port for a given url in url_file_path is open.
        Return True if and only if a socket could be open to that url:port.
        """
        with open(url_file_path, "r") as url_file:
            url = url_file.readline().strip()
        a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        location = (url, self.param_dict['port'])
        result_of_check = a_socket.connect_ex(location)
        return result_of_check == 0


class PortExperiment(enb.experiment.Experiment):
    """Example experiment that checks whether certain ports are open.
    """
    dataset_files_extension = "txt"

    def column_port_open(self, index, row):
        url_file_path, checkport_task = self.index_to_path_task(index)
        return checkport_task.check_one_port(url_file_path)


if __name__ == '__main__':
    # This is the list of inputs. Each one contains one IP in a single line.
    enb.config.options.base_dataset_dir = "./data/ips"

    # This is the list of tasks to be run
    tasks = [CheckPort(port=p) for p in [53, 22, 80, 443, 8080]]

    # Obtain the full table of results
    exp = PortExperiment(tasks=tasks)
    result_df = exp.get_df()

    # Display a list of observed open ports
    open_port_df = result_df[result_df["port_open"]]
    for url_file_path, url_df in open_port_df.groupby("file_path"):
        print(f"Found open ports in {open(url_file_path, 'r').read().strip()}:\n - ", end="")
        print("\n - ".join(str(d['port']) for d in url_df["param_dict"]))

