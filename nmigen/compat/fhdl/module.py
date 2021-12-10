from amaranth.compat.fhdl.module import *
from amaranth.compat.fhdl.module import __all__


import warnings
warnings.warn("instead of nmigen.compat.fhdl.module, use amaranth.compat.fhdl.module",
              DeprecationWarning, stacklevel=2)
