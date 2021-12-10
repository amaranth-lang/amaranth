import warnings

from .lattice_machxo_2_3l import LatticeMachXO2Platform


__all__ = ["LatticeMachXO2Platform"]


# TODO(amaranth-0.4): remove
warnings.warn("instead of amaranth.vendor.lattice_machxo2, use amaranth.vendor.lattice_machxo_2_3l",
              DeprecationWarning, stacklevel=2)
