from amaranth.lib.io import *
from amaranth.lib.io import __all__


import warnings
warnings.warn("instead of nmigen.lib.io, use amaranth.lib.io",
              DeprecationWarning, stacklevel=2)
