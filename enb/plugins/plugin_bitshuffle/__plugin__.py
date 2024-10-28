import enb.plugins


class BitshufflePlugin(enb.plugins.Plugin):
    name = "bitshuffle"
    label = "Codec wrapper that applies bitshuffle before another codec"
    tags = {"data compression", "codec"}
    contrib_authors = ["Andrew Collete et al."]
    contrib_reference_urls = ["https://github.com/h5py/h5py"]
    required_pip_modules = ["bitshuffle"]
    tested_on = {"linux"}
