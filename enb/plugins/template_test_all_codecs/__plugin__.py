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
        print(f"Found the following {len(codec_plugins)} codecs to be installed:\n\t- ", end="")
        print("\n\t- ".join(p.name for p in codec_plugins))
        print()
        plugin_dir = os.path.join(installation_dir, "plugins")
        os.makedirs(plugin_dir)

        codecname_exception_list = []
        for plugin in codec_plugins:
            assert cls.get_fields()["include_privative_codecs"] == "True" or cls.get_fields()[
                "include_privative_codecs"] == "False", \
                f"Invalid choice for 'include_privative_codecs': {cls.get_fields()['include_privative_codecs']}"
            if "privative" in plugin.tags and cls.get_fields()["include_privative_codecs"] == "False":
                print(f"\t... skipping privative {plugin.name}")
                continue
            print("\n" + "-"*shutil.get_terminal_size().columns + "\n")
            print(f"\t... installing {repr(plugin.name)}...")
            try:
                plugin.install(os.path.join(plugin_dir, plugin.name))
            except Exception as ex:
                codecname_exception_list.append((plugin.name, ex))
        if not codecname_exception_list:
            print("\nAll codecs successfully installed!")
        else:
            print(f"Plugin was only {repr(cls.name)} partially installed. "
                  "Errors were found installing the following codecs. "
                  "You may need to install them manually:\n\n\t-"
                  + ("\n\n"+"-"*shutil.get_terminal_size().columns+"\n\t-").join(f"{codec_name}: {ex}"
                                               for codec_name, ex in codecname_exception_list))
        print()

        main_script_name = "test_all_codecs.py"
        print(f"You can now run the experiment by executing the {main_script_name} script "
              f"in the installation folder, e.g., with")
        print()
        print(f"\t{os.path.basename(sys.executable)} "
              f"{os.path.join(installation_dir, main_script_name)} -v")
        print()
        if codecname_exception_list:
            print("Note that only successfully installed codecs will be part of the experiment, "
                  "but "
                  + ", ".join(repr(codec_name) for codec_name, _ in codecname_exception_list)
                  + " will not.")
            print()
