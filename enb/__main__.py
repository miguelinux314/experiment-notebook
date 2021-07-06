#!/usr/bin/env python3
import enb.atemplate as atemplate
import template_generator
import enb.config as config


def enb():
    template = atemplate.ATemplate()
    template.load_template("/home/alys/Documents/UAB/2021/TFG/tests/MyThingy/", "MyThingy")

    template_generator.template_scripts.script_generator(template)


