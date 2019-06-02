from ..build import *
from .fpga.lattice_ice40 import LatticeICE40Platform, IceStormProgrammerMixin


__all__ = ["ICEStickPlatform"]


class ICEStickPlatform(IceStormProgrammerMixin, LatticeICE40Platform):
    device    = "hx1k"
    package   = "tq144"
    clocks    = [
        ("clk12", 12e6),
    ]
    resources = [
        Resource("clk12", 0, Pins("21", dir="i"), extras=["IO_STANDARD=SB_LVCMOS33"]),

        Resource("user_led", 0, Pins("99", dir="o"), extras=["IO_STANDARD=SB_LVCMOS33"]),
        Resource("user_led", 1, Pins("98", dir="o"), extras=["IO_STANDARD=SB_LVCMOS33"]),
        Resource("user_led", 2, Pins("97", dir="o"), extras=["IO_STANDARD=SB_LVCMOS33"]),
        Resource("user_led", 3, Pins("96", dir="o"), extras=["IO_STANDARD=SB_LVCMOS33"]),
        Resource("user_led", 4, Pins("95", dir="o"), extras=["IO_STANDARD=SB_LVCMOS33"]),

        Resource("serial", 0,
            Subsignal("rx",  Pins("9", dir="i")),
            Subsignal("tx",  Pins("8", dir="o")),
            Subsignal("rts", Pins("7", dir="o")),
            Subsignal("cts", Pins("4", dir="i")),
            Subsignal("dtr", Pins("3", dir="o")),
            Subsignal("dsr", Pins("2", dir="i")),
            Subsignal("dcd", Pins("1", dir="i")),
            extras=["IO_STANDARD=SB_LVTTL", "PULLUP=1"],
        ),

        Resource("irda", 0,
            Subsignal("rx", Pins("106", dir="i")),
            Subsignal("tx", Pins("105", dir="o")),
            Subsignal("sd", Pins("107", dir="o")),
            extras=["IO_STANDARD=SB_LVCMOS33"]
        ),

        Resource("spiflash", 0,
            Subsignal("cs_n", Pins("71", dir="o")),
            Subsignal("clk",  Pins("70", dir="o")),
            Subsignal("mosi", Pins("67", dir="io")),
            Subsignal("miso", Pins("68", dir="io")),
            extras=["IO_STANDARD=SB_LVCMOS33"]
        ),
    ]
    prog_mode = "flash"
