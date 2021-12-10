import warnings

from .xilinx import XilinxPlatform


__all__ = ["Xilinx7SeriesPlatform"]


Xilinx7SeriesPlatform = XilinxPlatform


# TODO(amaranth-0.4): remove
warnings.warn("instead of amaranth.vendor.xilinx_7series.Xilinx7SeriesPlatform, "
              "use amaranth.vendor.xilinx.XilinxPlatform",
              DeprecationWarning, stacklevel=2)
