from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class UpCounter(wiring.Component):
    """
    A 16-bit up counter with a fixed limit.

    Parameters
    ----------
    limit : int
        The value at which the counter overflows.

    Attributes
    ----------
    en : Signal, in
        The counter is incremented if ``en`` is asserted, and retains
        its value otherwise.
    ovf : Signal, out
        ``ovf`` is asserted when the counter reaches its limit.
    """

    en: In(1)
    ovf: Out(1)

    def __init__(self, limit):
        self.limit = limit
        self.count = Signal(16)

        super().__init__()

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.ovf.eq(self.count == self.limit)

        with m.If(self.en):
            with m.If(self.ovf):
                m.d.sync += self.count.eq(0)
            with m.Else():
                m.d.sync += self.count.eq(self.count + 1)

        return m
# --- TEST ---
from amaranth.sim import Simulator, Period


dut = UpCounter(25)
async def bench(ctx):
    # Disabled counter should not overflow.
    ctx.set(dut.en, 0)
    for _ in range(30):
        await ctx.tick()
        assert not ctx.get(dut.ovf)

    # Once enabled, the counter should overflow in 25 cycles.
    ctx.set(dut.en, 1)
    for _ in range(24):
        await ctx.tick()
        assert not ctx.get(dut.ovf)
    await ctx.tick()
    assert ctx.get(dut.ovf)

    # The overflow should clear in one cycle.
    await ctx.tick()
    assert not ctx.get(dut.ovf)


sim = Simulator(dut)
sim.add_clock(Period(MHz=1))
sim.add_testbench(bench)
with sim.write_vcd("up_counter.vcd"):
    sim.run()
# --- CONVERT ---
from amaranth.back import verilog


top = UpCounter(25)
with open("up_counter.v", "w") as f:
    f.write(verilog.convert(top))
