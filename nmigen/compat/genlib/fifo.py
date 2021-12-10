from amaranth.compat.genlib.fifo import *
from amaranth.compat.genlib.fifo import __all__


import warnings
warnings.warn("instead of nmigen.compat.genlib.fifo, use amaranth.compat.genlib.fifo",
              DeprecationWarning, stacklevel=2)
