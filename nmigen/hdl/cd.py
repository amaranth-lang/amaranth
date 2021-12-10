from amaranth.hdl.cd import *
from amaranth.hdl.cd import __all__


import warnings
warnings.warn("instead of nmigen.hdl.cd, use amaranth.hdl.cd",
              DeprecationWarning, stacklevel=2)
