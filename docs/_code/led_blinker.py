from amaranth import *


class LEDBlinker(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        led = platform.request("led")

        half_freq = int(platform.default_clk_period.hertz // 2)
        timer = Signal(range(half_freq + 1))

        with m.If(timer == half_freq):
            m.d.sync += led.o.eq(~led.o)
            m.d.sync += timer.eq(0)
        with m.Else():
            m.d.sync += timer.eq(timer + 1)

        return m
# --- BUILD ---
from amaranth_boards.icestick import ICEStickPlatform


ICEStickPlatform().build(LEDBlinker(), do_program=True)
