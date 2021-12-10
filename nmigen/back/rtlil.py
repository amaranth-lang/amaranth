from amaranth.back.rtlil import *
from amaranth.back.rtlil import __all__


import warnings
warnings.warn("instead of nmigen.back.rtlil, use amaranth.back.rtlil",
              DeprecationWarning, stacklevel=2)
