from amaranth.build.plat import *
from amaranth.build.plat import __all__


import warnings
warnings.warn("instead of nmigen.build.plat, use amaranth.build.plat",
              DeprecationWarning, stacklevel=2)
