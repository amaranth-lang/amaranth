from nmigen.fhdl import *
from nmigen.back import rtlil, verilog


class ALU:
    def __init__(self, width):
        self.sel = Signal(2)
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)
        self.co  = Signal()

    def get_fragment(self, platform):
        f = Module()
        with f.If(self.sel == 0b00):
            f.comb += self.o.eq(self.a | self.b)
        with f.Elif(self.sel == 0b01):
            f.comb += self.o.eq(self.a & self.b)
        with f.Elif(self.sel == 0b10):
            f.comb += self.o.eq(self.a ^ self.b)
        with f.Else():
            f.comb += Cat(self.o, self.co).eq(self.a - self.b)
        return f.lower(platform)


alu  = ALU(width=16)
frag = alu.get_fragment(platform=None)
# print(rtlil.convert(frag, ports=[alu.sel, alu.a, alu.b, alu.o, alu.co]))
print(verilog.convert(frag, ports=[alu.sel, alu.a, alu.b, alu.o, alu.co]))
