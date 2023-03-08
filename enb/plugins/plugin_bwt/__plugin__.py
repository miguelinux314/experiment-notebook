import os
import enb.plugins

class BWTPlugin(enb.plugins.PluginMake):
    name = "bwt"
    label = "Application of the Burrows-Wheeler Transform (BWT)"
    tags = {"data compression", "codec"}
    contrib_authors = ["Michael Dipperstein"]
    contrib_reference_urls = ["https://github.com/MichaelDipperstein/bwt"]
    tested_on = {"linux"}

    @classmethod
    def build(cls, installation_dir):
        super().build(installation_dir=installation_dir)
        os.rename(os.path.join(installation_dir, "sample"),
                  os.path.join(installation_dir, "bwt"))
