import os
import sys

import enb.plugins


class TestAllCodecsPlugin(enb.plugins.Template):
    name = "test-codecs"
    authors = ["Miguel Hernández-Cabronero"]
    label = "Install all codec plugins verify their availability"
    contrib_reference_urls = ["https://github.com/miguelinux314/experiment-notebook"]
    tags = {"data compression", "test"}
    tested_on = {"linux"}

    @classmethod
    def build(cls, installation_dir):
        super().build(installation_dir=installation_dir)
        codec_plugins = [cls for cls in enb.plugins.list_all_installables()
                         if "codec" in cls.tags]
        print(f"Found {len(codec_plugins)} codecs:\n\t- ")
        print("\n\t- ".join(p.name for p in codec_plugins))
        print()

        print(f"Installing {len(codec_plugins)} codecs...")
        plugin_dir = os.path.join(installation_dir, "plugins")
        os.makedirs(plugin_dir)
        for plugin in codec_plugins:
            print(f"\t... installing {plugin.name}...")
            plugin.install(os.path.join(plugin_dir, plugin.name))
        print("All codecs installed.")
        print()

        main_script_name = "test_all_codecs.py"
        print(f"You can now run the experiment by executing the {main_script_name} script "
              f"in the installation folder, e.g., with")
        print()
        print(f"\t{os.path.basename(sys.executable)} {os.path.join(installation_dir, main_script_name)} -v")
        print()
