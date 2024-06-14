from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main


class Adder(wiring.Component):
    def __init__(self, width):
        super().__init__({
            "a": In(width),
            "b": In(width),
            "o": Out(width),
        })

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.a + self.b)
        return m


class Subtractor(wiring.Component):
    def __init__(self, width):
        super().__init__({
            "a": In(width),
            "b": In(width),
            "o": Out(width),
        })

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.a - self.b)
        return m


class ALU(wiring.Component):
    def __init__(self, width):
        super().__init__({
            "op": In(1),
            "a": In(width),
            "b": In(width),
            "o": Out(width),
        })
        self.add = Adder(width)
        self.sub = Subtractor(width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.add = self.add
        m.submodules.sub = self.sub
        m.d.comb += [
            self.add.a.eq(self.a),
            self.sub.a.eq(self.a),
            self.add.b.eq(self.b),
            self.sub.b.eq(self.b),
        ]
        with m.If(self.op):
            m.d.comb += self.o.eq(self.sub.o)
        with m.Else():
            m.d.comb += self.o.eq(self.add.o)
        return m


if __name__ == "__main__":
    alu = ALU(width=16)
    main(alu)
