from setuptools import setup, find_packages


def scm_version():
    def local_scheme(version):
        if version.tag and not version.distance:
            return version.format_with("")
        else:
            return version.format_choice("+{node}", "+{node}.dirty")
    return {
        "relative_to": __file__,
        "version_scheme": "guess-next-dev",
        "local_scheme": local_scheme
    }


def doc_version():
    try:
        from setuptools_scm.git import parse as parse_git
    except ImportError:
        return ""

    git = parse_git(".")
    if not git:
        return ""
    elif git.exact:
        return git.format_with("v{tag}")
    else:
        return "latest"


setup(
    name="amaranth",
    use_scm_version=scm_version(),
    author="whitequark",
    author_email="whitequark@whitequark.org",
    description="Amaranth hardware definition language",
    #long_description="""TODO""",
    license="BSD",
    python_requires="~=3.6",
    setup_requires=["wheel", "setuptools", "setuptools_scm"],
    install_requires=[
        "importlib_metadata; python_version<'3.8'",  # for __version__ and amaranth._toolchain.yosys
        "importlib_resources; python_version<'3.9'", # for amaranth._toolchain.yosys
        "pyvcd~=0.2.2", # for amaranth.pysim
        "Jinja2~=3.0",  # for amaranth.build
    ],
    extras_require={
        # this version requirement needs to be synchronized with the one in amaranth.back.verilog!
        "builtin-yosys": ["amaranth-yosys>=0.10.*"],
        "remote-build": ["paramiko~=2.7"],
    },
    packages=find_packages(exclude=("tests", "tests.*")),
    entry_points={
        "console_scripts": [
            "amaranth-rpc = amaranth.rpc:main",
            "nmigen-rpc = nmigen.rpc:main",
        ]
    },
    project_urls={
        "Documentation": "https://amaranth-lang.org/docs/amaranth/{}".format(doc_version()),
        "Source Code": "https://github.com/amaranth-lang/amaranth",
        "Bug Tracker": "https://github.com/amaranth-lang/amaranth/issues",
    },
)
