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
    tested_on = {"linux"}
