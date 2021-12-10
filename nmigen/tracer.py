from amaranth.tracer import *
from amaranth.tracer import __all__


import warnings
warnings.warn("instead of nmigen.tracer, use amaranth.tracer",
              DeprecationWarning, stacklevel=2)
