import inspect
import importlib.util
from os import makedirs
from os.path import basename, join, exists
from enb import icompression
import plugins
import jinja2
from jinja2 import Environment, PackageLoader, select_autoescape


class script_generator:
    """

    """
    __template_json = None
    __template = None
    __script = None

    def __init__(self, a_template):
        """

        :param a_template:
        """
        self.__template_json = a_template.get_template()
        self.__script = ""
        print(self.__template_json)
        #self.scan_for_plugins()
        self.generate_script()

    def scan_for_plugins(self):
        """

        :return:
        """
        plugins_dict = {}
        modules = []

        if self.__template_json["plugins"]["plugins_dir"] is not None:
            base_name = basename(self.__template_json["plugins"]["plugins_dir"])
            base_path = self.__template_json["plugins"]["plugins_dir"]
            spec = importlib.util.spec_from_file_location(base_name, join(base_path, "../enb/__init__.py"))
            plugins_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugins_module)

            modules = [a_module for a_module in inspect.getmembers(plugins_module, inspect.ismodule) if
                       a_module[0].startswith("plugin")]
        else:
            modules = [a_module for a_module in inspect.getmembers(plugins, inspect.ismodule) if
                       a_module[0].startswith("plugin")]

        for a_module in modules:
            if a_module[0].startswith("plugin"):
                for name, obj in inspect.getmembers(a_module[1], inspect.ismodule):
                    plugins_dict[name] = {}

                    for n, submodule in inspect.getmembers(obj, inspect.isclass):
                        if issubclass(submodule, icompression.AbstractCodec) and "Abstract" not in n:
                            plugins_dict[name][n] = submodule

        self.__template_json["plugins"]["plugins_dict"] = plugins_dict

    def generate_script(self):
        """

        :return:
        """
        env = Environment(
            loader=jinja2.PackageLoader('template_generator'),
            autoescape=select_autoescape()
        )

        self.__template = env.get_template("experiment_template.py.tlp")

        if not exists(join(self.__template_json["template_workdir"], "data")):
            makedirs(join(self.__template_json["template_workdir"], "data"))

        with open(join(self.__template_json["template_workdir"], self.__template_json["template_name"]) + ".py", "w") \
                as template_file:
            template_file.write(self.__template.render(**self.__template_json))