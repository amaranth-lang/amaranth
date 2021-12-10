from amaranth.sim import *
from amaranth.sim import __all__


import warnings
warnings.warn("instead of nmigen.sim, use amaranth.sim",
              DeprecationWarning, stacklevel=2)
