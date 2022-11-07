import enb.plugins


class CCSDS122Plugin(enb.plugins.Plugin):
    name = "ccsds122x1"
    label = "Wrappers for CCSDS 122.1"
    tags = {"data compression", "codec", "image", "privative"}
    contrib_authors = ["Ian Blanes", "Miguel Hernández-Cabronero", "CNES, et al."]
    contrib_reference_urls = ["https://ccsds.org"]
    tested_on = {"linux"}
