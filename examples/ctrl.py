from nmigen.fhdl import *
from nmigen.back import rtlil, verilog


class ClockDivisor:
    def __init__(self, factor):
        self.v = Signal(factor, reset=2**factor-1)
        self.o = Signal()
        self.ce = Signal()

    def get_fragment(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return CEInserter(self.ce)(m.lower(platform))


sync = ClockDomain()
ctr  = ClockDivisor(factor=16)
frag = ctr.get_fragment(platform=None)
# print(rtlil.convert(frag, ports=[sync.clk, ctr.o, ctr.ce], clock_domains={"sync": sync}))
print(verilog.convert(frag, ports=[sync.clk, ctr.o, ctr.ce], clock_domains={"sync": sync}))
