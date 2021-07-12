#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper for the IWT transform
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "25/05/2020"

import os

from enb.config import get_options

options = get_options(from_main=False)

from . import abstract_mhdc_transform

iwt_transform_number = 1


class IWTVersionTable(abstract_mhdc_transform.MHDCTransformTable):
    """Forward IWT version table
    """

    @property
    def transform_number(self):
        return iwt_transform_number


class InverseIWTVersionTable(abstract_mhdc_transform.InverseMHDCTransformTable):
    """Inverse IWT version table
    """

    @property
    def transform_number(self):
        return iwt_transform_number


class IWTLosslessCompressionExperiment(abstract_mhdc_transform.MDHCLosslessCompressionExperiment):
    @property
    def transform_number(self):
        return iwt_transform_number


def apply_iwt(input_dir, output_dir, forward_properties_csv=None, inverse_properties_csv=None,
              repetitions=10, run_sequential=True):
    """Apply the IWT to input_dir and save the results to output_dir.

    :param input_dir: input directory to be transformed (recursively)
    :param output_dir: path to the output transformed dir
    :param forward_properties_csv: if not None, properties of the transformed images
      are stored here (including fwd transform time)
    :param inverse_properties_csv: if not None, properties of the reconstructed images
      are stored here (including inverse transform time)
    :param repetitions: number of repetitions used to calculate execution time
      (for both forward and inverse transform)
    :param run_sequential: if True, transformations are run in sequential mode
      (as opposed to parallel) so that time measurements can be taken

    :raises AssertionError: if transformation/reconstruction is not lossless

    :return: fwd_pot_df, inv_pot_df, i.e., the dataframes obtained with get_df
      for IWTVersionTAble and InverseIWTVersionTable, respectively.
    """
    return abstract_mhdc_transform.apply_transform(
        input_dir=input_dir, output_dir=output_dir,
        forward_class=IWTVersionTable,
        inverse_class=InverseIWTVersionTable,
        forward_properties_csv=forward_properties_csv,
        inverse_properties_csv=inverse_properties_csv,
        repetitions=repetitions, run_sequential=run_sequential)


if __name__ == '__main__':
    default_input_dir = "./green_book_corpus"
    default_output_dir = "/data/research-materials/iwt_green_book"
    persistence_dir = "./persistence"
    repetition_count = 10
    if repetition_count != 10:
        print("[i]nfo repetition_count = {}".format(repetition_count))
    run_sequential = True

    apply_iwt(
        input_dir=os.path.abspath(os.path.realpath(
            options.base_dataset_dir if options.base_dataset_dir
            else default_input_dir)),
        output_dir=os.path.abspath(os.path.realpath(
            options.base_version_dataset_dir if options.base_version_dataset_dir
            else default_output_dir)),
        forward_properties_csv=os.path.join(persistence_dir, "iwt_versioned_properties.csv"),
        inverse_properties_csv=os.path.join(persistence_dir, "iiwt_versioned_properties.csv"),
        run_sequential=run_sequential,
        repetitions=repetition_count)
