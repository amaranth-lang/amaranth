from setuptools import setup


def doc_version():
    try:
        from setuptools_scm.git import parse as parse_git
        git = parse_git(".")
        if git.exact:
            return git.format_with("v{tag}")
        else:
            return "latest"
    except ImportError:
        # PEP 517 compliant build tools will never reach this code path.
        # Poetry reaches this code path.
        return ""


setup(
    project_urls={
        "Homepage": "https://amaranth-lang.org/",
        "Documentation": "https://amaranth-lang.org/docs/amaranth/{}".format(doc_version()),
        "Source Code": "https://github.com/amaranth-lang/amaranth",
        "Bug Tracker": "https://github.com/amaranth-lang/amaranth/issues",
    },
)
