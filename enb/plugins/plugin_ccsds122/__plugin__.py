import enb.plugins


class CCSDS122Plugin(enb.plugins.Plugin):
    name = "ccsds122x1"
    label = "Wrappers for CCSDS 122.1"
    tags = {"data compression", "codec", "privative"}
    contrib_authors = ["Ian Blanes", "Miguel Hernández-Cabronero", "CNES", "et al."]
    contrib_reference_urls = ["https://ccsds.org"]
    extra_requirements_message = """
    WARNING: neither source code nor binaries of this plugin can be distributed by enb. 
    It will be essentially useless unless you can provide the appropriate binaries.
    """
    tested_on = {"linux"}
