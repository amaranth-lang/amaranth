from nmigen.fhdl import *
from nmigen.back import rtlil, verilog


class Adder:
    def __init__(self, width):
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)

    def get_fragment(self, platform):
        f = Module()
        f.comb += self.o.eq(self.a + self.b)
        return f.lower(platform)


class Subtractor:
    def __init__(self, width):
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)

    def get_fragment(self, platform):
        f = Module()
        f.comb += self.o.eq(self.a - self.b)
        return f.lower(platform)


class ALU:
    def __init__(self, width):
        self.op  = Signal()
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)

        self.add = Adder(width)
        self.sub = Subtractor(width)

    def get_fragment(self, platform):
        f = Module()
        f.submodules.add = self.add
        f.submodules.sub = self.sub
        f.comb += [
            self.add.a.eq(self.a),
            self.sub.a.eq(self.a),
            self.add.b.eq(self.b),
            self.sub.b.eq(self.b),
        ]
        with f.If(self.op):
            f.comb += self.o.eq(self.sub.o)
        with f.Else():
            f.comb += self.o.eq(self.add.o)
        return f.lower(platform)


alu  = ALU(width=16)
frag = alu.get_fragment(platform=None)
# print(rtlil.convert(frag, ports=[alu.op, alu.a, alu.b, alu.o]))
print(verilog.convert(frag, ports=[alu.op, alu.a, alu.b, alu.o, alu.add.o, alu.sub.o]))
