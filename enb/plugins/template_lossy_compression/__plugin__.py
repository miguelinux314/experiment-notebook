import os
import stat
import glob
import enb.plugins


class CompressionExperimentTemplate(enb.plugins.Template):
    """Template for lossy data compression experiments.
    """
    name = "lossy-compression"
    author = ["Miguel Hernández-Cabronero"]
    label = "Template for lossy compression experiments"
    tags = {"project", "image", "documentation", "data compression"}
    tested_on = {"linux", "windows"}

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False, fields=None):
        # Save
        super().install(installation_dir=installation_dir,
                        overwrite_destination=overwrite_destination,
                        fields=fields)
        for py_path in glob.glob(os.path.join(installation_dir, "*.py")):
            os.chmod(py_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        # Copy the default enb.ini file into the project folder
        enb.plugins.install("enb.ini", installation_dir, overwrite=True, automatic_import=False)
