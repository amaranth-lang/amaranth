import os, sys
sys.path.insert(0, os.path.abspath("."))

import time
from importlib.metadata import version as package_version


project = "Amaranth language & toolchain"
version = package_version('amaranth').replace(".editable", "")
release = version.split("+")[0]
copyright = time.strftime("2020—%Y, Amaranth project contributors")

extensions = [
	"sphinx.ext.intersphinx",
	"sphinx.ext.doctest",
    "sphinx.ext.todo",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
    "sphinxcontrib.platformpicker",
]

with open(".gitignore") as f:
    exclude_patterns = [line.strip() for line in f.readlines()]

root_doc = "cover"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "jsonschema": (f"https://python-jsonschema.readthedocs.io/en/v{package_version('jsonschema')}/", None),
}

todo_include_todos = True

autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True
}
autodoc_preserve_defaults = True

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_ivar = True
napoleon_include_init_with_doc = True
napoleon_include_special_with_doc = True
napoleon_custom_sections = ["Platform overrides"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "_static/logo.png"

rst_prolog = """
.. role:: py(code)
   :language: python
"""
