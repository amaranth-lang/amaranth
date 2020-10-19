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
    if git.exact:
        return git.format_with("{tag}")
    else:
        return "latest"


setup(
    name="nmigen",
    use_scm_version=scm_version(),
    author="whitequark",
    author_email="whitequark@whitequark.org",
    description="Python toolbox for building complex digital hardware",
    #long_description="""TODO""",
    license="BSD",
    python_requires="~=3.6",
    setup_requires=["wheel", "setuptools", "setuptools_scm"],
    install_requires=[
        "importlib_metadata; python_version<'3.8'",  # for __version__ and nmigen._yosys
        "importlib_resources; python_version<'3.9'", # for nmigen._yosys
        "pyvcd~=0.2.2", # for nmigen.pysim
        "Jinja2~=2.11", # for nmigen.build
    ],
    extras_require={
        # this version requirement needs to be synchronized with the one in nmigen.back.verilog!
        "builtin-yosys": ["nmigen-yosys>=0.9.post3527.*"],
        "remote-build": ["paramiko~=2.7"],
    },
    packages=find_packages(exclude=["tests*"]),
    entry_points={
        "console_scripts": [
            "nmigen-rpc = nmigen.rpc:main",
        ]
    },
    project_urls={
        "Documentation": "https://nmigen.info/nmigen/{}".format(doc_version()),
        "Source Code": "https://github.com/nmigen/nmigen",
        "Bug Tracker": "https://github.com/nmigen/nmigen/issues",
    },
)
