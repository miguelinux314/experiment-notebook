import enb


class PlotGalleryTemplate(enb.plugins.Template):
    """Template for lossless and lossy data compression experiments.
    """
    name = "analysis-gallery"
    author = ["Miguel Hernández-Cabronero"]
    label = "Self-contained gallery of data analysis and plotting examples."
    tags = {"documentation"}
    tested_on = {"linux", "windows"}