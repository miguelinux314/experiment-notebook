import enb.plugins


class V2FCodecPlugin(enb.plugins.Plugin):
    name = "v2f"
    label = "Wrapper of a codec based on V2F forests"
    tags = {"data compression", "codec", "privative"}
    contrib_authors = ["Miguel Hernández-Cabronero"]
    tested_on = {"linux"}
    extra_requirements_message = "The v2f_compress, v2f_decompress and v2f_verify binaries should be " \
                                 "manually copied to the plugin installation dir."
