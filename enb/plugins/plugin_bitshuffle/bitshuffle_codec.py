"""Implementation of a codec that applies a bitshuffle transform before compressing with a codec instance
provided to the constructor.
"""
import os
import tempfile
import time

import bitshuffle
import numpy as np

import enb


class BitshuffleWrapper(enb.icompression.AbstractCodec):
    """Codec that applies bitshuffle to the data before compressing with a codec instance
    provided to the constructor.
    """

    def __init__(self, codec: enb.icompression.AbstractCodec):
        """
        :param codec: The codec instance used to compress and decompress the transformed data.
        """
        super().__init__(param_dict=dict(codec_name=codec.name))
        self.codec = codec

    def compress(self, original_path: str, compressed_path: str, original_file_info=None):
        """Apply bitshuffle and then compress with `self.codec`.
        """
        with tempfile.TemporaryDirectory(dir=enb.config.options.base_tmp_dir) as tmp_dir:
            # Save the transformed data to a temporary file (likely memory)
            shuffled_path = os.path.join(tmp_dir, os.path.basename(original_path))
            original_data = enb.isets.load_array(
                file_or_path=original_path,
                image_properties_row=original_file_info)
            time_before = time.process_time() if not enb.config.options.report_wall_time else time.time()
            shuffled_array = bitshuffle.bitshuffle(np.ascontiguousarray(original_data))
            time_after = time.process_time() if not enb.config.options.report_wall_time else time.time()
            shuffle_time = max(0.0, time_after - time_before)
            enb.isets.dump_array(array=shuffled_array, file_or_path=shuffled_path)

            # Compress the transformed data normally
            time_before = time.process_time() if not enb.config.options.report_wall_time else time.time()
            compression_results = self.codec.compress(
                original_path=shuffled_path,
                compressed_path=compressed_path,
                original_file_info=original_file_info
            )
            time_after = time.process_time() if not enb.config.options.report_wall_time else time.time()
            compression_time = max(0.0, time_after - time_before)
            if compression_results is None:
                compression_results = self.compression_results_from_paths(
                    original_path=shuffled_path,
                    compressed_path=compressed_path)
            os.remove(shuffled_path)

            compression_results.original_path = original_path
            if compression_results.compression_time_seconds is None:
                compression_results.compression_time_seconds = compression_time
            compression_results.compression_time_seconds += shuffle_time

            return compression_results

    def decompress(self, compressed_path, reconstructed_path, original_file_info=None):
        """Decompress with `self.codec` and then revert the bitshuffle transform.
        """
        with tempfile.TemporaryDirectory(dir=enb.config.options.base_tmp_dir) as tmp_dir:
            shuffled_path = os.path.join(tmp_dir, f"{reconstructed_path}_shuffled")

            # Decompress the shuffled data
            time_before = time.process_time() if not enb.config.options.report_wall_time else time.time()
            decompression_results = self.codec.decompress(
                compressed_path=compressed_path,
                reconstructed_path=shuffled_path)
            time_after = time.process_time() if not enb.config.options.report_wall_time else time.time()
            decompression_time = max(0.0, time_after - time_before)
            if decompression_results is None:
                decompression_results = self.decompression_results_from_paths(
                    compressed_path=compressed_path,
                    reconstructed_path=shuffled_path)
            decompression_results.reconstructed_path = reconstructed_path

            # Unshuffle and write output
            array = enb.isets.load_array(shuffled_path)
            time_before = time.process_time() if not enb.config.options.report_wall_time else time.time()
            unshuffled_array = bitshuffle.bitunshuffle(np.ascontiguousarray(array))
            time_after = time.process_time() if not enb.config.options.report_wall_time else time.time()
            shuffle_time = max(0.0, time_after - time_before)
            enb.isets.dump_array(array=unshuffled_array, file_or_path=reconstructed_path)
            os.remove(shuffled_path)

            if decompression_results.decompression_time_seconds is None:
                decompression_results.decompression_time_seconds = decompression_time
            decompression_results.decompression_time_seconds += shuffle_time
            
            return decompression_results

    @property
    def name(self):
        """Return the original codec name and the quantization parameter
        """
        return f"{self.codec.name}_bitshuffle"

    @property
    def label(self):
        """Return the original codec label and the quantization parameter.
        """
        return f"Bitshuffle + {self.codec.label}"
