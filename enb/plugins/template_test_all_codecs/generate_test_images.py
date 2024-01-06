#!/usr/bin/env python3
"""Generate the sample vectors for the codec availability test.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/02/24"

import os
import shutil
import numpy as np
import enb
from enb.config import options

def generate_test_images(base_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")):
    width = 128
    height = 128

    for bytes_per_sample in [1, 2, 4]:
        enb.logger.verbose(f"\tgenerating vectors with {bytes_per_sample} "
                           f"byte{'s' if bytes_per_sample != 1 else ''} per sample...")

        for label, component_count in [("mono", 1), ("rgb", 3), ("rgba", 4), ("multi", 32)]:
            for signed in [True, False]:
                for big_endian in [True, False]:
                    for is_float in [True, False]:
                        if (is_float and bytes_per_sample < 2) \
                                or (is_float and not signed) \
                                or (is_float and not big_endian) \
                                or (signed and bytes_per_sample < 2) \
                                or (not big_endian and bytes_per_sample <= 1):
                            continue

                        if is_float:
                            # Float  samples
                            effective_bits_per_sample = 8 * bytes_per_sample

                            output_dir = os.path.join(
                                base_dir,
                                f"{label}_float",
                                f"{label}_f{effective_bits_per_sample}")

                            if os.path.isdir(output_dir) and not options.force:
                                continue

                            shutil.rmtree(output_dir, ignore_errors=True)
                            os.makedirs(output_dir)

                            type = f"f{effective_bits_per_sample}"
                            dtype = f"f{bytes_per_sample}"
                            geometry = f"{component_count}x{height}x{width}"
                            output_path = os.path.join(output_dir, f"testsample_{type}-{geometry}.raw")
                            total_samples = width * height * component_count

                            if bytes_per_sample == 2:
                                min_sample_value = np.finfo(np.float16).min
                                max_sample_value = np.finfo(np.float16).max
                            elif bytes_per_sample == 4:
                                min_sample_value = np.finfo(np.float32).min
                                max_sample_value = np.finfo(np.float32).max

                            samples = max_sample_value * np.random.rand(total_samples).astype(np.float64)
                            samples[::2] *= -1
                            samples[0] = min_sample_value
                            samples[1] = max_sample_value
                            with open(output_path, "wb") as output_file:
                                output_file.write(bytes(samples.astype(dtype)))

                        else:
                            # Integer samples
                            type = f"{'s' if signed else 'u'}{8 * bytes_per_sample}{'be' if big_endian else 'le'}"
                            dtype = f"{'>' if big_endian else '<'}{'i' if signed else 'u'}{bytes_per_sample}"
                            geometry = f"{component_count}x{height}x{width}"
                            output_dir = os.path.join(
                                base_dir, f"{label}_{type}")

                            if os.path.isdir(output_dir) and not options.force:
                                continue

                            shutil.rmtree(output_dir, ignore_errors=True)
                            os.makedirs(output_dir)

                            for missing_bits in range(8 * bytes_per_sample):
                                effective_bits_per_sample = 8 * bytes_per_sample - missing_bits
                                output_path = os.path.join(output_dir, f"testsample_effective_dr_{effective_bits_per_sample}bit_{type}-{geometry}.raw")

                                total_samples = width * height * component_count
                                if signed:
                                    min_sample_value = - (2 ** (effective_bits_per_sample - 1))
                                    max_sample_value = 2 ** (effective_bits_per_sample - 1) - 1
                                else:
                                    min_sample_value = 0
                                    max_sample_value = 2 ** effective_bits_per_sample - 1
                                samples = np.zeros(total_samples)
                                for i in range(total_samples):
                                    samples[i] = min_sample_value + i % (max_sample_value - min_sample_value + 1)
                                samples[0] = min_sample_value
                                samples[1] = max_sample_value
                                with open(output_path, "wb") as output_file:
                                    output_file.write(bytes(samples.astype(dtype)))

if __name__ == '__main__':
    generate_test_images()
