import enb.plugins


class FSEPlugin(enb.plugins.PluginMake):
    name = "fse"
    label = "Wrappers for FSE codecs. Includes a Huffman-only entropy codec."
    tags = {"data compression", "codec"}
    contrib_authors = ["Yann Collet"]
    contrib_reference_urls = ["https://github.com/Cyan4973/FiniteStateEntropy"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/fse_git.zip?raw=true",
         "fse_git.zip")]
    tested_on = {"linux"}
