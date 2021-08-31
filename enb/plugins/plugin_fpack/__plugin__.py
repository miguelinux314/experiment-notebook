import enb.plugins


class FPackPlugin(enb.plugins.PluginMake):
    name = "fpack"
    label = "Wrapper for the FPACK compressor"
    tags = {"data compression", "codec"}
    contrib_authors = ["William D. Pence"]
    contrib_reference_urls = ["https://heasarc.gsfc.nasa.gov/fitsio/fpack/"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/cfitsio-3.49.tar.gz?raw=true",
         "cfitsio-3.49.tar.gz")]
    tested_on = {"linux"}
