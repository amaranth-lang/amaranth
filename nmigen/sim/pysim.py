from amaranth.sim.pysim import *
from amaranth.sim.pysim import __all__


import warnings
warnings.warn("instead of nmigen.sim.pysim, use amaranth.sim.pysim",
              DeprecationWarning, stacklevel=2)
