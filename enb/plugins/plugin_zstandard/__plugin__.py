import enb.plugins

class ZstandardPlugin(enb.plugins.PluginMake):
    name = "zstd"
    label = "Zstandard library wrapper"
    tags = {"data compression", "codec"}
    authors = ["Òscar Maireles"]
    contrib_authors = ["Yann Collet"]
    contrib_reference_urls = ["https://github.com/facebook/zstd"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/zstd-1.1.3.zip?raw=true",
         "zstd-1.1.3.zip")]
    tested_on = {"linux"}
