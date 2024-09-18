from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.sim import *
from amaranth.back import verilog


class Counter(wiring.Component):
    o: Out(1)
    en: In(1)

    def __init__(self, width):
        super().__init__()
        self.v = Signal(width, init=2**width-1)

    def elaborate(self, platform):
        m = Module()
        m.d.sync += self.v.eq(self.v + 1)
        m.d.comb += self.o.eq(self.v[-1])
        return EnableInserter(self.en)(m)


ctr = Counter(width=16)

print(verilog.convert(ctr))

sim = Simulator(ctr)
sim.add_clock(Period(MHz=1))
async def testbench_ce(ctx):
    await ctx.tick().repeat(3)
    ctx.set(ctr.en, 1)
    await ctx.tick().repeat(3)
    ctx.set(ctr.en, 0)
    await ctx.tick().repeat(3)
    ctx.set(ctr.en,1)
sim.add_testbench(testbench_ce)
with sim.write_vcd("ctrl.vcd", "ctrl.gtkw", traces=[ctr.en, ctr.v, ctr.o]):
    sim.run_until(Period(us=100))
