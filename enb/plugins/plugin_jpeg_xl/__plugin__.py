import textwrap
import enb.plugins


class JPEGXLPlugin(enb.plugins.PluginMake):
    name = "jpegxl"
    label = "Wrapper for a reference JPEG-XL implementation"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["See https://gitlab.com/wg1/jpeg-xl/-/blob/main/CONTRIBUTORS"]
    contrib_reference_urls = ["https://gitlab.com/wg1/jpeg-xl.git"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/jpegxl_git.zip?raw=true",
         "jpegxl_git.zip")]
    extra_requirements_message = textwrap.dedent("""
            The cmake tool is needed to build this plugin, if not present already. 
            You can install cmake as follows: 

            * Ubuntu: `sudo apt install cmake`
            * MacOS:
                1. Install homebrew from http://brew.sh
                2. `brew install gcc@9`
                
            Also, if execution fails due to the lack of libraries such as `libjxl_threads.so.0.8`, 
            you may need to manually compile the plugin and copy the resulting libraries, e.g., in `/usr/lib`. 
            """)
    tested_on = {"linux"}
