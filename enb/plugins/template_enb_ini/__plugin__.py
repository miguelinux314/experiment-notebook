import os
import shutil
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
        output_path = os.path.join(installation_dir, "enb.ini")
        if os.path.exists(output_path) and not options.force:
            raise ValueError(f"Output file {output_path} exists. Refusing to overwrite.")
        shutil.copy(os.path.join(enb.enb_installation_dir, "config", "enb.ini"), output_path)
