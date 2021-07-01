#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compression experiment intended to execute all codec plugins

TODO: complete with remaining plugins.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "02/02/2021"

import sys
import re
import os
import glob
import subprocess
import filecmp
import pandas as pd
import tempfile
import matplotlib.pyplot as plt
import pandas.plotting as pdpt
import collections
import math

from enb.config import get_options
import enb.atable

options = get_options()

from plugins import plugin_jpeg, plugin_flif
from plugins import plugin_mcalic
from plugins import plugin_ccsds122
# from plugins import plugin_fapec
from plugins import plugin_fse_huffman
from plugins import plugin_lcnl
from plugins import plugin_marlin
from plugins import plugin_zip
from plugins import plugin_jpeg_xl
from plugins import plugin_hevc
from plugins import plugin_kakadu
from plugins import plugin_vvc
from plugins import plugin_fpack
from plugins import plugin_zstandard
from plugins import plugin_fpzip
from plugins import plugin_zfp
from plugins import plugin_fpc
from plugins import plugin_spdp
from plugins import plugin_lz4

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
    for c in [
            plugin_ccsds122.ccsds122_codec.MHDC_IWT(),
            # plugin_ccsds122.ccsds122_codec.MHDC_ID(),
            # plugin_ccsds122.ccsds122_codec.MHDC_POT()
    ]:
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
    for c in [plugin_flif.flif_codec.FLIF()]:
        all_codecs.append(c)
        flif_family.add_task(c.name, f"{c.label}")
    all_families.append(flif_family)

    fse_family = enb.aanalysis.TaskFamily(label="FSE")
    for c in [plugin_fse_huffman.fse_codec.FSE()]:
        all_codecs.append(c)
        fse_family.add_task(c.name, f"{c.label}")
    all_families.append(fse_family)

    huffman_family = enb.aanalysis.TaskFamily(label="Huffman")
    for c in [plugin_fse_huffman.huffman_codec.Huffman()]:
        all_codecs.append(c)
        huffman_family.add_task(c.name, f"{c.label}")
    all_families.append(huffman_family)

    lcnl_family = enb.aanalysis.TaskFamily(label="LCNL")
    # plugin_lcnl.lcnl_codecs.CCSDS_LCNL.ENTROPY_BLOCK_ADAPTIVE,
    # plugin_lcnl.lcnl_codecs.CCSDS_LCNL.ENTROPY_SAMPLE_ADAPTIVE
    for c in [plugin_lcnl.lcnl_codecs.CCSDS_LCNL(entropy_coder_type=plugin_lcnl.lcnl_codecs.CCSDS_LCNL.ENTROPY_HYBRID)]:
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
              plugin_zip.zip_codecs.LZMA(),):
        all_codecs.append(c)
        zip_family.add_task(c.name, f"{c.label}")
    all_families.append(zip_family)

    jpeg_xl_family = enb.aanalysis.TaskFamily(label="JPEG-XL")
    for c in (plugin_jpeg_xl.jpegxl_codec.JPEG_XL(quality_0_to_100=100, compression_level=7) for m in [0]):
        all_codecs.append(c)
        jpeg_xl_family.add_task(c.name,
                                f"{c.label} {c.param_dict['quality_0_to_100']} {c.param_dict['compression_level']}")
    all_families.append(jpeg_xl_family)

    ht = False
    lossless = True
    # for ht in [True, False]:
    #     for lossless in [True, False]:
    kakadu_family = enb.aanalysis.TaskFamily(label=f"Kakadu {'HT' if ht else ''}"
                                                   + f"{'lossless' if lossless else 'lossy'}")
    if lossless:
        c = plugin_kakadu.kakadu_codec.Kakadu(ht=ht, lossless=lossless)
    else:
        c = plugin_kakadu.kakadu_codec.Kakadu(ht=ht, lossless=lossless, quality_factor=75)
    all_codecs.append(c)
    kakadu_family.add_task(c.name + f"{' HT' if c.param_dict['ht'] else ''}"
                           + f"{'lossless' if lossless else 'lossy'}",
                           f"{c.label} HT {c.param_dict['ht']} Quality Factor {c.param_dict['quality_factor']}")
    all_families.append(kakadu_family)

    for label, c in [("HEVC lossless", plugin_hevc.hevc_codec.HEVC_lossless()),
                     # ("HEVC lossy QP25", plugin_hevc.hevc_codec.HEVC_lossy(qp=25)),
                     # ("HEVC lossy 0.25bps", plugin_hevc.hevc_codec.HEVC_lossy(bit_rate=0.25))
                     ]:
        family = enb.aanalysis.TaskFamily(label=label)
        all_codecs.append(c)
        family.add_task(c.name, c.label)
        all_families.append(family)

    for label, c in [
                     ("VVC lossless", plugin_vvc.vvc_codec.VVC_lossless()),
                     # ("VVC lossy QP25", plugin_vvc.vvc_codec.VVC_lossy(qp=25)),
                     # ("VVC lossy 0.25bps", plugin_vvc.vvc_codec.VVC_lossy(bit_rate=0.25)),
                     ]:
        family = enb.aanalysis.TaskFamily(label=label)
        all_codecs.append(c)
        family.add_task(c.name, c.label)
        all_families.append(family)
        
    fpack_family = enb.aanalysis.TaskFamily(label="Fpack")
    for c in [plugin_fpack.fpack_codec.Fpack()]:
        all_codecs.append(c)
        fpack_family.add_task(c.name, f"{c.label}")
    all_families.append(fpack_family)
    
    zstandard_family = enb.aanalysis.TaskFamily(label="Zstandard")
    for c in [plugin_zstandard.zstd_codec.Zstandard()]:
        all_codecs.append(c)
        zstandard_family.add_task(c.name, f"{c.label}")
    all_families.append(zstandard_family)
    
    fpzip_family = enb.aanalysis.TaskFamily(label="Fpzip")
    for c in [plugin_fpzip.fpzip_codec.Fpzip()]:
        all_codecs.append(c)
        fpzip_family.add_task(c.name, f"{c.label}")
    all_families.append(fpzip_family)
      
    zfp_family = enb.aanalysis.TaskFamily(label="Zfp")
    for c in [plugin_zfp.zfp_codec.Zfp()]:
        all_codecs.append(c)
        zfp_family.add_task(c.name, f"{c.label}")
    all_families.append(zfp_family)
    
    fpc_family = enb.aanalysis.TaskFamily(label="FPC")
    for c in (plugin_fpc.fpc_codec.Fpc(),):
        all_codecs.append(c)
        fpc_family.add_task(c.name, f"{c.label}")
    all_families.append(fpc_family)
    
    spdp_family = enb.aanalysis.TaskFamily(label="SPDP")
    for c in (plugin_spdp.spdp_codec.Spdp(),):
        all_codecs.append(c)
        spdp_family.add_task(c.name, f"{c.label}")
    all_families.append(spdp_family)
     
    lz4_family = enb.aanalysis.TaskFamily(label="LZ4")
    for c in (plugin_lz4.lz4_codec.Lz4(),):
        all_codecs.append(c)
        lz4_family.add_task(c.name, f"{c.label}")
    all_families.append(lz4_family)
   
    label_by_group_name = dict()
    for family in all_families:
        label_by_group_name.update(family.name_to_label)

    # Run experiment and produce figures
    options.base_dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    exp = enb.icompression.LossyCompressionExperiment(codecs=all_codecs)

    target_dirs = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "data", "*")))

    target_dir_names = [os.path.basename(d) for d in target_dirs]

    columns = ["codec_name"]
    columns.extend(target_dir_names)
    columns.extend(["min_lossless_bitdepth", "max_lossless_bitdepth"])
    df_capabilities = pd.DataFrame(columns=columns)

    args = [v for v in sys.argv[1:] if not v.startswith("-")]
    if args:
        table_codecs = [c for c in all_codecs if any(a.lower() in c.name.lower() for a in args)]
    else:
        table_codecs = all_codecs
    table_codecs = sorted(table_codecs, key=lambda c: c.label.lower())
    min_lossless_bitdepth_by_name = collections.defaultdict(lambda: float("inf"))
    max_lossless_bitdepth_by_name = collections.defaultdict(lambda: float("-inf"))
    min_compression_ratio_by_name = collections.defaultdict(lambda: float("inf"))
    max_compression_ratio_by_name = collections.defaultdict(lambda: float("-inf"))

    for c in table_codecs:
        data_dict = dict(codec_name=c.label)
        if options.verbose:
            print(f"Testing codec {c.name}...")
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
                        c.compress(original_path=input_path,
                                   compressed_path=tmp_compressed.name,
                                   original_file_info=row_info)
                        state = "decompressing"
                        c.decompress(compressed_path=tmp_compressed.name,
                                     reconstructed_path=tmp_reconstructed.name,
                                     original_file_info=row_info)
                        
                        match = re.search(r"(u|s)(\d+)be", column_name)
                        if match:
                            signed = match.group(1) == "s"
                            bits_per_sample = int(match.group(2))
                        else:
                            match = re.search(r"f(\d+)", column_name)
                            signed = True
                            bits_per_sample = int(match.group(1))

                        min_compression_ratio_by_name[c.label] = min(
                            min_compression_ratio_by_name[c.label],
                            os.path.getsize(input_path) / os.path.getsize(tmp_compressed.name)
                        )
                        max_compression_ratio_by_name[c.label] = max(
                            max_compression_ratio_by_name[c.label],
                            os.path.getsize(input_path) / os.path.getsize(tmp_compressed.name)
                        )

                        if not filecmp.cmp(input_path, tmp_reconstructed.name):
                            if (not isinstance(c, enb.icompression.LossyCodec)
                                    and not isinstance(c, enb.icompression.NearLosslessCodec)):
                                data_dict[column_name] = "Not lossless"
                            else:
                                data_dict[column_name] = "Lossy"
                            break
                        else:
                            if options.verbose > 2:
                                print("Losless!")

                            min_lossless_bitdepth_by_name[c.label] = min(
                                min_lossless_bitdepth_by_name[c.label],
                                bits_per_sample)
                            max_lossless_bitdepth_by_name[c.label] = max(
                                max_lossless_bitdepth_by_name[c.label],
                                bits_per_sample)
                    except Exception as ex:
                        data_dict[column_name] = "Not available"
                        if options.verbose > 1:
                            print(f"Error {state}; {ex}")
                        break
            else:
                data_dict[column_name] = "Lossless"
        data_dict["min_lossless_bitdepth"] = min_lossless_bitdepth_by_name[c.name]
        data_dict["max_lossless_bitdepth"] = max_lossless_bitdepth_by_name[c.name]
        df_capabilities.loc[c.label] = pd.Series(data_dict)

    df_capabilities["lossless_range"] = df_capabilities["codec_name"].apply(
        lambda name: f"{min_lossless_bitdepth_by_name[name]}"
                     f":{max_lossless_bitdepth_by_name[name]}"
        if math.isfinite(float(min_lossless_bitdepth_by_name[name]))
           and math.isfinite(float(max_lossless_bitdepth_by_name[name]))
        else "None"
    )
    df_capabilities["cr_range"] = df_capabilities["codec_name"].apply(
        lambda name: f"{min_compression_ratio_by_name[name]:.2f}"
                     f":{max_compression_ratio_by_name[name]:.2f}"
        if math.isfinite(float(min_compression_ratio_by_name[name]))
           and math.isfinite(float(max_compression_ratio_by_name[name]))
        else "None"
    )

    del df_capabilities["min_lossless_bitdepth"]
    del df_capabilities["max_lossless_bitdepth"]

    df_capabilities.to_csv("full_df_capabilitites.csv")

    print(f"[watch] df_capabilities={df_capabilities}")

    all_dir_names = list(target_dir_names)
    all_target_dir_names = ["mono_u8be", "rgb_u8be", "multi_u8be",
                            "mono_u16be", "rgb_u16be", "multi_u16be",
                            "mono_s16be", "rgb_s16be", "multi_s16be",
                            "codec_name",
                            "lossless_range", "cr_range"]

    all_column_names = [
        "8bit Mono", "8bit RGB", "8bit Multi",
        "16bit Mono", "16bit RGB", "16bit Multi",
        "Sig. 16bit Mono", "Sig. 16bit RGB", "Sig. 16bit Multi",
        "Lossless range", "CR range"
    ]

    full_df = df_capabilities.copy()
    for i, group_name in enumerate(["u8be", "u16be", "s16be"]):
        old_col_names = all_target_dir_names[i * 3:(i + 1) * 3] + all_target_dir_names[-2:]
        new_col_names = all_column_names[i * 3:(i + 1) * 3] + all_column_names[-2:]
        df_capabilities = full_df.copy()

        df_colors = df_capabilities.copy()
        df_colors["codec_name"] = "#ffffff"
        for d in df_capabilities.columns:
            df_colors[d] = df_capabilities[d].apply(
                lambda x: "#55ff55" if x == "Lossless"
                else "#ff5555" if x == "Not lossless"
                else "#8cb4ff" if x == "Lossy"
                else "#fbf3b5")

        for old, new in zip(old_col_names, new_col_names):
            if old in df_capabilities:
                df_capabilities[new] = df_capabilities[old]
                del df_capabilities[old]
            if old in df_colors:
                df_colors[new] = df_colors[old]
                del df_colors[old]

        df_capabilities = df_capabilities[new_col_names + ["codec_name"]]
        df_colors = df_colors[[*new_col_names]]

        plt.figure()
        fig, ax = plt.subplots(1, 1)
        ax.axis("off")

        df_capabilities.set_index("codec_name")

        table = pdpt.table(ax, df_capabilities[new_col_names],
                           loc="center",
                           cellColours=df_colors[new_col_names].values,
                           cellLoc="center")
        pdf_name = f"codec_availability_{group_name}.pdf"
        plt.savefig(pdf_name, bbox_inches="tight")
        plt.close()
        invocation = f"convert -density 400 {pdf_name} -trim {pdf_name.replace('.pdf', '.png')}"
        status, output = subprocess.getstatusoutput(invocation)
        if status != 0:
            raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
                status, invocation, output))
