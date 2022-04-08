import enb.plugins


class FPCPlugin(enb.plugins.PluginMake):
    name = "fpc"
    label = "FPC codec wrappers"
    tags = {"data compression", "codec"}
    contrib_authors = ["Martin Burtscher et al."]
    contrib_reference_urls = ["https://userweb.cs.txstate.edu/~burtscher/research/FPC/"]
    tested_on = {"linux"}
