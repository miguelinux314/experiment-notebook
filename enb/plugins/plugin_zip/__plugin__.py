import enb.plugins


class LZBZPlugin(enb.plugins.Plugin):
    name = "zip"
    label = "Assortment of lz-based and bzip-based codecs"
    tags = {"data compression", "codec"}
    contrib_authors = ["The zlib team", "The lzma team", "The bz2 team"]
    contrib_reference_urls = ["https://docs.python.org/3/library/zlib.html",
                              "https://docs.python.org/3/library/lzma.html",
                              "https://docs.python.org/3/library/bz2.html"]
    tested_on = {"linux", "windows"}
