from setuptools import setup
from setuptools_scm.git import parse as parse_git


def doc_version():
    git = parse_git(".")
    if not git:
        return ""
    elif git.exact:
        return git.format_with("v{tag}")
    else:
        return "latest"


setup(
    project_urls={
        "Homepage": "https://amaranth-lang.org/",
        "Documentation": "https://amaranth-lang.org/docs/amaranth/{}".format(doc_version()),
        "Source Code": "https://github.com/amaranth-lang/amaranth",
        "Bug Tracker": "https://github.com/amaranth-lang/amaranth/issues",
    },
)
