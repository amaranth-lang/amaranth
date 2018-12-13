from nmigen.fhdl import *
from nmigen.back import rtlil, verilog, pysim


class ClockDivisor:
    def __init__(self, factor):
        self.v = Signal(factor, reset=2**factor-1)
        self.o = Signal()

    def get_fragment(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return m.lower(platform)


ctr  = ClockDivisor(factor=16)
frag = ctr.get_fragment(platform=None)

# print(rtlil.convert(frag, ports=[ctr.o]))
print(verilog.convert(frag, ports=[ctr.o]))

sim = pysim.Simulator(frag, vcd_file=open("clkdiv.vcd", "w"))
sim.add_clock("sync", 1e-6)
with sim: sim.run_until(100e-6, run_passive=True)
