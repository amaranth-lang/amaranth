from amaranth.compat.sim import *
from amaranth.compat.sim import __all__


import warnings
warnings.warn("instead of nmigen.compat.sim, use amaranth.compat.sim",
              DeprecationWarning, stacklevel=2)
