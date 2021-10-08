import warnings

from .xilinx import XilinxPlatform


__all__ = ["XilinxUltraScalePlatform"]


XilinxUltraScalePlatform = XilinxPlatform


# TODO(nmigen-0.4): remove
warnings.warn("instead of nmigen.vendor.xilinx_ultrascale.XilinxUltraScalePlatform, "
              "use nmigen.vendor.xilinx.XilinxPlatform",
              DeprecationWarning, stacklevel=2)
