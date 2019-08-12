from nmigen import *
from nmigen.back import rtlil, verilog, pysim


class Counter(Elaboratable):
    def __init__(self, width):
        self.v = Signal(width, reset=2**width-1)
        self.o = Signal()
        self.en = Signal()

    def elaborate(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return EnableInserter(self.en)(m)


ctr = Counter(width=16)

print(verilog.convert(ctr, ports=[ctr.o, ctr.en]))

with pysim.Simulator(ctr,
        vcd_file=open("ctrl.vcd", "w"),
        gtkw_file=open("ctrl.gtkw", "w"),
        traces=[ctr.en, ctr.v, ctr.o]) as sim:
    sim.add_clock(1e-6)
    def ce_proc():
        yield; yield; yield
        yield ctr.en.eq(1)
        yield; yield; yield
        yield ctr.en.eq(0)
        yield; yield; yield
        yield ctr.en.eq(1)
    sim.add_sync_process(ce_proc())
    sim.run_until(100e-6, run_passive=True)
