import enb.plugins


class FPZIPPlugin(enb.plugins.PluginMake):
    name = "fpzip"
    label = "Wrappers for FPZIP codecs"
    tags = {"data compression", "codec"}
    contrib_authors = ["Peter Lindstrom", "Martin Isenburg"]
    contrib_reference_urls = ["https://doi.org/10.1109/TVCG.2006.143"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/fpzip-1.3.0.tar.gz?raw=true",
         "fpzip-1.3.0.tar.gz")]
    tested_on = {"linux"}
