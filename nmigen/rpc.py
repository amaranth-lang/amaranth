from amaranth.rpc import *
from amaranth.rpc import __all__


import warnings
warnings.warn("instead of nmigen.rpc, use amaranth.rpc",
              DeprecationWarning, stacklevel=2)
