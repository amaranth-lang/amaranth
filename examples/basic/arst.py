from amaranth import *
from amaranth.cli import main


class ClockDivisor(Elaboratable):
    def __init__(self, factor):
        self.v = Signal(factor)
        self.o = Signal()

    def elaborate(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return m


if __name__ == "__main__":
    m = Module()
    m.domains.sync = sync = ClockDomain("sync", async_reset=True)
    m.submodules.ctr = ctr = ClockDivisor(factor=16)
    main(m, ports=[ctr.o, sync.clk])
