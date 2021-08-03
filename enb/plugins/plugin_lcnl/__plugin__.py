import enb.plugins


class LCNLPlugin(enb.plugins.Plugin):
    name = "lcnl"
    label = "Wrappers for LCNL CCSDS 123.0-B-2"
    tags = {"data compression", "codec", "privative"}
    contrib_authors = ["Ian Blanes", "Miguel Hernández-Cabronero", "CNES", "et al."]
    contrib_reference_urls = [
        "http://deic.uab.cat/~mhernandez/media/papers/Miguel_Hernandez-IEEE_GRSM_123x0b2_explained.pdf"]
    extra_requirements_message = """
    WARNING: neither source code nor binaries of this plugin can be distributed by enb. 
    It will be essentially useless unless you can provide the appropriate binaries.
    """
    tested_on = {"linux"}
