from amaranth.back.pysim import *
from amaranth.back.pysim import __all__


import warnings
warnings.warn("instead of nmigen.back.pysim, use amaranth.back.pysim",
              DeprecationWarning, stacklevel=2)
