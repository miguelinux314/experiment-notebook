import enb


class PNGToRawTemplate(enb.plugins.Template):
    name = "png-to-raw"
    author = ["Miguel Hernández-Cabronero"]
    label = "Curate a directory of PNG files into raw (fixed-length) format"
    tags = {"template", "data compression", "image"}
    tested_on = {"linux"}