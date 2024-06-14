from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class Counter(wiring.Component):
    o: Out(1)

    def __init__(self, width):
        super().__init__()
        self.v = Signal(width, init=2**width-1)

    def elaborate(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return m


ctr = Counter(width=16)
if __name__ == "__main__":
    main(ctr)
