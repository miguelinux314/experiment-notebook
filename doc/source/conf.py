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
sys.path.insert(0, os.path.realpath(os.path.join(os.path.abspath('..'), '..')))

# -- Project information -----------------------------------------------------

project = 'Experiment Notebook'
copyright = '2020, Miguel Hernández-Cabronero'
author = 'Miguel Hernández-Cabronero'

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
]

intersphinx_mapping = {
    'pandas': ('http://pandas.pydata.org/pandas-docs/dev', None),
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_logo = "img/enb_logo_small.png"

# Output static examples
# Basic example
if not os.path.exists("_static/example_basic_workflow.zip") \
        or not os.path.exists("_static/distribution_line_count.pdf") \
        or not os.path.exists("_static/persistence_basic_workflow.csv") \
        or not os.path.exists("_static/distribution_word_count.pdf"):
    cwd = os.getcwd()
    os.chdir("examples")
    invocation = "./basic_workflow.py"
    status, output = subprocess.getstatusoutput(invocation)
    if status != 0:
        raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
            status, invocation, output))
    status, output = subprocess.getstatusoutput(invocation)
    if status != 0:
        raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
            status, invocation, output))
    os.chdir(cwd)

    # Basic Workflow Example
    shutil.copy("examples/plots/distribution_line_count.pdf", "_static")
    shutil.copy("examples/plots/distribution_word_count.pdf", "_static")
    shutil.copy("examples/persistence_basic_workflow.csv", "_static")
    with zipfile.ZipFile("_static/example_basic_workflow.zip", "w") as zip_file:
        zip_file.write("examples/basic_workflow.py", arcname="basic_workflow.py")
        for f in glob.glob("examples/data/wiki/*"):
            zip_file.write(f, arcname=f.replace("examples/", ""))

            
# Re-generate module autodoc
cwd = os.getcwd()
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

shutil.rmtree("doc/source/api/")
invocation = "sphinx-apidoc -o doc/source/api enb"
status, output = subprocess.getstatusoutput(invocation)
if status != 0:
    raise Exception("Status = {} != 0.\nInput=[{}].\nOutput=[{}]".format(
        status, invocation, output))
os.chdir(cwd)