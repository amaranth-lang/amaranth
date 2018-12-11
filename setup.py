import os
from os import path

from setuptools import setup, find_packages


setup(
    name="nmigen",
    version="0.1",
    author="whitequark",
    author_email="whitequark@whitequark.org",
    description="Python toolbox for building complex digital hardware",
    #long_description="""TODO""",
    license="BSD",
    packages=find_packages(),
)
