#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compression experiment intended to execute all codec plugins
TODO: complete with remaining plugins.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "02/02/2021"

import sys
import os
import glob
import subprocess
import filecmp
import pandas as pd
import tempfile
import matplotlib.pyplot as plt

from enb.config import get_options
import enb.atable

options = get_options()

from plugins import plugin_jpeg
from plugins import plugin_mcalic
from plugins import plugin_ccsds122
from plugins import plugin_fapec
from plugins import plugin_flif
from plugins import plugin_fse
from plugins import plugin_lcnl
from plugins import plugin_marlin
from plugins import plugin_zip
from plugins import plugin_jpeg_xl


if __name__ == '__main__':
    all_codecs = []
    all_families = []

    jpeg_ls_family = enb.aanalysis.TaskFamily(label="JPEG-LS")
    for c in (plugin_jpeg.jpeg_codecs.JPEG_LS(max_error=0) for m in [0]):
        all_codecs.append(c)
        jpeg_ls_family.add_task(c.name, f"{c.label} PAE {c.param_dict['m']}")
    all_families.append(jpeg_ls_family)

    mcalic_family = enb.aanalysis.TaskFamily(label="M-CALIC")
    for c in (plugin_mcalic.mcalic_codecs.MCALIC_Magli(max_error=m) for m in [0]):
        all_codecs.append(c)
        mcalic_family.add_task(c.name, f"{c.label} PAE {c.param_dict['max_error']}")
    all_families.append(mcalic_family)

    ccsds122_family = enb.aanalysis.TaskFamily(label="CCSDS 122")
    for c in (plugin_ccsds122.ccsds122_codec.MHDC_IWT(),
              plugin_ccsds122.ccsds122_codec.MHDC_ID(),
              plugin_ccsds122.ccsds122_codec.MHDC_POT()):
        all_codecs.append(c)
        ccsds122_family.add_task(c.name, f"{c.label}")
    all_families.append(ccsds122_family)

    # fapec_family = enb.aanalysis.TaskFamily(label="FAPEC")
    # for c in (plugin_fapec.fapec_codec.FAPEC_LP(),
    #           plugin_fapec.fapec_codec.FAPEC_MB(),
    #           plugin_fapec.fapec_codec.FAPEC_DWT(),
    #           plugin_fapec.fapec_codec.FAPEC_HPA(),
    #           plugin_fapec.fapec_codec.FAPEC_CILLIC(),
    #           plugin_fapec.fapec_codec.FAPEC_2DDWT(),):
    #     all_codecs.append(c)
    #     fapec_family.add_task(c.name, f"{c.label}")
    # all_families.append(fapec_family)

    flif_family = enb.aanalysis.TaskFamily(label="FLIF")
    for c in (plugin_flif.flif_codec.FLIF(),):
        all_codecs.append(c)
        flif_family.add_task(c.name, f"{c.label}")
    all_families.append(flif_family)

    fse_family = enb.aanalysis.TaskFamily(label="FSE")
    for c in (plugin_fse.fse_codec.FSE(),):
        all_codecs.append(c)
        fse_family.add_task(c.name, f"{c.label}")
    all_families.append(fse_family)

    lcnl_family = enb.aanalysis.TaskFamily(label="LCNL")
    for c in (plugin_lcnl.lcnl_codecs.CCSDS_LCNL(entropy_coder_type=ec)
              for ec in (plugin_lcnl.lcnl_codecs.CCSDS_LCNL.ENTROPY_HYBRID,
                         plugin_lcnl.lcnl_codecs.CCSDS_LCNL.ENTROPY_BLOCK_ADAPTIVE,
                         plugin_lcnl.lcnl_codecs.CCSDS_LCNL.ENTROPY_SAMPLE_ADAPTIVE)):
        all_codecs.append(c)
        lcnl_family.add_task(c.name, f"{c.label}")
    all_families.append(lcnl_family)

    marlin_family = enb.aanalysis.TaskFamily(label="ImageMarlin")
    for c in (plugin_marlin.marlin_codec.ImageMarlin(),):
        all_codecs.append(c)
    marlin_family.add_task(c.name, f"{c.label}")
    all_families.append(marlin_family)

    zip_family = enb.aanalysis.TaskFamily(label="*Zip")
    for c in (plugin_zip.zip_codecs.LZ77Huffman(),
              plugin_zip.zip_codecs.BZIP2(),
              plugin_zip.zip_codecs.LZMA()):
        all_codecs.append(c)
        zip_family.add_task(c.name, f"{c.label}")
    all_families.append(zip_family)

    # jpeg_xl_family = enb.aanalysis.TaskFamily(label="JPEG-XL")
    # for c in (plugin_jpeg_xl.jpegxl_codec.JPEG_XL(),):
    #     all_codecs.append(c)
    #     jpeg_xl_family.add_task(c.name, f"{c.label}")
    # all_families.append(jpeg_xl_family)

    label_by_group_name = dict()
    for family in all_families:
        label_by_group_name.update(family.name_to_label)

    # Run experiment and produce figures
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    exp = enb.icompression.LossyCompressionExperiment(codecs=all_codecs)

    columns = ["codec_name"]
    target_dirs = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "data", "*")))
    target_dir_names = [os.path.basename(d) for d in target_dirs]
    columns.extend(target_dir_names)
    df_capabilities = pd.DataFrame(columns=columns)
    print(f"[watch] columns={columns}")

    table_codecs = all_codecs if len(sys.argv) == 1 else \
        [c for c in all_codecs if any(p.lower() in c.name.lower() for p in sys.argv[1:])]
    table_codecs = sorted(table_codecs, key=lambda c: c.label.lower())
    for codec in table_codecs:
        data_dict = dict(codec_name=codec.label)
        if options.verbose:
            print(f"Testing codec {codec.name}...")
        for d in target_dirs:
            column_name = os.path.basename(d)
            if options.verbose > 1:
                print(f"\ttesting {column_name}")
            for input_path in glob.glob(os.path.join(d, "*.raw")):
                row_info = exp.dataset_table_df.loc[
                    enb.atable.indices_to_internal_loc(input_path)]
                with tempfile.NamedTemporaryFile() as tmp_compressed, \
                        tempfile.NamedTemporaryFile() as tmp_reconstructed:
                    state = "compressing"
                    try:

                        codec.compress(original_path=input_path,
                                       compressed_path=tmp_compressed.name,
                                       original_file_info=row_info)
                        state = "decompressing"
                        codec.decompress(compressed_path=tmp_compressed.name,
                                         reconstructed_path=tmp_reconstructed.name,
                                         original_file_info=row_info)
                        if not filecmp.cmp(input_path, tmp_reconstructed.name):
                            if (isinstance(codec, enb.icompression.LosslessCodec)):
                                data_dict[column_name] = "Not lossless"
                            else:
                                data_dict[column_name] = "Lossy"
                            break
                    except Exception as ex:
                        data_dict[column_name] = "Not available"
                        if options.verbose:
                            print(f"Error {state}; {ex}")
                        break
            else:
                data_dict[column_name] = "Lossless"
        df_capabilities.loc[codec.label] = pd.Series(data_dict)
        
    print(f"[watch] df_capabilities={df_capabilities}")
    

    df_colors = df_capabilities.copy()
    df_colors["codec_name"] = "#ffffff"
    for d in target_dir_names:
        df_colors[d] = df_capabilities[d].apply(
            lambda x: "#55ff55" if x == "Lossless"
                else "#ff5555" if x == "Not lossless"
                else "#6666ff" if x == "Lossy"
                else "#fbf3b5")


    import pandas.plotting as pdpt
    plt.figure()
    fig, ax = plt.subplots(1, 1)
    ax.axis("off")

    df_capabilities.set_index("codec_name")
    table = pdpt.table(ax, df_capabilities[target_dir_names],
                       loc="center", cellColours=df_colors[target_dir_names].values, cellLoc="center")
    plt.savefig("codec_availability.pdf", bbox_inches="tight")
    plt.close()
    invocation = "convert -density 400 codec_availability.pdf -trim codec_availability.png"
    status, output = subprocess.getstatusoutput(invocation)
    if status != 0:
        raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
            status, invocation, output))
