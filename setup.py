from setuptools import setup, find_packages


if sys.version_info[:3] < (3, 7):
    raise SystemExit("nMigen requires Python 3.7+")


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
