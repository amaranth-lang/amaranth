import warnings

from .lattice_machxo_2_3l import LatticeMachXO2Platform


__all__ = ["LatticeMachXO2Platform"]


# TODO(nmigen-0.4): remove
warnings.warn("instead of nmigen.vendor.lattice_machxo2, use nmigen.vendor.lattice_machxo_2_3l",
              DeprecationWarning, stacklevel=2)
