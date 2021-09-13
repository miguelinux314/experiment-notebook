import enb.plugins


class FLIFPlugin(enb.plugins.PluginMake):
    name = "flif"
    label = "Wrapper for the FLIF compressor"
    tags = {"data compression", "codec"}
    contrib_authors = ["The FLIF community"]
    contrib_reference_urls = ["https://flif.info"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/flif_0.3_2017.zip?raw=true",
         "flif_0.3_2017.zip")]
    extra_requirements_message = """
    Additional packages are needed for this plugin. These need to be installed via pip, pacman, or 
    whatever system package manager you use. 
    
    Instructions for several linux distributions are shown next, copied from 
    the README.md provided in the original package:
        
      * Debian: `sudo apt update; sudo apt-get install libpng-dev`
      * Ubuntu: `sudo apt update; sudo apt install -y libpng-dev make pgk-config`
      * Fedora: `sudo apt update; sudo dnf install libpng-devel`
    
    Instructions for Windows, MacOS and others can also be found in the README.md file.        
    """
    tested_on = {"linux"}
