from amaranth.sim.core import *
from amaranth.sim.core import __all__


import warnings
warnings.warn("instead of nmigen.sim.core, use amaranth.sim.core",
              DeprecationWarning, stacklevel=2)
