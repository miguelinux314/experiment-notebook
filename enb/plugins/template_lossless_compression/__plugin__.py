import enb.plugins

class CompressionExperimentTemplate(enb.plugins.Template):
    """Template for lossless and lossy data compression experiments.
    """
    name = "lossless-compression"
    author = ["Miguel Hernández-Cabronero"]
    label = "Template for lossless and lossy data compression experiments"
    tags = {"project", "data compression"}
    tested_on = {"linux"}
    required_fields_to_help = {"user_name": "Your name here"}
