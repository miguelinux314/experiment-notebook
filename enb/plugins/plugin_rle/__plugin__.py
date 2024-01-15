import os
import zipfile
import shutil
import enb.plugins


class RLE(enb.plugins.PluginMake):
    name = "rle"
    label = "Run-Length Encoding codec"
    tags = {"data compression", "codec"}
    contrib_authors = ["Michael Dipperstein"]
    contrib_reference_urls = ["https://github.com/MichaelDipperstein/rle"]
    tested_on = {"linux"}

    @classmethod
    def build(cls, installation_dir):
        with zipfile.ZipFile(os.path.join(os.path.dirname(__file__), "rle.zip"), "r") as zip_file:
            zip_file.extractall(path=installation_dir)
        super().build(installation_dir=installation_dir)
        shutil.rmtree(os.path.join(installation_dir, "rle_src"))
