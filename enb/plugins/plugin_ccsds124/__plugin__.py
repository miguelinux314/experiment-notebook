import enb.plugins


class LCNLPlugin(enb.plugins.Plugin):
    name = "ccsds124x0"
    label = "Wrappers for CCSDS 124.0-B-1"
    tags = {"data compression", "codec", "privative"}
    contrib_authors = ["Miguel Hernández-Cabronero", "Ian Blanes"]
    extra_requirements_message = ("Binaries for CCSDS 124.0-B-1 are not available due to "
                                  "intellectual property issues.")
    tested_on = {"linux"}
