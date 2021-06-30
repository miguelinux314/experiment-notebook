#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the sample vectors for the test.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "24/02/2021"

import os
import shutil
import numpy as np

if __name__ == '__main__':
    width = 128
    height = 128

    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    for label, component_count in [("mono", 1), ("rgb", 3), ("rgba", 4), ("multi", 10)]:
        for signed in [True, False]:
            for bytes_per_sample in [1, 2, 4]:
                if signed and bytes_per_sample == 1:
                    continue

                for missing_bits in range(8):
                    bits_per_sample = 8 * bytes_per_sample - missing_bits

                    output_dir = os.path.join(base_dir, f"{label}_{'s' if signed else 'u'}{bits_per_sample}be")
                    shutil.rmtree(output_dir, ignore_errors=True)
                    os.makedirs(output_dir)

                    type = f"{'s' if signed else 'u'}{8 * bytes_per_sample}be"
                    dtype = f">{'i' if signed else 'u'}{bytes_per_sample}"
                    geometry = f"{component_count}x{height}x{width}"
                    output_path = os.path.join(output_dir, f"sample_{type}-{geometry}.raw")

                    total_samples = width*height*component_count
                    if signed:
                        min_sample_value = - (2 ** (bits_per_sample-1))
                        max_sample_value = 2 ** (bits_per_sample-1) - 1
                    else:
                        min_sample_value = 0
                        max_sample_value = 2**bits_per_sample - 1
                    samples = np.zeros(total_samples)
                    for i in range(total_samples):
                        samples[i] = min_sample_value + i % (max_sample_value - min_sample_value + 1)
                    samples[0] = min_sample_value
                    samples[1] = max_sample_value


                    with open(output_path, "wb") as output_file:
                        output_file.write(bytes(samples.astype(dtype)))
                        
            for bytes_per_sample in [2,4]:
                if signed and bytes_per_sample == 1:
                    continue

                for missing_bits in range(8):
                    bits_per_sample = 8 * bytes_per_sample - missing_bits

                    output_dir = os.path.join(base_dir, f"{label}_{'s' if signed else 'f'}{bits_per_sample}be")
                    shutil.rmtree(output_dir, ignore_errors=True)
                    os.makedirs(output_dir)
                    
                    type = f"{'s' if signed else 'f'}{8 * bytes_per_sample}be"
                    dtype = f"{'>i' if signed else 'f'}{bytes_per_sample}"
                    
                    geometry = f"{component_count}x{height}x{width}"
                    output_path = os.path.join(output_dir, f"sample_{type}-{geometry}.raw")

                    total_samples = width*height*component_count
                    if signed:
                        min_sample_value = - (2 ** (bits_per_sample-1))
                        max_sample_value = 2 ** (bits_per_sample-1) - 1
                    else:
                        min_sample_value = np.finfo('f').min
                        max_sample_value = np.finfo('f').max
                    samples = np.zeros(total_samples)
                    for i in range(total_samples):
                        samples[i] = min_sample_value + i % (max_sample_value - min_sample_value + 1)
                    samples[0] = min_sample_value
                    samples[1] = max_sample_value


                    with open(output_path, "wb") as output_file:
                        output_file.write(bytes(samples.astype(dtype)))

            for bytes_per_sample in [2,4,8]:
                if signed and bytes_per_sample == 1:
                    continue

                for missing_bits in range(8):
                    bits_per_sample = 8 * bytes_per_sample - missing_bits

                    output_dir = os.path.join(base_dir, f"{label}_{'s' if signed else 'u' and 'f'}{bits_per_sample}be")
                    shutil.rmtree(output_dir, ignore_errors=True)
                    os.makedirs(output_dir)
                    
                    type = f"{'s' if signed else 'u' and 'f'}{8 * bytes_per_sample}be"
                    dtype = f"{'>i' if signed else '>u' and 'f'}{bytes_per_sample}"
                    
                    geometry = f"{component_count}x{height}x{width}"
                    output_path = os.path.join(output_dir, f"sample_{type}-{geometry}.raw")

                    total_samples = width*height*component_count
                    if signed:
                        min_sample_value = - (2 ** (bits_per_sample-1))
                        max_sample_value = 2 ** (bits_per_sample-1) - 1
                    else:
                        min_sample_value = 0
                        max_sample_value = 2**bits_per_sample - 1
                    samples = np.zeros(total_samples)
                    for i in range(total_samples):
                        samples[i] = min_sample_value + i % (max_sample_value - min_sample_value + 1)
                    samples[0] = min_sample_value
                    samples[1] = max_sample_value


                    with open(output_path, "wb") as output_file:
                        output_file.write(bytes(samples.astype(dtype)))




