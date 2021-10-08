import warnings

from .xilinx import XilinxPlatform


__all__ = ["Xilinx7SeriesPlatform"]


Xilinx7SeriesPlatform = XilinxPlatform


# TODO(nmigen-0.4): remove
warnings.warn("instead of nmigen.vendor.xilinx_7series.Xilinx7SeriesPlatform, "
              "use nmigen.vendor.xilinx.XilinxPlatform",
              DeprecationWarning, stacklevel=2)
