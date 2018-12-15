from nmigen import *
from nmigen.back import rtlil, verilog, pysim


class Counter:
    def __init__(self, width):
        self.v = Signal(width, reset=2**width-1)
        self.o = Signal()

    def get_fragment(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return m.lower(platform)


ctr  = Counter(width=16)
frag = ctr.get_fragment(platform=None)

# print(rtlil.convert(frag, ports=[ctr.o]))
print(verilog.convert(frag, ports=[ctr.o]))

with pysim.Simulator(frag,
        vcd_file=open("ctr.vcd", "w")) as sim:
    sim.add_clock(1e-6)
    sim.run_until(100e-6, run_passive=True)
