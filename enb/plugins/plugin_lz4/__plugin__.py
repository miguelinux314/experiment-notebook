import enb.plugins


class LZ4Plugin(enb.plugins.PluginMake):
    name = "lz4"
    label = "Wrapper for a LZ4 codec"
    tags = {"data compression", "codec"}
    contrib_authors = ["Yann Collet"]
    contrib_reference_urls = ["https://lz4.github.io/lz4/"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/lz4-1.9.2.zip?raw=true",
         "lz4-1.9.2.zip")]
    tested_on = {"linux"}
