from amaranth.build.run import *
from amaranth.build.run import __all__


import warnings
warnings.warn("instead of nmigen.build.run, use amaranth.build.run",
              DeprecationWarning, stacklevel=2)
