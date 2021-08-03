import enb.plugins


class ZFPPlugin(enb.plugins.PluginMake):
    name = "zfp"
    label = "Wrapper for the zfp library"
    tags = {"data compression", "codec"}
    contrib_authors = ["Lawrence Livermore National Laboratory"]
    contrib_reference_urls = ["https://www.travis-ci.com/github/LLNL/zfp"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/zfp-0.5.5.tar.gz?raw=true",
         "zfp-0.5.5.tar.gz")]
    tested_on = {"linux"}
