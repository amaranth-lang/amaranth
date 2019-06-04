from ...build import *
from ..fpga.lattice_ice40 import LatticeICE40Platform, TinyProgrammerMixin


__all__ = ["TinyFPGABXPlatform"]


class TinyFPGABXPlatform(TinyProgrammerMixin, LatticeICE40Platform):
    device     = "lp8k"
    package    = "cm81"
    clocks     = [
        ("clk16", 16e6),
    ]
    resources  = [
        Resource("clk16", 0, Pins("B2", dir="i"),
                 extras={"GLOBAL": "1", "IO_STANDARD": "SB_LVCMOS33"}),

        Resource("user_led", 0, Pins("B3", dir="o"), extras={"IO_STANDARD": "SB_LVCMOS33"}),

        Resource("usb", 0,
            Subsignal("d_p",    Pins("B4", dir="io")),
            Subsignal("d_n",    Pins("A4", dir="io")),
            Subsignal("pullup", Pins("A3", dir="o")),
            extras={"IO_STANDARD": "SB_LVCMOS33"}
        ),

        Resource("spiflash", 0,
            Subsignal("cs_n", Pins("F7", dir="o")),
            Subsignal("clk",  Pins("G7", dir="o")),
            Subsignal("mosi", Pins("G6", dir="o")),
            Subsignal("miso", Pins("H7", dir="i")),
            Subsignal("wp",   Pins("H4", dir="o")),
            Subsignal("hold", Pins("J8", dir="o")),
            extras={"IO_STANDARD": "SB_LVCMOS33"}
        ),

        Resource("spiflash4x", 0,
            Subsignal("cs_n", Pins("F7", dir="o")),
            Subsignal("clk",  Pins("G7", dir="o")),
            Subsignal("dq",   Pins("G6 H7 H4 J8", dir="io")),
            extras={"IO_STANDARD": "SB_LVCMOS33"}
        ),
    ]
    connectors = [
        Connector("gpio", 0,
            # Left side of the board
            #     1  2  3  4  5  6  7  8  9 10 11 12 13
             "   A2 A1 B1 C2 C1 D2 D1 E2 E1 G2 H1 J1 H2"
            # Right side of the board
            #          14 15 16 17 18 19 20 21 22 23 24
             "         H9 D9 D8 B8 A9 B8 A8 B7 A7 B6 A6"
            # Bottom of the board
            # 25 26 27 28 29 30 31
             "G1 J3 J4 G9 J9 E8 J2"),
    ]
