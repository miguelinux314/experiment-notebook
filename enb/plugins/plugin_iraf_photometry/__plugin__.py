import os
import enb.plugins


class IRAFPhotometryPlugin(enb.plugins.Plugin):
    name = "iraf_photometry"
    label = "Extra photometry information from image files"
    tags = {"image"}
    contrib_authors = ["IRAF community"]
    contrib_reference_urls = ["https://iraf-community.github.io"]
    required_pip_modules = ["pyraf"]
    tested_on = {"linux"}
    extra_requirements_message = """
        The IRAF photometry plugin requires the `iraf` package and `pyraf` pip module to be installed in your system. 
        In ubuntu/debian/etc it can be installed with `sudo apt install iraf`. 
        It might be available in other distribution repositories as well. 
        You can also install IRAF from the sources available at https://github.com/iraf-community/iraf.
        The pyraf python module can also be installed from pip, but it requires non-automatic configuration.   
        """
