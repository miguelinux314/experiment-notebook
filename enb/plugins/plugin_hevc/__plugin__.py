import textwrap
import enb.plugins

class HEVCPlugin(enb.plugins.PluginMake):
    name = "hevc"
    label = "Wrapper for the HEVC / H.265 codec"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["ISO", "ITU", "IEC"]
    contrib_reference_urls = ["https://hevc.hhi.fraunhofer.de/"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/HM-master.zip?raw=true",
         "HM-master.zip")]
    extra_requirements_message = textwrap.dedent("""
    The cmake tool is needed to build this plugin, if not present already. 
    You can install cmake as follows: 
    
    * Ubuntu: `sudo apt install cmake`
    * MacOS:
        1. Install homebrew from http://brew.sh
        2. `brew install gcc@9`
    """)
    tested_on = {"linux"}
