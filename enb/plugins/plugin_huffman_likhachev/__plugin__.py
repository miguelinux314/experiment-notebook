import enb.plugins


class HuffmanLikhachevPlugin(enb.plugins.PluginMake):
    name = "huffman"
    label = "Huffman codec (8 bit)"
    tags = {"data compression", "codec"}
    contrib_authors = ["A. Likhachev"]
    contrib_reference_urls = ["https://github.com/ALikhachev/Huffman-code"]
    tested_on = {"linux"}
