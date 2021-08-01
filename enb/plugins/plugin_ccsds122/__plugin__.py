import enb.plugins

class CCSDS122Plugin(enb.plugins.Plugin):
    name = "ccsds122.1"
    label = "Wrappers for CCSDS 122.1 codec implementations"
    contrib_authors = ["Consultative Committee for Space Data Systems (CCSDS)"]
    contrib_reference_urls = ["https://ccsds.org"]

    @classmethod
    def install(cls, installation_dir):
        print("Warning: neither source code nor binaries of this plugin can be distributed by enb. "
              "It will be essentially useless unless you can provide the appropriate binaries.")
        super().install(installation_dir=installation_dir)
