import enb.plugins


class HuffmanNayukiPlugin(enb.plugins.PluginMake):
    name = "huffman"
    label = "Huffman codec (8 bit)"
    tags = {"data compression", "codec"}
    contrib_authors = ["Project Nayuki"]
    contrib_reference_urls = ["https://github.com/nayuki/Reference-Huffman-coding"]
    tested_on = {"linux"}
