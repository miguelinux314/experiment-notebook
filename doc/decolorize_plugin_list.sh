#!/usr/bin/env bash
# Run `enb plugin list` and remove ANSI color sequences from the output.
enb plugin list | sed -r $'s/\x1B\\[[0-9;]*[mK]//g'