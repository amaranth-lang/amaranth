from amaranth.hdl.ast import *
from amaranth.hdl.ast import __all__


import warnings
warnings.warn("instead of nmigen.hdl.ast, use amaranth.hdl.ast",
              DeprecationWarning, stacklevel=2)
