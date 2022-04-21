import enb.plugins


class ACPlugin(enb.plugins.PluginMake):
    name = "arithmetic_codec"
    label = "Arithmetic codec (8 bit)"
    tags = {"data compression", "codec"}
    contrib_authors = ["Nayuki"]
    contrib_reference_urls = ["https://github.com/nayuki/Reference-arithmetic-coding/"]
    contrib_download_url_name = [
        (
        "https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/nayuki_arithmetic_coder_reference.zip?raw=true",
        "nayuki_arithmetic_coder_reference.zip")]
    tested_on = {"linux"}
