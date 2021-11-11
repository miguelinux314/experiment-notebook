import enb


class BasicWorkflowTemplate(enb.plugins.Template):
    """Template for lossless and lossy data compression experiments.
    """
    name = "experiment-example"
    author = ["Miguel Hernández-Cabronero"]
    label = "Self-contained example of a simple enb's experiment."
    tags = {"project", "data compression", "template"}
    tested_on = {"linux"}
