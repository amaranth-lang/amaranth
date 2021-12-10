from amaranth.build.res import *
from amaranth.build.res import __all__


import warnings
warnings.warn("instead of nmigen.build.res, use amaranth.build.res",
              DeprecationWarning, stacklevel=2)
