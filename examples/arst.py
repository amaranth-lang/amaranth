from nmigen import *
from nmigen.cli import main


class ClockDivisor:
    def __init__(self, factor):
        self.v = Signal(factor)
        self.o = Signal()

    def elaborate(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return m


if __name__ == "__main__":
    ctr = ClockDivisor(factor=16)
    m = ctr.elaborate(platform=None)
    m.domains += ClockDomain("sync", async_reset=True)
    main(m, ports=[ctr.o])
