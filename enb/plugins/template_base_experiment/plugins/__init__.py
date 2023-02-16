import os
import importlib
import glob

# By default, all modules under this folder are imported
for plugin_dir in (os.path.abspath(path)
                   for path in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "*"))
                   if os.path.isdir(path) and os.path.isfile(os.path.join(path, f"__init__.py"))):
    importlib.import_module(f"{os.path.basename(os.path.dirname(os.path.abspath(__file__)))}"
                            f".{os.path.basename(plugin_dir)}")
