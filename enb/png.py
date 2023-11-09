#!/usr/bin/env python3
"""PNG manipulation (e.g., curation) tools.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2023/02/12"

import os
import subprocess
import tempfile

import imageio
import numpngw
import numpy as np
import pdf2image

import enb
import enb.sets


class PNGWrapperCodec(enb.icompression.WrapperCodec):
    """Raw images are coded into PNG before compression with the wrapper,
    and PNG is decoded to raw after decompression.
    """

    # pylint: disable=abstract-method

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        img = enb.isets.load_array_bsq(
            file_or_path=original_path, image_properties_row=original_file_info)

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
            numpngw.write_png(tmp_file.name, img)
            compression_results = super().compress(
                original_path=tmp_file.name,
                compressed_path=compressed_path,
                original_file_info=original_file_info)
            crs = self.compression_results_from_paths(
                original_path=original_path, compressed_path=compressed_path)
            crs.compression_time_seconds = max(
                0, compression_results.compression_time_seconds)
            crs.maximum_memory_kb = compression_results.maximum_memory_kb
            return crs

    def decompress(self, compressed_path, reconstructed_path,
                   original_file_info=None):
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
            decompression_results = super().decompress(
                compressed_path=compressed_path,
                reconstructed_path=tmp_file.name)

            invocation = f"file {tmp_file.name}"
            status, output = subprocess.getstatusoutput(invocation)
            if status != 0:
                raise Exception(f"Status = {status} != 0.\n"
                                f"Input=[{invocation}].\n"
                                f"Output=[{output}]")
            img = imageio.imread(tmp_file.name, "png")
            img.swapaxes(0, 1)
            assert len(img.shape) in [2, 3, 4]
            if len(img.shape) == 2:
                img = np.expand_dims(img, axis=2)

            dtype = ">"
            dtype += "i" if original_file_info["signed"] else "u"
            dtype += f"{original_file_info['bytes_per_sample']}"

            enb.isets.dump_array_bsq(img, file_or_path=reconstructed_path,
                                     dtype=dtype)

            drs = self.decompression_results_from_paths(
                compressed_path=compressed_path,
                reconstructed_path=reconstructed_path)
            drs.decompression_time_seconds = decompression_results.decompression_time_seconds
            drs.maximum_memory_kb = decompression_results.maximum_memory_kb


class PNGCurationTable(enb.sets.FileVersionTable):
    """Given a directory tree containing PNG images, copy those images into
    a new directory tree in raw BSQ format adding geometry information tags to
    the output names recognized by `enb.isets.load_array_bsq`.
    """
    dataset_files_extension = "png"

    def __init__(self, original_base_dir, version_base_dir,
                 csv_support_path=None):
        """
        :param original_base_dir: path to the original directory
          (it must contain all indices requested later with self.get_df()).
          If None, options.base_datset_dir is used

        :param version_base_dir: path to the versioned base directory
          (versioned directories preserve names and structure within
          the base dir)

        :param csv_support_path: path to the file where results
          (of the versioned data) are to be
          long-term stored.
          If None, one is assigned by default based on options.persistence_dir.
        """
        super().__init__(version_base_dir=version_base_dir,
                         version_name=self.__class__.__name__,
                         original_base_dir=original_base_dir,
                         check_generated_files=False,
                         csv_support_path=csv_support_path)

    def version(self, input_path, output_path, row):
        """Transform PNG files into raw images with name tags
        recognized by isets.
        """
        with enb.logger.info_context(f"Versioning {input_path}"):
            img = imageio.v2.imread(input_path)
            if len(img.shape) == 2:
                img = img[:, :, np.newaxis]
            assert len(img.shape) == 3, \
                f"Invalid shape in read image {input_path}: {img.shape}"
            img = img.swapaxes(0, 1)
            if img.dtype == np.uint8:
                type_str = "u8be"
            elif img.dtype == np.uint16:
                type_str = "u16be"
            else:
                raise f"Invalid data type found in read image " \
                      f"{input_path}: {img.dtype}"
            output_path = f"{output_path[:-4]}-{type_str}" \
                          f"-{img.shape[2]}x{img.shape[1]}x{img.shape[0]}.raw"
            enb.isets.dump_array_bsq(array=img, file_or_path=output_path)


def render_array_png(img, png_path):
    """Render an uint8 or uint16 image with 1, 3 or 4 components.
    :param img: image array indexed by [x,y,z].
    :param png_path: path where the png file is to be stored.
    """
    max_value = np.max(img)
    if img.dtype == np.uint8:
        pass
    elif any(img.dtype == t for t in (np.uint16, np.uint32, np.uint64)):
        if max_value <= 255:
            img = img.astype(np.uint8)
        elif max_value <= 65535:
            img = img.astype(np.uint16)
        else:
            raise ValueError(
                f"Invalid maximum value {max_value} for type {img.dtype}. "
                f"Not valid for PNG")
    else:
        raise ValueError(
            f"Image type {img.dtype} not supported for rendering into PNG. "
            f"Try np.uint8 or np.uint16.")

    if img.shape[2] not in {1, 3, 4}:
        raise ValueError(
            f"Number of components not valid. Image shape (x,y,z) = {img.shape}")
    if os.path.dirname(png_path):
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
    imageio.imwrite(png_path, img.swapaxes(0, 1), format="png")


def raw_path_to_png(raw_path, png_path, image_properties_row=None):
    """Render an uint8 or uint16 raw image with 1, 3 or 4 components.

    :param raw_path: path to the image in raw format to render in png.
    :param png_path: path where the png file is to be stored.

    :param image_properties_row: if row_path does not contain geometry
      information, this parameter should be a dict-like object that indicates
      width, height, number of components, bytes per sample, signedness and
      endianness if applicable.
    """
    img = enb.isets.load_array_bsq(file_or_path=raw_path,
                                   image_properties_row=image_properties_row)
    render_array_png(img=img, png_path=png_path)


class PDFToPNG(enb.sets.FileVersionTable):
    """Take all .pdf files in input dir and save them as .png files into
    output_dir, maintining the relative folder structure.
    """
    dataset_files_extension = "pdf"

    def __init__(self, input_pdf_dir, output_png_dir, csv_support_path=None):
        super().__init__(version_name="pdf_to_png",
                         original_base_dir=input_pdf_dir,
                         version_base_dir=output_png_dir,
                         csv_support_path=csv_support_path,
                         check_generated_files=True)

    def version(self, input_path, output_path, row):
        with enb.logger.info_context(
                f"{self.__class__.__name__}: {input_path} -> {output_path}...\n"):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            imgs = pdf2image.convert_from_path(pdf_path=input_path)
            assert len(imgs) == 1
            imgs[0].save(output_path)


def pdf_to_png(input_dir, output_dir):
    """Take all .pdf files in input dir and save them as .png files into
    output_dir, maintining the relative folder structure.

    It is perfectly valid for input_dir and output_dir to point to the same
    location, but input_dir must exist beforehand.
    """
    with tempfile.NamedTemporaryFile() as tmp_file:
        PDFToPNG(input_pdf_dir=input_dir, output_png_dir=output_dir,
                 csv_support_path=tmp_file.name).get_df()
