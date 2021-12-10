from amaranth.hdl.mem import *
from amaranth.hdl.mem import __all__


import warnings
warnings.warn("instead of nmigen.hdl.mem, use amaranth.hdl.mem",
              DeprecationWarning, stacklevel=2)
