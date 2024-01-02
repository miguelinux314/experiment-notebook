import enb


class ClusterConfigTemplate(enb.plugins.Template):
    """Template for lossless and lossy data compression experiments.
    """
    name = "cluster-config"
    author = ["Miguel Hernández-Cabronero"]
    label = "Template of a CSV configuration file for enb clusters"
    tags = {"project"}
    tested_on = {"linux"}
    extra_requirements_message = ("You will need to use the `--ssh_csv=enb_cluster.csv` "
                                  "option in the command line, or add/update an .ini file such as enb.ini.\n"
                                  "See the 'enb.ini' plugin and the user manual for more info.")
