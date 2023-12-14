import enb.plugins


class MontsecPlugin(enb.plugins.plugin.PluginJava):
    name = "montsec"
    label = "Wrapper for the montsec codec"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["Group on Interactive Coding of Images (GICI)"]
    tested_on = {"linux", "macos"}
