from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog


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

sim = Simulator(ctr)
sim.add_clock(1e-6)
def ce_proc():
    yield; yield; yield
    yield ctr.en.eq(1)
    yield; yield; yield
    yield ctr.en.eq(0)
    yield; yield; yield
    yield ctr.en.eq(1)
sim.add_sync_process(ce_proc)
with sim.write_vcd("ctrl.vcd", "ctrl.gtkw", traces=[ctr.en, ctr.v, ctr.o]):
    sim.run_until(100e-6, run_passive=True)
