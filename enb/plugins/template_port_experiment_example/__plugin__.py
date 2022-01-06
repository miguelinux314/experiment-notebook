import enb


class PortExperimentTemplate(enb.plugins.Template):
    """Self-contained example using the basic usage of enb's experiment class
    """
    name = "port-experiment-example"
    author = ["Miguel Hernández-Cabronero"]
    label = "Self-contained port scanning experiment example"
    tags = {"documentation"}
    tested_on = {"linux", "windows"}