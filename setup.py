from setuptools import setup, find_packages


def scm_version():
    def local_scheme(version):
        return version.format_choice("+{node}", "+{node}.dirty")
    return {
        "relative_to": __file__,
        "version_scheme": "guess-next-dev",
        "local_scheme": local_scheme
    }


setup(
    name="nmigen",
    use_scm_version=scm_version(),
    author="whitequark",
    author_email="whitequark@whitequark.org",
    description="Python toolbox for building complex digital hardware",
    #long_description="""TODO""",
    license="BSD",
    python_requires="~=3.6",
    setup_requires=["setuptools_scm"],
    install_requires=["setuptools", "pyvcd>=0.1.4", "bitarray", "Jinja2"],
    packages=find_packages(),
    project_urls={
        #"Documentation": "https://nmigen.readthedocs.io/",
        "Source Code": "https://github.com/m-labs/nmigen",
        "Bug Tracker": "https://github.com/m-labs/nmigen/issues",
    },
)
