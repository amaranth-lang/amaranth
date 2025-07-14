from _base import DummyEngine, PrintObserver

# def test_print_observer():
#     engine = DummyEngine()
#     observer = PrintObserver()
#     engine.add_observer(observer)

#     engine.notify_signal_change("CLK")
#     engine.notify_memory_change("RAM", 0x10)
#     engine.notify_close()

# if __name__ == "__main__":
#     test_print_observer()

from amaranth import *
from amaranth.sim import Tick, Simulator
from amaranth.sim._coverage import ToggleCoverageObserver

class ToggleDUT(Elaboratable):
    def __init__(self):
        self.out = Signal(name="out")

    def elaborate(self, platform):
        m = Module()
        counter = Signal(2, name="counter")
        m.d.sync += counter.eq(counter + 1)
        m.d.comb += self.out.eq(counter[1])
        return m


def run_toggle_coverage_test():
    dut = ToggleDUT()
    sim = Simulator(dut)

    toggle_cov = ToggleCoverageObserver(sim._engine.state)
    sim._engine.add_observer(toggle_cov)

    def process():
        for _ in range(8):  # Run for 8 cycles
            yield Tick()
            sim._engine.notify_signal_change(dut.out)

    sim.add_clock(1e-6)
    sim.add_testbench(process)
    sim.run()

    results = toggle_cov.get_results()
    print("Toggle coverage results:")
    for signal_name, toggles in results.items():
        print(f"{signal_name}: 0→1={toggles['0->1']}, 1→0={toggles['1->0']}")

    assert results["out"]["0->1"]
    assert results["out"]["1->0"]


if __name__ == "__main__":
    run_toggle_coverage_test()
