import warnings

from .xilinx import XilinxPlatform


__all__ = ["XilinxUltraScalePlatform"]


XilinxUltraScalePlatform = XilinxPlatform


# TODO(amaranth-0.4): remove
warnings.warn("instead of amaranth.vendor.xilinx_ultrascale.XilinxUltraScalePlatform, "
              "use amaranth.vendor.xilinx.XilinxPlatform",
              DeprecationWarning, stacklevel=2)
