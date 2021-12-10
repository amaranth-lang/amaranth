import warnings

from .xilinx import XilinxPlatform


__all__ = ["XilinxSpartan3APlatform", "XilinxSpartan6Platform"]


XilinxSpartan3APlatform = XilinxPlatform
XilinxSpartan6Platform = XilinxPlatform


# TODO(amaranth-0.4): remove
warnings.warn("instead of amaranth.vendor.xilinx_spartan_3_6.XilinxSpartan3APlatform and "
              ".XilinxSpartan6Platform, use amaranth.vendor.xilinx.XilinxPlatform",
              DeprecationWarning, stacklevel=2)
