import textwrap
import enb.plugins


class NDZIPPlugin(enb.plugins.PluginMake):
    name = "ndzip"
    label = "Wrapper for ndzip"
    tags = {"data compression", "codec"}
    contrib_authors = ["Fabian Knorr"]
    contrib_reference_urls = ["https://github.com/fknorr/ndzip"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/ndzip-master-enb.zip?raw=true",
         "ndzip-master-enb.zip")]
    extra_requirements_message = textwrap.dedent("""
    The following system packages should be installed for this plugin to be able to compile:
    
        - cmake
        - libboost-dev
        - libboost-thread-dev
        - libboost-program-options-dev
    """)
    tested_on = {"linux"}
