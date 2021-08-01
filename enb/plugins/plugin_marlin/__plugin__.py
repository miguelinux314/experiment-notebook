import enb.plugins

class MarlinPlugin(enb.plugins.Plugin):
    name = "marlin"
    label = "Marlin-based image compressor"
    contrib_authors = ["Manuel Martínez Torres", "Miguel Hernández-Cabronero"]
    contrib_reference_urls = ["https://github.com/miguelinux314/marlin"]
    contrib_download_url_name = [()]


    @classmethod
    def install(cls, installation_dir):
        super().install(installation_dir=installation_dir)
