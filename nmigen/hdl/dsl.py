from amaranth.hdl.dsl import *
from amaranth.hdl.dsl import __all__


import warnings
warnings.warn("instead of nmigen.hdl.dsl, use amaranth.hdl.dsl",
              DeprecationWarning, stacklevel=2)
