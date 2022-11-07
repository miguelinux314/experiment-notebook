import enb.plugins


class FapecPlugin(enb.plugins.Plugin):
    name = "fapec"
    label = "Wrappers for FAPEC"
    tags = {"data compression", "image", "codec", "privative"}
    contrib_authors = ["DAPCOM"]
    contrib_reference_urls = ["https://www.dapcom.es/fapec/"]
    tested_on = {"linux"}
