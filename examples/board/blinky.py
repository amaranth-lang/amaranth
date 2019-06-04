from nmigen import *
from nmigen_boards.ice40_hx1k_blink_evn import *


class Blinky(Elaboratable):
    def elaborate(self, platform):
        clk3p3   = platform.request("clk3p3")
        user_led = platform.request("user_led", 0)
        counter  = Signal(20)

        m = Module()
        m.domains.sync = ClockDomain()
        m.d.comb += ClockSignal().eq(clk3p3.i)
        m.d.sync += counter.eq(counter + 1)
        m.d.comb += user_led.o.eq(counter[-1])
        return m


if __name__ == "__main__":
    platform = ICE40HX1KBlinkEVNPlatform()
    platform.build(Blinky(), do_program=True)
