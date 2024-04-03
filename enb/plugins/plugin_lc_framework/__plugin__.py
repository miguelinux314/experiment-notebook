import enb.plugins


class LCFrameworkPlugin(enb.plugins.PluginMake):
    name = "lc_framework"
    label = "Wrapper for a LC framework using one unique predefined algorithm"
    tags = {"data compression", "codec"}
    authors = ["Pau Quintas Torra", "Xavier Fernandez Mellado"]
    contrib_authors = ["Martin Burtscher"]
    contrib_reference_urls = ["https://github.com/burtscher/LC-framework"]
    contrib_download_url_name = [
        ("https://github.com/burtscher/LC-framework/archive/refs/heads/main.zip?raw=true",
         "lc-framework.zip")]
    tested_on = {"linux"}
