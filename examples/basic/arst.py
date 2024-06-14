from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class ClockDivisor(wiring.Component):
    o: Out(1)

    def __init__(self, factor):
        super().__init__()
        self.v = Signal(factor)

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
