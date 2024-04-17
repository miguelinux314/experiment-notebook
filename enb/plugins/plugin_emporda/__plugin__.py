import os
import zipfile
import enb.plugins


class EmpordaPlugin(enb.plugins.plugin.PluginJava):
    name = "emporda"
    label = "Wrapper for the emporda codec (AC and CCSDS versions)"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["Group on Interactive Coding of Images (GICI)"]
    contrib_reference_urls = ["http://gici.uab.cat/GiciWebPage/downloads.php#emporda"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/"
         "emporda_20240419.zip?raw=true", "emporda.zip")]
    tested_on = {"linux"}

    @classmethod
    def build(cls, installation_dir):
        """Unzip the folder contents and build the plugin.
        """
        with zipfile.ZipFile(os.path.join(installation_dir, "emporda.zip"), "r") as zip_file:
            zip_file.extractall(installation_dir)
        super().build(installation_dir)
