from amaranth.back.verilog import *
from amaranth.back.verilog import __all__


import warnings
warnings.warn("instead of nmigen.back.verilog, use amaranth.back.verilog",
              DeprecationWarning, stacklevel=2)
