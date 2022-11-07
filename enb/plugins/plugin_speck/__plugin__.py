import enb.plugins


class SpeckPlugin(enb.plugins.plugin.PluginJava):
    name = "speck"
    label = "Wrapper for the SPECK codec"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["Group on Interactive Coding of Images (GICI)"]
    contrib_reference_urls = [
        "https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/SPModule_20220804.zip?raw=true"]
    tested_on = {"linux"}
