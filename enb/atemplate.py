import os
import sys
import json
import inspect
import importlib.util
from plugins import *
from os.path import isdir, join


class ATemplate:
    __args = None
    __classifier = None
    __template = None

    def __init__(self, args=None):
        """
        spec = importlib.util.spec_from_file_location("plugin_fits",
                                                      "~/Documents/UAB/2021/TFG/experiment-notebook/plugins/")
        foo = importlib.util.module_from_spec(spec)
        print(foo)
        """

    def arg_handler(self):
        if self.__args["operation"] is "new_template":
            print("Here: ")
            print(self.__args)
            self.new_template()
        elif self.__args["operation"] is "add":
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
            if template_name is not "":
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
