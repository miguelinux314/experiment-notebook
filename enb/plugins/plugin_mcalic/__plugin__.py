import os
import stat
import glob
import enb.plugins


class MCALICPlugin(enb.plugins.Plugin):
    name = "mcalic"
    label = "Wrapper for E. Magli et al.'s M-CALIC codec"
    tags = {"data compression", "image", "codec"}
    contrib_authors = ["Enrico Magli et al."]
    contrib_reference_urls = ["https://doi.org/10.1109/LGRS.2003.822312"]
    contrib_download_url_name = [
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/mcalic/Mcalic_enc_nl?raw=true",
         "Mcalic_enc_nl"),
        ("https://github.com/miguelinux314/experiment-notebook/blob/dev/contrib/mcalic/Mcalic_dec_nl?raw=true",
         "Mcalic_dec_nl"),
    ]
    tested_on = {"linux"}
    
    @classmethod
    def build(cls, installation_dir):
        super().build(installation_dir)
        for path in glob.glob(os.path.join(installation_dir, "*")):
            if any(os.path.basename(path) in p for p in ("Mcalic_dec_nl", "Mcalic_enc_nl")):
                os.chmod(path, stat.S_IREAD | stat.S_IEXEC)
            