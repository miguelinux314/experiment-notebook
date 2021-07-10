import sys
import enb
import enb.config as config
from enb import aanalysis
from enb import icompression
from enb.icompression import experiment
import inspect
import plugins


def list_add_options():
    print("You can add to a template the following elements:\n"
          + "- Experiments\n"
          + "- Analysis\n"
          + "- Steps\n\n"
          + "For more information on this, consult the manual.")


class ParameterHandler:
    __paramenters = {}

    def __init__(self, template_path):
        print(template_path)
        modules = [obj for name, obj in inspect.getmembers(plugins, inspect.ismodule)]
        submodules = []
        plugins_dict = {}

        for a_module in modules:
            for name, submodule in inspect.getmembers(a_module, inspect.ismodule):
                if "_codec" in name:
                    submodules.append(submodule)
                    plugins_dict[name] = {}
                    print(name)
                    for n, obj in inspect.getmembers(submodule, inspect.isclass):
                        if issubclass(obj, icompression.AbstractCodec) and "Abstract" not in n:
                            plugins_dict[name] = {
                                n: obj
                            }

        print(plugins_dict)



    def sort_out_parameters(self):
        if "template" in sys.argv:
            print("template")
            if config.options["list_template_options"]:
                print(self.list("template_options"))
            elif "add" in sys.argv:
                if config.options["list_adding_options"]:
                    print(self.list("add_elements"))
                elif config.options["list_experiments"]:
                    print(self.list("experiments"))
                    print("Something else other than listing")

            """
            self.__paramenters["template_name"] = config.options["template_name"]
            self.__paramenters["working_dir"] = config.options["working_dir"]

            if "-c" in sys.argv:
                self.__paramenters["operation"] = "new_template"
            elif "add" in sys.argv:
                self.__paramenters["operation"] = "add"

                if config.options["list_template_options"]:
                    print(self.list("add_elements"))
                elif "experiment" in sys.argv:
                    if config.options["list_experiments"]:
                        print(self.list("experiments"))
                    elif config.options["experiment_type"]:
                        available_experiments = self.list("experiments", True)

                        if config.options["experiment_type"] in available_experiments:
                            print("Valid experiment")
                            self.__paramenters["element"] = "experiment"
                            self.__paramenters["parameters"] = {}
                            self.__paramenters["parameters"]["experiment_type"] = config.options["experiment_type"]
                        else:
                            print("Sorry, the experiment '" + config.options["experiment_type"]
                                  + "' does not exist, to list available experiments consult the manual.")

                elif "analysis" in sys.argv:
                    if config.options["list_analysis"]:
                        print("Analysis:")
                        print(self.list("analysis"))
                    elif config.options["analysis_type"]:
                        available_analysis = self.list("analysis", True)

                        if config.options["analysis_type"] in available_analysis:
                            print("Valid analysis")
                            self.__paramenters["element"] = "analysis"
                            self.__paramenters["parameters"] = {}
                            self.__paramenters["parameters"]["analysis_type"] = config.options["analysis_type"]
                        else:
                            print("Sorry, the analysis '" + config.options["analysis_type"]
                                  + "' does not exist, to list available analysis consult the manual.")
                elif "step" in sys.argv:
                    self.__paramenters["element"] = "step"
                    self.__paramenters["parameters"] = {}

            # template = atemplate.ATemplate(params)
            """

    @staticmethod
    def list(option, to_validate=False):
        obj_to_find = None
        obj_to_exclude = None
        listed_stuff = []

        if option == "template_options":
            message = "You can execute the following operations on an existing template:\n" \
                   + "- add\n\n" \
                   + "For more information on this, consult the manual."
        elif option == "add_elements":
            message = "You can add to a template the following elements:\n" \
                   + "- Experiments\n" \
                   + "- Analysis\n" \
                   + "- Steps\n\n" \
                   + "For more information on this, consult the manual."
        else:
            modules = inspect.getmembers(enb, inspect.ismodule)

            for a_module in modules:
                for name, obj in inspect.getmembers(a_module[1]):
                    if inspect.isclass(obj) and issubclass(obj, experiment.Experiment
                    if option == "experiments" else aanalysis.Analyzer) and name is not obj_to_exclude:
                        listed_stuff.append(name)

            message = "You can add the following " + option + " to a template:\n\n"

            for element in listed_stuff:
                message = message + "- " + element + "\n"

            message += "\nFor more information consult the manual"

        return listed_stuff if to_validate else message
