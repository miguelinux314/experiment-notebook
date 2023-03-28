import enb.plugins


class LPAQ8Plugin(enb.plugins.PluginMake):
    name = "lpaq8"
    label = "Implementation of the LPAQ8 algorithm"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["Matt Mahoney", "Alexander Ratushnyak"]
    contrib_reference_urls = ["http://mattmahoney.net/dc/"]
    tested_on = {"linux"}
