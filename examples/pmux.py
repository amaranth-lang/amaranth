from nmigen.fhdl import *
from nmigen.back import rtlil, verilog


class ParMux:
    def __init__(self, width):
        self.s = Signal(3)
        self.a = Signal(width)
        self.b = Signal(width)
        self.c = Signal(width)
        self.o = Signal(width)

    def get_fragment(self, platform):
        f = Module()
        with f.Case(self.s, "--1"):
            f.comb += self.o.eq(self.a)
        with f.Case(self.s, "-1-"):
            f.comb += self.o.eq(self.b)
        with f.Case(self.s, "1--"):
            f.comb += self.o.eq(self.c)
        with f.Case(self.s):
            f.comb += self.o.eq(0)
        return f.lower(platform)


pmux = ParMux(width=16)
frag = pmux.get_fragment(platform=None)
# print(rtlil.convert(frag, ports=[pmux.s, pmux.a, pmux.b, pmux.c, pmux.o]))
print(verilog.convert(frag, ports=[pmux.s, pmux.a, pmux.b, pmux.c, pmux.o]))
