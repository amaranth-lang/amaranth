from amaranth import *
from amaranth.cli import main


class Counter(Elaboratable):
    def __init__(self, width):
        self.v = Signal(width, reset=2**width-1)
        self.o = Signal()

    def elaborate(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return m


ctr = Counter(width=16)
if __name__ == "__main__":
    main(ctr, ports=[ctr.o])
