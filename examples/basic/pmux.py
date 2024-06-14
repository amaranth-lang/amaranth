from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class ParMux(wiring.Component):
    def __init__(self, width):
        super().__init__({
            "s": In(3),
            "a": In(width),
            "b": In(width),
            "c": In(width),
            "o": Out(width),
        })

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.s):
            with m.Case("--1"):
                m.d.comb += self.o.eq(self.a)
            with m.Case("-1-"):
                m.d.comb += self.o.eq(self.b)
            with m.Case("1--"):
                m.d.comb += self.o.eq(self.c)
            with m.Default():
                m.d.comb += self.o.eq(0)
        return m


if __name__ == "__main__":
    pmux = ParMux(width=16)
    main(pmux)
