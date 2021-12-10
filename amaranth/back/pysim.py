import warnings

from ..sim import *


__all__ = ["Settle", "Delay", "Tick", "Passive", "Active", "Simulator"]


# TODO(amaranth-0.4): remove
warnings.warn("instead of amaranth.back.pysim.*, use amaranth.sim.*",
              DeprecationWarning, stacklevel=2)
