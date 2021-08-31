import enb.plugins


class KakaduPlugin(enb.plugins.Plugin):
    name = "kakadu"
    label = "Wrappers for Kakadu JPEG 2000"
    contrib_authors = ["Kakadu Software Pty. Ltd."]
    contrib_reference_urls = ["https://kakadusoftware.com"]
    tags = {"data compression", "codec", "privative"}
    tested_on = {"linux"}
