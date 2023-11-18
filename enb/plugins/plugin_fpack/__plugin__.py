import textwrap
import enb.plugins

class FPackPlugin(enb.plugins.PluginMake):
    name = "fpack"
    label = "Wrapper for the FPACK compressor"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["William D. Pence"]
    contrib_reference_urls = ["https://heasarc.gsfc.nasa.gov/fitsio/fpack/"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/"
         "cfitsio-3.49.tar.gz?raw=true",
         "cfitsio-3.49.tar.gz")]
    extra_requirements_message = textwrap.dedent("""
        The cmake tool is needed to build this plugin, if not present already. 
        You can install cmake as follows: 

        * Ubuntu: `sudo apt install cmake`
        * MacOS:
            1. Install homebrew from http://brew.sh
            2. `brew install gcc@9`
        """)
    tested_on = {"linux"}
