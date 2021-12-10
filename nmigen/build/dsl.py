from amaranth.build.dsl import *
from amaranth.build.dsl import __all__


import warnings
warnings.warn("instead of nmigen.build.dsl, use amaranth.build.dsl",
              DeprecationWarning, stacklevel=2)
