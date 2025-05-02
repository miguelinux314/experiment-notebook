import enb


class PPMToRawTemplate(enb.plugins.Template):
    name = "ppm-to-raw"
    author = ["Miguel Hernández-Cabronero"]
    label = "Curate a directory of PPM files into raw (fixed-length) format"
    tags = {"template", "data compression", "image"}
    tested_on = {"linux"}
