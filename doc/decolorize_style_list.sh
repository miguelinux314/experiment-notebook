#!/usr/bin/env bash
enb show styles | sed -r $'s/\x1B\\[[0-9;]*[mK]//g' | tail -n+3
