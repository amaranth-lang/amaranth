from amaranth.hdl import *
from amaranth.hdl import __all__


import warnings
warnings.warn("instead of nmigen.hdl, use amaranth.hdl",
              DeprecationWarning, stacklevel=2)
