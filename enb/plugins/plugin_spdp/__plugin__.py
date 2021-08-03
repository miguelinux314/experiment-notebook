import enb.plugins


class SPDPPlugin(enb.plugins.PluginMake):
    name = "spdp"
    label = "Wrapper for the spdp codec"
    tags = {"data compression", "codec"}
    contrib_authors = ["Martin Burtscher"]
    contrib_reference_urls = ["https://userweb.cs.txstate.edu/~burtscher/research/SPDPcompressor/"]
    tested_on = {"linux"}
