#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tools to connect to ray clusters
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "21/11/2019"

import os
import ray

from enb.config import get_options

options = get_options()


def init_ray():
    if not ray.is_initialized():
        if os.path.exists(os.path.expanduser("~/cluster_head.txt")):
            print("Joining cluster...")
            ray.init(address=open(os.path.expanduser("~/cluster_head.txt"), "r").read())
        else:
            print("Making new cluster...")
            ray.init()
