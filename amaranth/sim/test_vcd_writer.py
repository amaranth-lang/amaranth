from amaranth import Elaboratable, Module, Signal
from amaranth.sim import Simulator

class Top(Elaboratable):
    def __init__(self):
        self.a = Signal()

    def elaborate(self, platform):
        m = Module()
        count = Signal(4)
        m.d.sync += [
            count.eq(count + 1),
            self.a.eq(count[-1])
        ]
        return m

# Create design and simulator
dut = Top()
sim = Simulator(dut)
sim.add_clock(1e-6)  # 1 MHz

def process():
    for _ in range(10):
        yield

sim.add_sync_process(process)

# Write VCD output
with open("test_output.vcd", "w") as vcd_file:
    with sim.write_vcd(vcd_file=vcd_file, gtkw_file=None, traces=[dut.a]):
        sim.run()
