#!/usr/bin/env python3
"""Example that approximates the value of pi using the montecarlo method.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/12/27"

import platform

import numpy as np
import enb


class MontecarloPiExperiment(enb.experiment.Experiment):
    def column_sample_size(self, index, row):
        """Keep track of how many samples were employed for this approximation.
        """
        task = self.index_to_path_task(index)[1]
        return task.param_dict["sample_size"]

    def column_computed_on_ip(self, index, row):
        """Register the node that computed this particular sample.
        """
        return enb.misc.get_node_ip()

    def column_estimated_pi_value(self, index, row):
        """Make a Montecarlo approximation of pi.
        """
        random_values = -1 + 2 * np.random.random((row["sample_size"], 2))
        return 4 * np.count_nonzero(
            random_values[:, 0] * random_values[:, 0] + random_values[:, 1] * random_values[:, 1]
            <= 1) / row["sample_size"]


if __name__ == '__main__':
    sample_size = 10000000
    sample_count = 128

    if enb.config.options.ssh_cluster_csv_path is None:
        if enb.parallel_ray.is_ray_enabled():
            print("enb.config.options.ssh_cluster_csv_path is not set. "
                  "You can do so with --ssh_cluster_csv_path=enb_cluster.csv"
                  "or creating an '*.ini' file with\n"
                  "[enb.config.options]\nssh_cluster_csv_path = enb_cluster.csv\n"
                  "Please see https://miguelinux314.github.io/experiment-notebook/cluster_setup.html "
                  "for more details.")
    else:
        print(f"Using cluster configuration file at {enb.config.options.ssh_cluster_csv_path}")

    exp = MontecarloPiExperiment(
        tasks=[enb.experiment.ExperimentTask(dict(label=i, sample_size=sample_size))
               for i in range(sample_count)])
    df = exp.get_df()

    total_samples = df["sample_size"].sum()
    estimated_pi_value = (df["estimated_pi_value"] * df["sample_size"]).sum() / total_samples
    different_nodes = len(df["computed_on_ip"].unique())
    print(f"Approximated pi ~ {estimated_pi_value} using {total_samples} total samples on {different_nodes} nodes.")