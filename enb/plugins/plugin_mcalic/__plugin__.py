import enb.plugins


class MCALICPlugin(enb.plugins.Plugin):
    name = "mcalic"
    label = "Wraper for E. Magli et al.'s M-CALIC codec"
    tags = {"data compression", "codec"}
    contrib_authors = ["Enrico Magli et al."]
    contrib_reference_urls = ["https://doi.org/10.1109/LGRS.2003.822312"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/mcalic/Mcalic_enc_nl?raw=true",
         "Mcalic_enc_nl"),
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/mcalic/Mcalic_dec_nl?raw=true",
         "Mcalic_dec_nl"),
    ]
    tested_on = {"linux"}
