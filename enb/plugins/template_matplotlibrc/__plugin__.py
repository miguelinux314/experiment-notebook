import os
import shutil
import matplotlib
import enb
from enb.config import options


class MatplotlibrcTemplate(enb.plugins.Template):
    """Copy a full enb.ini configuration in the destination project folder.
    """
    name = "matplotlibrc"
    author = ["Miguel Hernández-Cabronero"]
    label = "Copy matplotlib's default rc file into the destination directory."
    tags = {"project"}
    tested_on = {"linux", "windows"}

    @classmethod
    def build(cls, installation_dir):
        output_path = os.path.join(installation_dir, "matplotlibrc")
        if os.path.exists(output_path) and not options.force:
            raise ValueError(f"Output file {output_path} exists. Refusing to overwrite.")
        shutil.copy(matplotlib.matplotlib_fname(), output_path)
        print("\nSee https://matplotlib.org/stable/tutorials/introductory/customizing.html#the-matplotlibrc-file \n"
              "for information on how to edit this file.\n")
