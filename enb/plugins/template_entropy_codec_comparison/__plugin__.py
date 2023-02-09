import sys
import os
import shutil
import stat
import glob
import subprocess
import enb.plugins
from enb.config import options


class EntropyCodecComparisonTemplate(enb.plugins.Template):
    """Template for a comparison of (lossless) entropy codecs.
    """
    name = "entropy-codec-comparison"
    author = ["Miguel Hernández-Cabronero"]
    label = "Template for the comparison of entropy codecs"
    tags = {"project", "data compression"}
    tested_on = {"linux"}

    additional_plugins = ["fse", "zip", "lz4", "arithmetic-coder", "huffman"]

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False, fields=None):
        super().install(installation_dir=installation_dir,
                        overwrite_destination=overwrite_destination,
                        fields=fields)
        for py_path in glob.glob(os.path.join(installation_dir, "*.py")):
            os.chmod(py_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        # Copy the default enb.ini file into the project folder
        target_enb_ini = os.path.join(installation_dir, "enb.ini")
        if os.path.exists(target_enb_ini) and not options.force:
            enb.logger.warn(f"File {target_enb_ini} already exists. Not overwriting.")
        else:
            shutil.copyfile(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                         f"config", "enb.ini"),
                            os.path.join(installation_dir, f"enb.ini"))
            
        for p in cls.additional_plugins:
            with enb.logger.message_context(f"Installing plugin {repr(p)}"):
                invocation = f"{sys.executable} -m enb plugin install {p} {os.path.join(installation_dir, 'plugins', p)}"
                status, output = subprocess.getstatusoutput(invocation)
                if status != 0:
                    raise Exception(f"Status = {status} != 0.\n"
                                    f"Input=[{invocation}].\n"
                                    f"Output=[{output}]")
