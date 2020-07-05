import os, sys
sys.path.insert(0, os.path.abspath("."))

import nmigen

project = "nMigen toolchain"
version = nmigen.__version__
release = version.split("+")[0]
copyright = "2020, nMigen developers"

extensions = [
	"sphinx.ext.intersphinx",
	"sphinx.ext.doctest",
    "sphinx.ext.todo",
    "sphinx_rtd_theme",
    "sphinxcontrib.platformpicker",
]

with open(".gitignore") as f:
    exclude_patterns = [line.strip() for line in f.readlines()]

master_doc = "cover"

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

todo_include_todos = True

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
