from ..build import *
from .fpga.lattice_ice40 import LatticeICE40Platform, TinyProgrammerMixin


__all__ = ["TinyFPGABXPlatform"]


class TinyFPGABXPlatform(TinyProgrammerMixin, LatticeICE40Platform):
    device    = "lp8k"
    package   = "cm81"
    clocks    = [
        ("clk16", 16e6),
    ]
    resources = [
        Resource("clk16", 0, Pins("B2", dir="i"),
                 extras={"GLOBAL": 1, "IO_STANDARD": "SB_LVCMOS33"}),

        Resource("user_led", 0, Pins("B3", dir="o"), extras={"IO_STANDARD": "SB_LVCMOS33"}),

        Resource("usb", 0,
            Subsignal("d_p",     Pins("B4", dir="io")),
            Subsignal("d_n",     Pins("A4", dir="io")),
            Subsignal("pull_up", Pins("A3", dir="o")),
            extras={"IO_STANDARD": "SB_LVCMOS33"}
        ),

        Resource("spiflash", 0,
            Subsignal("cs_n", Pins("F7", dir="o")),
            Subsignal("clk",  Pins("G7", dir="o")),
            Subsignal("mosi", Pins("G6", dir="io")),
            Subsignal("miso", Pins("H7", dir="io")),
            extras={"IO_STANDARD": "SB_LVCMOS33"}
        ),
    ]
