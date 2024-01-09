import os
import glob
import shutil
import configparser
import enb
from enb.config import options


class AbstractColorsTemplate:
    author = ["Miguel Hernández-Cabronero"]
    tags = {"project"}
    tested_on = {"linux"}

    @classmethod
    def install(cls, installation_dir):
        input_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{cls.name}.ini")
        if not os.path.exists(input_path):
            raise ValueError(f"Template plugin {cls.__name__} is not properly configured: "
                             f"{input_path} does not exist.\nPlease reinstall enb and contact the "
                             f"maintainers if the problem persists.")

        output_path = os.path.join(installation_dir, f"{cls.name}.ini")
        if os.path.exists(output_path) and not options.force:
            raise ValueError(f"Output file {output_path} exists. Refusing to overwrite.")

        # Verify that no clashes exist with currently installed config files
        color_config = configparser.ConfigParser()
        color_config.read(input_path)

        for ini_path in glob.glob(os.path.join(installation_dir, "*.ini")):
            existing_config = configparser.ConfigParser()
            existing_config.read(ini_path)

            for cat_name, category in color_config.items():
                if cat_name == "DEFAULT":
                    continue
                if cat_name not in existing_config:
                    continue
                for color_option_name in category.keys():
                    if color_option_name in existing_config[cat_name]:
                        enb.logger.warn(
                            f"Option {repr(color_option_name)} in category {repr(cat_name)} "
                            f"was already present in {repr(os.path.abspath(ini_path))}, "
                            f"and in {repr(os.path.abspath(output_path))}. "
                            f"Consider removing one of the definitions, as it is not guaranteed"
                            f"which of the values will be kept by enb.\n",
                            markup=True)

        shutil.copyfile(input_path, output_path)
        cls.report_successful_installation(installation_dir=installation_dir)


class DefaultColorsTemplate(AbstractColorsTemplate, enb.plugins.Template):
    """Default color template.
    """
    name = "colors-default"
    label = "Default color template for light or dark background terminals"


class DarkColorsTemplate(AbstractColorsTemplate, enb.plugins.Template):
    """Dark color template.
    """
    name = "colors-dark"
    label = "Color template for dark background terminals"
