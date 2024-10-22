import os
import datetime

import enb
from enb.config import options


class EnbIniTemplate(enb.plugins.Template):
    """Copy a full enb.ini configuration in the destination project folder.
    """
    name = "enb.ini"
    author = ["Miguel Hernández-Cabronero"]
    label = "Copy a full enb.ini configuration in the destination project folder."
    tags = {"project"}
    tested_on = {"linux", "windows"}

    @classmethod
    def build(cls, installation_dir):
        full_ini_path = os.path.join(enb.enb_installation_dir, "config", "enb.ini")
        output_path = os.path.join(installation_dir, "enb.ini")
        if os.path.exists(output_path) and not options.force:
            raise ValueError(f"Output file {output_path} exists. Refusing to overwrite.")

        with open(full_ini_path, "r") as input_file, open(output_path, "w") as output_file:
            output_file.write(
                f"# Project created {datetime.datetime.now()}.\n"
                f"# Default option values can be changed by uncommenting them below.\n"
                f"# NOTE: CLI options overwrite the ones defined in this file.\n"
                "\n")
            output_file.write("".join(f"# {line}" for line in input_file.readlines()))
