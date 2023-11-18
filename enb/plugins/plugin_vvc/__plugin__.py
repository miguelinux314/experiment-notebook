import textwrap
import enb.plugins


class VVCPlugin(enb.plugins.PluginMake):
    name = "vvc"
    label = "Wrapper for the VVC / H.266 codec"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["ISO", "ITU", "IEC"]
    contrib_reference_urls = ["https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM/-/tree/master"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/"
         "VVCSoftware_VTM-VTM-15.0.zip?raw=true",
         "VVCSoftware_VTM-master.zip")]
    extra_requirements_message = textwrap.dedent("""
    The cmake tool is needed to build this plugin, if not present already. 
    You can install cmake as follows: 
    
    * Ubuntu: `sudo apt install cmake`
    * MacOS:
        1. Install homebrew from http://brew.sh
        2. `brew install gcc@9`
    """)
    tested_on = {"linux"}
