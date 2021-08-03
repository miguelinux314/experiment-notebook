import enb.plugins


class KakaduPlugin(enb.plugins.Plugin):
    name = "kakadu"
    label = "Wrappers for Kakadu JPEG 2000"
    contrib_authors = ["Kakadu Software Pty. Ltd."]
    contrib_reference_urls = ["https://kakadusoftware.com"]
    tags = {"data compression", "codec", "privative"}
    extra_requirements_message = """
    WARNING: neither source code nor binaries of this plugin can be distributed by enb.
    These should be available at https://kakadusoftware.com. 
    It will be essentially useless unless you can provide the appropriate binaries.
    You can refer to this plugin's README.md file for additional installation help.
    """
    tested_on = {"linux"}
