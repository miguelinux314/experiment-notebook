import os
import shutil
import sys

import enb.plugins


class TestAllCodecsPlugin(enb.plugins.Template):
    name = "test-codecs"
    authors = ["Miguel Hernández-Cabronero"]
    label = "Install all codec plugins verify their availability"
    contrib_reference_urls = ["https://github.com/miguelinux314/experiment-notebook"]
    tags = {"data compression", "image", "test"}
    tested_on = {"linux"}
    required_fields_to_help = {"include_privative_codecs": "It indicates whether privative codecs "
                                                           "(those for which codec binaries and sources are not available) "
                                                           "are included in the test.\n"
                                                           "Must be 'True' or 'False'. "}

    @classmethod
    def build(cls, installation_dir):
        super().build(installation_dir=installation_dir)
        codec_plugins = [c for c in enb.plugins.list_all_installables() if "codec" in c.tags]
        print(f"Found {len(codec_plugins)} codecs:\n\t- ", end="")
        print("\n\t- ".join(p.name for p in codec_plugins))
        print()

        print(f"Installing {len(codec_plugins)} codecs...")
        plugin_dir = os.path.join(installation_dir, "plugins")
        os.makedirs(plugin_dir)

        for plugin in codec_plugins:
            assert cls.get_fields()["include_privative_codecs"] == "True" or cls.get_fields()[
                "include_privative_codecs"] == "False", \
                f"Invalid choice for 'include_privative_codecs': {cls.get_fields()['include_privative_codecs']}"
            if "privative" in plugin.tags and cls.get_fields()["include_privative_codecs"] == "False":
                print(f"\t... skipping privative {plugin.name}")
                continue
            print("\n" + "-"*shutil.get_terminal_size().columns + "\n")
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
