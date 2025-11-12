import enb.plugins


class WebPPlugin(enb.plugins.PluginMake):
    name = "webp"
    label = "Reference implementation of the WebP codec"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["Google Inc."]
    contrib_reference_urls = ["https://chromium.googlesource.com/webm/libwebp"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/libwebp_1.6.0.zip?raw=true",
         "libwebp_1.6.0.zip")]
    tested_on = {"linux"}
