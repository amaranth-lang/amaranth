import unittest
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


class ToggleCoverageTest(unittest.TestCase):
    def test_toggle_coverage(self):
        dut = ToggleDUT()
        sim = Simulator(dut)

        toggle_cov = ToggleCoverageObserver(sim._engine.state)
        sim._engine.add_observer(toggle_cov)

        def process():
            for _ in range(8):
                yield Tick()
                sim._engine.notify_signal_change(dut.out)

        sim.add_clock(1e-6)
        sim.add_testbench(process)
        sim.run()

        results = toggle_cov.get_results()
        print("Toggle coverage results:")
        for signal_name, toggles in results.items():
            print(f"{signal_name}: 0→1={toggles['0->1']}, 1→0={toggles['1->0']}")

        self.assertTrue(results["out"]["0->1"], "Expected at least one 0→1 toggle on 'out'")
        self.assertTrue(results["out"]["1->0"], "Expected at least one 1→0 toggle on 'out'")


if __name__ == "__main__":
    unittest.main()
