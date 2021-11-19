import enb


class PortExperimentTemplate(enb.plugins.Template):
    """Template for lossless and lossy data compression experiments.
    """
    name = "port-experiment-example"
    author = ["Miguel Hernández-Cabronero"]
    label = "Self-contained example using the basic usage of enb's experiment class"
    tags = {"data compression", "documentation"}
    tested_on = {"linux"}
