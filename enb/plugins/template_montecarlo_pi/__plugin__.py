import enb


class MontecarloPiTemplate(enb.plugins.Template):
    """Experiment that shows how to approximate pi in a distributed way
    (for demonstration purposes only).
    """
    name = "montecarlo-pi"
    author = ["Miguel Hernández-Cabronero"]
    label = "Demo project that approximates pi in a distributed way"
    tags = {"documentation"}
    tested_on = {"linux", "windows"}

    @classmethod
    def build(cls, installation_dir):
        super().build(installation_dir=installation_dir)
        enb.plugins.get_installable_by_name("cluster-config").install(installation_dir=installation_dir)
