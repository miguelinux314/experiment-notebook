import enb


class BasicWorkflowTemplate(enb.plugins.Template):
    """Template for lossless and lossy data compression experiments.
    """
    name = "basic-workflow"
    author = ["Miguel Hernández-Cabronero"]
    label = "Basic, self-contained example of enb's workflow"
    tags = {"project", "data compression", "documentation"}
    tested_on = {"linux", "windows"}