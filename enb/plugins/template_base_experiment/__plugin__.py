import os
import glob
import shutil
import stat
import enb


class ExperimentTemplate(enb.plugins.Template):
    """Generic experiment template.
    """
    name = "experiment"
    author = ["Miguel Hernández-Cabronero"]
    label = "Generic experiment template. " \
            "Run `enb plugin list experiment` for specific experiment templates."
    tags = {"project", "documentation"}
    tested_on = {"linux", "windows"}

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False,
                fields=None):
        super().install(installation_dir=installation_dir,
                        overwrite_destination=overwrite_destination,
                        fields=fields)
        for py_path in glob.glob(os.path.join(installation_dir, "*.py")):
            os.chmod(py_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        # Copy the default enb.ini file into the project folder
        target_enb_ini = os.path.join(installation_dir, "enb.ini")
        if os.path.exists(target_enb_ini) and not options.force:
            enb.logger.warn(
                f"File {target_enb_ini} already exists. Not overwriting.")
        else:
            shutil.copyfile(os.path.join(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                         f"config", "enb.ini"),
                            os.path.join(installation_dir, f"enb.ini"))
