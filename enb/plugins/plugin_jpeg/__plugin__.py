import enb.plugins


class JPEGPlugin(enb.plugins.PluginMake):
    name = "jpeg"
    label = "Reference JPEG and JPEG-LS implementation"
    tags = {"data compression", "codec"}
    contrib_authors = ["Thomas Richter"]
    contrib_reference_urls = ["https://github.com/thorfdbg/libjpeg/"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/libjpeg-master-1.59.zip?raw=true",
         "libjpeg-master-1.59.zip")]
    tested_on = {"linux"}
