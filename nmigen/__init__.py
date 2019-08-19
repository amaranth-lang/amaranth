from ._version import get_versions
__version__ = get_versions()["full-revisionid"]
del get_versions

from .hdl import *
from .lib import *
