import enb


class ClusterConfigTemplate(enb.plugins.Template):
    """Template for lossless and lossy data compression experiments.
    """
    name = "cluster-config"
    author = ["Miguel Hernández-Cabronero"]
    label = "Template of a CSV configuration file for enb clusters"
    tags = {"project"}
    tested_on = {"linux"}
