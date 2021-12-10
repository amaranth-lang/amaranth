from amaranth.lib.scheduler import *
from amaranth.lib.scheduler import __all__


import warnings
warnings.warn("instead of nmigen.lib.scheduler, use amaranth.lib.scheduler",
              DeprecationWarning, stacklevel=2)
