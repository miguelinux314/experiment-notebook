import os

import enb.plugins


class TestAllCodecsPlugin(enb.plugins.Plugin):
    name = "test-codecs"
    label = "Install all codec plugins and test their availability"
    contrib_authors = ["The enb library team"]
    contrib_reference_urls = ["https://github.com/miguelinux314/experiment-notebook"]
    tags = ["data compression", "test"]

    @classmethod
    def build(cls, installation_dir):
        super().build(installation_dir=installation_dir)
        codec_plugins = [cls for cls in enb.plugins.list_all_plugins()
                         if "codec" in cls.tags]
        print(f"Found {len(codec_plugins)} codecs:")
        print("\n\t- ".join(p.name for p in codec_plugins))

        print(f"Installing codecs...")
        plugin_dir = os.path.join(installation_dir, "plugins")
        os.makedirs(plugin_dir)
        for plugin in codec_plugins:
            print(f"\t... installing {plugin.name}")
            plugin.install(os.path.join(plugin_dir, plugin.name))

        # Add the __init__.py so that test_all_codecs can import the installed modules
        with open(os.path.join(plugin_dir, "__init__.py"), "w"):
            pass


