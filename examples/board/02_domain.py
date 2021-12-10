# If more control over clocking and resets is required, a "sync" clock domain could be created
# explicitly, which overrides the default behavior. Any other clock domains could also be
# independently created in addition to the main "sync" domain.

from amaranth import *
from amaranth_boards.ice40_hx1k_blink_evn import *


class BlinkyWithDomain(Elaboratable):
    def elaborate(self, platform):
        clk3p3 = platform.request("clk3p3")
        led    = platform.request("led", 0)
        timer  = Signal(20)

        m = Module()
        m.domains.sync = ClockDomain()
        m.d.comb += ClockSignal().eq(clk3p3.i)
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += led.o.eq(timer[-1])
        return m


if __name__ == "__main__":
    platform = ICE40HX1KBlinkEVNPlatform()
    platform.build(BlinkyWithDomain(), do_program=True)
