import enb.plugins


class EmpordaPlugin(enb.plugins.plugin.PluginJava):
    name = "emporda"
    label = "Wrapper for the emporda codec"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["Group on Interactive Coding of Images (GICI)"]
    contrib_reference_urls = ["http://gici.uab.cat/GiciWebPage/downloads.php#emporda"]
    tested_on = {"linux"}
