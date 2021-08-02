import enb.plugins

class FapecPlugin(enb.plugins.Plugin):
    name = "fapec"
    label = "Wrappers for FAPEC"
    tags = ["data compression", "codec", "privative"]
    contrib_authors = ["DAPCOM"]
    contrib_reference_urls = ["https://www.dapcom.es/fapec/"]
    extra_requirements_message = """
        WARNING: neither source code nor binaries of this plugin can be distributed by enb. 
        It will be essentially useless unless you can provide the appropriate binaries.
        See https://www.dapcom.es/fapec/ for licensing options.
        """
