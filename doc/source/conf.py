# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))
import os
import sys
import zipfile
import glob
import shutil
import subprocess
import enb
sys.path.insert(0, os.path.realpath(os.path.join(os.path.abspath('..'), '..')))

# -- Project information -----------------------------------------------------

project = "Experiment Notebook (enb)"
version = f"v{enb.config.ini.get_key('enb', 'version')}"
release = version
copyright = f"2020-*, Miguel Hernández-Cabronero"
author = "Miguel Hernández-Cabronero, et al."

# The full version, including alpha/beta/rc tags
release = 'MIT License'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinxcontrib.programoutput",
]

intersphinx_mapping = {
    'pandas': ('https://pandas.pydata.org/pandas-docs/dev', None),
    'ray': ('https://docs.ray.io/en/master/', None)
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

def skip(app, what, name, obj, would_skip, options):
    if name.startswith("_") and not name in ("__init__",):
        return True
    if any(name == s for s in ("__doc__", "__dict__", "__module__")):
        return True

    return False

def setup(app):
    app.connect("autodoc-skip-member", skip)

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_css_files = [
    'css/enb-rtd.css',
]


#
html_context = {
    'display_github': True,
}

html_theme_options = {
    'display_version': True,
}

rst_prolog = """
:github_url: https://github.com/miguelinux314/experiment-notebook
"""

html_logo = "img/enb_logo_small.png"

# pygments_style = "gruvbox-light"
pygments_style = "zenburn"

# Re-generate module autodoc
cwd = os.getcwd()
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
shutil.rmtree("doc/source/api/", ignore_errors=True)
invocation = "sphinx-apidoc -o doc/source/api enb"
status, output = subprocess.getstatusoutput(invocation)
if status != 0:
    raise Exception(f"Status = {status} != 0.\n"
                    f"Input=[{invocation}].\n"
                    f"Output=[{output}]")
os.chdir(cwd)
