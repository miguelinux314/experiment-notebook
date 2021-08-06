#!/usr/bin/env python3
"""The core functionality of enb is extended by means of plugins and templates. These derive from Installable,
a class that by default copies the Installable's source contents and runs the subclass' build() method.
Python libraries available via pip can be defined for Installables, which are attempted to be satisfied before invoking
the build method.

Plugins are conceived self-contained, python modules that can assume the enb library is installed.

- They can be installed into your projects via the enb CLI (e.g., with `enb plugin install <name> <clone_dir>`),
  and then imported like any other module.

- The list of plugins available off-the-box can be obtained using the enb CLI (e.g., with `enb plugin list`).

- Plugins may declare pip dependencies, which are attempted to be satisfied automatically when the plugins
  are installed. In addition, plugins may define their `extra_requirements_message` member to be not None,
  in which case it describes manual intervention required from the user either as a pre-installation
  or post-installation step. That message is shown when attempting to install the plugin with
  not-None `extra_requirements_message`.

- The __init__.py file is automatically generated and should not be present in the source plugin folder.

Templates are very similar to plugins, with a few key differences:

- Templates may require so-called fields in order to produce output.
  Templates without required fields are tagged as "snippet".

- One or more templates can be installed into an existing directory.

- Templates automatically interpret any *.enbt file as a template. The jinja library is used to
  process them, and the resulting files are renamed removing '.enbt' from their name.
"""

from .installable import Installable, import_all_installables, list_all_installables
from .plugin import Plugin, PluginMake

