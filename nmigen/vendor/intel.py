from amaranth.vendor.intel import *
from amaranth.vendor.intel import __all__


import warnings
warnings.warn("instead of nmigen.vendor.intel, use amaranth.vendor.intel",
              DeprecationWarning, stacklevel=2)
