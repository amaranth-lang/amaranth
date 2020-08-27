import warnings

from ..sim import *


__all__ = ["Settle", "Delay", "Tick", "Passive", "Active", "Simulator"]


# TODO(nmigen-0.4): remove
warnings.warn("instead of nmigen.back.pysim.*, use nmigen.sim.*",
              DeprecationWarning, stacklevel=2)
