#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"""

import os
import sys
import json
import inspect
import importlib.util
from plugins import *
from os.path import isdir, join

## Old code, potentially to be ported to config.py
# class TemplateOptions(singleton_cli.GlobalOptions):
#     @cli_parsers_builder(""
#         , title="Subcommands"
#         , description="Allows you to either create or modify a template at will."
#         , new_parser=True
#         , parser_alias="template")
#     def template_parser(self, value):
#         pass
#
#     @cli_parsers_builder("n",
#                          group_name="General Options"
#         , parser_parent="template"
#         , action=singleton_cli.ValidationTemplateNameAction
#         , help="Followed by a string defines the name of a template"
#                + " to either be added, modified or deleted."
#         , required=False)
#     def template_name(self, value):
#         pass
#
#     """
#     @cli_parsers_builder("template_name",
#                          parser_parent="template"
#         , positional=True
#         , group_name="General Options"
#         , type=str
#         , help="This should also work.")
#     def template_name(self, value):
#         pass
#     """
#
#     @cli_parsers_builder("c",
#                          group_name="General Options"
#         , parser_parent="template"
#         , default=False
#         , action="store_true"
#         , help="To create a new template.")
#     def create_new_template(self, value):
#         pass
#
#     @cli_parsers_builder("l",
#                          group_name="General Options"
#         , parser_parent="template"
#         , default=False
#         , action="store_true"
#         , help="To list all the actions one can do over a template.")
#     def list_template_options(self, value):
#         pass
#
#     @cli_parsers_builder(""
#         , title="Subcommands"
#         , description="Allows you to add either en Experiment, an"
#                       + " Analysis or a step."
#         , new_parser=True
#         , parser_parent="template"
#         , parser_alias="add")
#     def add_parser(self, value):
#         pass
#
#     @cli_parsers_builder("w",
#                          group_name="General Options"
#         , parser_parent="template"
#         , default="./"
#         , type=str
#         , help="Controller that allows you to define the operation to"
#                + " be exacted over a template."
#         , action=singleton_cli.WritableDirAction
#         , required=False)
#     def working_dir(self, value):
#         pass
#
#     @cli_parsers_builder("l",
#                          group_name="General Options"
#         , parser_parent="add"
#         , help="To list adding options."
#         , default=False
#         , action="store_true")
#     def list_adding_options(self, value):
#         pass
#
#     @cli_parsers_builder("",
#                          group_name="General Options"
#         , new_parser=True
#         , parser_parent="add"
#         , parser_alias="experiment")
#     def experiment_parser(self, value):
#         pass
#
#     @cli_parsers_builder("l",
#                          group_name="General Options"
#         , parser_parent="experiment"
#         , help="To list all existing possible experiments."
#         , default=False
#         , action="store_true")
#     def list_experiments(self, value):
#         pass
#
#     @cli_parsers_builder("e",
#                          group_name="General Options"
#         , parser_parent="experiment"
#         , help="To define the experiment type we would like to add."
#         , type=str
#         , required=False)
#     def experiment_type(self, value):
#         pass
#
#     @cli_parsers_builder("",
#                          group_name="General Options"
#         , new_parser=True
#         , parser_parent="add"
#         , parser_alias="analysis")
#     def analysis_parser(self, value):
#         pass
#
#     @cli_parsers_builder("l",
#                          group_name="General Options"
#         , parser_parent="analysis"
#         , help="To list all existing possible analysis."
#         , default=False
#         , action="store_true")
#     def list_analysis(self, value):
#         pass
#
#     @cli_parsers_builder("a",
#                          group_name="General Options"
#         , parser_parent="analysis"
#         , help="To define the analysis to add."
#         , type=str
#         , required=False)
#     def analysis_type(self, value):
#         pass
#
#     @cli_parsers_builder("",
#                          group_name="General Options"
#         , new_parser=True
#         , parser_parent="add"
#         , parser_alias="step")
#     def step_parser(self, value):
#         pass
#
#

class ATemplate:
    __args = None
    __classifier = None
    __template = None

    def __init__(self, args=None):
        if args is not None:
            self.__args = args
            self.arg_handler()

        """
        spec = importlib.util.spec_from_file_location("plugin_fits",
                                                      "~/Documents/UAB/2021/TFG/experiment-notebook/plugins/")
        foo = importlib.util.module_from_spec(spec)
        print(foo)
        """

    def arg_handler(self):

        if self.__args["operation"] == "new_template":
            print("Here: ")
            print(self.__args)
            self.new_template()
        elif self.__args["operation"] == "add":
            print("Adding stuff:")
            self.add_element()

    def new_template(self):
        if self.__args["working_dir"] is None:
            print("A working dir has not been specified for this template, please define it."
                  + "\nFor more information on how to do it, execute command:\n"
                  + "enb -h / enb --help")
            sys.exit(1)
        else:
            print("Gets here too")

            template_path = os.path.join(self.__args["working_dir"], self.__args["template_name"])
            template = {
                "name": self.__args["template_name"],
                "path": template_path
            }

            file_to_create = os.path.join(template_path, template["name"] + ".json")

            print("The following directory is going to be created:\n"
                  + template_path)
            try:
                os.mkdir(template_path)
            except OSError:
                print("Creation of the directory %s failed" % template_path)
            else:
                print("Successfully created the directory %s " % template_path)

            with open(file_to_create, "w") as outfile:
                json.dump(template, outfile)

            print("The template has been created successfully, to modify it consult the help manual.")

    def add_element(self):
        print(self.__args)
        template_name = (self.__args["template_name"]
                         if self.__args["template_name"].endswith(".json")
                         else self.__args["template_name"] + ".json")
        template = None

        if self.__args["working_dir"] is None:
            print("A working dir has not been specified for this template, please define it."
                  + "\nFor more information on how to do it, execute command:\n"
                  + "enb -h / enb --help")
            sys.exit(1)
        elif not os.path.isfile(os.path.join(self.__args["working_dir"], template_name)):
            print("The template '" + template_name
                  + "' does not exist in path '"
                  + self.__args["assign_workdir"]
                  + "' try again.")
        else:
            template_full_path = os.path.join(self.__args["working_dir"], template_name)
            template = None

            with open(template_full_path) as json_file:
                template = json.load(json_file)
                print(template)

            template = self.add_experiment(template)

    def erase_template(self):
        pass

    def add_experiment(self, template):
        if template["experiments"] is None:
            template["experiments"] = {}

        template["experiments"][self.__args["parameters"]["experiment_type"]] = {}

        return template

    def add_analysis(self, template):
        pass

    def add_step(self, template):
        pass

    def load_template(self, path, template_name=""):
        if isdir(path):
            if template_name:
                template_name = template_name if template_name.endswith(".json") else template_name + ".json"
                full_path = join(path, template_name)

                with open(full_path) as json_file:
                    template = json.load(json_file)

                self.__template = template
            else:
                print("Sorry, the name of the template must contain at least 1 character.")
        else:
            print("Sorry, the path indicated does not exit.")

    def get_template(self):
        return self.__template
