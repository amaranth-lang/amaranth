from amaranth.lib.fifo import *
from amaranth.lib.fifo import __all__


import warnings
warnings.warn("instead of nmigen.lib.fifo, use amaranth.lib.fifo",
              DeprecationWarning, stacklevel=2)
