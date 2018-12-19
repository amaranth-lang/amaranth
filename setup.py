import sys
from setuptools import setup, find_packages


if sys.version_info[:3] < (3, 6):
    raise SystemExit("nMigen requires Python 3.6+")


setup(
    name="nmigen",
    version="0.1",
    author="whitequark",
    author_email="whitequark@whitequark.org",
    description="Python toolbox for building complex digital hardware",
    #long_description="""TODO""",
    license="BSD",
    install_requires=["pyvcd>=0.1.4", "bitarray"],
    packages=find_packages(),
    project_urls={
        #"Documentation": "https://glasgow.readthedocs.io/",
        "Source Code": "https://github.com/m-labs/nmigen",
        "Bug Tracker": "https://github.com/m-labs/nmigen/issues",
    }
)
