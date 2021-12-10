from amaranth.cli import main, main_parser, main_runner
from amaranth.cli import __all__


import warnings
warnings.warn("instead of nmigen.cli, use amaranth.cli",
              DeprecationWarning, stacklevel=2)
