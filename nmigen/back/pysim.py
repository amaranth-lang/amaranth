import warnings

from ..sim.pysim import *


__all__ = ["Settle", "Delay", "Tick", "Passive", "Active", "Simulator"]


# TODO(nmigen-0.4): remove
warnings.warn("instead of back.pysim, use sim.pysim",
              DeprecationWarning, stacklevel=2)
