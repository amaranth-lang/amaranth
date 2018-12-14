from nmigen.fhdl import *
from nmigen.back import rtlil, verilog, pysim


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


ctr  = ClockDivisor(factor=16)
frag = ctr.get_fragment(platform=None)

# print(rtlil.convert(frag, ports=[ctr.o, ctr.ce]))
print(verilog.convert(frag, ports=[ctr.o, ctr.ce]))

sim = pysim.Simulator(frag, vcd_file=open("ctrl.vcd", "w"))
sim.add_clock("sync", 1e-6)
def ce_proc():
    yield; yield; yield
    yield ctr.ce.eq(1)
    yield; yield; yield
    yield ctr.ce.eq(0)
    yield; yield; yield
    yield ctr.ce.eq(1)
sim.add_sync_process(ce_proc())
with sim: sim.run_until(100e-6, run_passive=True)
