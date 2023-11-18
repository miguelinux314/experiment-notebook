import textwrap
import enb.plugins


class MarlinPlugin(enb.plugins.PluginMake):
    name = "marlin"
    label = "Marlin-based image compressor"
    tags = {"data compression", "codec"}
    contrib_authors = ["Manuel Martínez Torres", "Miguel Hernández-Cabronero"]
    contrib_reference_urls = ["https://github.com/miguelinux314/marlin"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/marlin_ubuntu20_git.zip?raw=true",
         "marlin_ubuntu20_git.zip")]
    extra_requirements_message = textwrap.dedent("""
            The cmake tool is needed to build this plugin, if not present already. 
            You can install cmake as follows: 

            * Ubuntu: `sudo apt install cmake`
            * MacOS:
                1. Install homebrew from http://brew.sh
                2. `brew install gcc@9`
            """)
    tested_on = {"linux"}
