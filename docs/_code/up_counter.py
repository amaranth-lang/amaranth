from amaranth import *


class UpCounter(Elaboratable):
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
    def __init__(self, limit):
        self.limit = limit

        # Ports
        self.en  = Signal()
        self.ovf = Signal()

        # State
        self.count = Signal(16)

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
from amaranth.sim import Simulator


dut = UpCounter(25)
def bench():
    # Disabled counter should not overflow.
    yield dut.en.eq(0)
    for _ in range(30):
        yield
        assert not (yield dut.ovf)

    # Once enabled, the counter should overflow in 25 cycles.
    yield dut.en.eq(1)
    for _ in range(25):
        yield
        assert not (yield dut.ovf)
    yield
    assert (yield dut.ovf)

    # The overflow should clear in one cycle.
    yield
    assert not (yield dut.ovf)


sim = Simulator(dut)
sim.add_clock(1e-6) # 1 MHz
sim.add_sync_process(bench)
with sim.write_vcd("up_counter.vcd"):
    sim.run()
# --- CONVERT ---
from amaranth.back import verilog


top = UpCounter(25)
with open("up_counter.v", "w") as f:
    f.write(verilog.convert(top, ports=[top.en, top.ovf]))
