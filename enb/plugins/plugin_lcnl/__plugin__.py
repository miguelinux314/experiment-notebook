import enb.plugins


class LCNLPlugin(enb.plugins.Plugin):
    name = "lcnl"
    label = "Wrappers for LCNL CCSDS 123.0-B-2"
    tags = {"data compression", "image", "codec", "privative"}
    contrib_authors = ["Ian Blanes", "Miguel Hernández-Cabronero", "CNES, et al."]
    contrib_reference_urls = [
        "http://deic.uab.cat/~mhernandez/media/papers/Miguel_Hernandez-IEEE_GRSM_123x0b2_explained.pdf"]
    extra_requirements_message = "Low-complexity near-lossless image compression (LCNL), CCSDS 123.0-B2\n" \
                                 "The source code and the binaries are not redistributed with enb due to intellectual property issues.\n" \
                                 "The binaries can be obtained at https://www.connectbycnes.fr/en/ccsds-1230-b-2-ccsds-1210-b-3 provided by CNES."
    tested_on = {"linux"}
