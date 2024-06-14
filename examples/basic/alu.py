from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.cli import main

class ALU(wiring.Component):
    def __init__(self, width):
        super().__init__({
            "sel": In(2),
            "a": In(width),
            "b": In(width),
            "o": Out(width),
            "co": Out(1),
        })

    def elaborate(self, platform):
        m = Module()
        with m.If(self.sel == 0b00):
            m.d.comb += self.o.eq(self.a | self.b)
        with m.Elif(self.sel == 0b01):
            m.d.comb += self.o.eq(self.a & self.b)
        with m.Elif(self.sel == 0b10):
            m.d.comb += self.o.eq(self.a ^ self.b)
        with m.Else():
            m.d.comb += Cat(self.o, self.co).eq(self.a - self.b)
        return m


if __name__ == "__main__":
    alu = ALU(width=16)
    main(alu)
