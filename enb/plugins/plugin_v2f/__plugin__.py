import enb.plugins


class V2FCodecPlugin(enb.plugins.Plugin):
    name = "v2f"
    label = "Plugin allowing compression based on Variable-to-Fixed (V2F) codes (forest)"
    tags = {"data compression", "codec"}
    contrib_authors = ["Miguel Hernández-Cabronero"]
    tested_on = {"linux"}
    extra_requirements_message = "The v2f_compress, v2f_decompress and v2f_verify binaries should be " \
                                 "manually copied to the plugin installation dir."
