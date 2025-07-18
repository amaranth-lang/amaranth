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
    
class IrregularToggleDUT(Elaboratable):
    def __init__(self):
        self.out = Signal(name="out")

    def elaborate(self, platform):
        m = Module()
        counter = Signal(4, name="counter")
        toggle = Signal()

        m.d.sync += counter.eq(counter + 1)
        with m.If((counter == 1) | (counter == 3) | (counter == 6)):
            m.d.sync += toggle.eq(~toggle)
        m.d.comb += self.out.eq(toggle)

        return m

class ToggleCoverageTest(unittest.TestCase):
    def test_toggle_coverage_regular(self):
        dut = ToggleDUT()
        sim = Simulator(dut)

        toggle_cov = ToggleCoverageObserver(sim._engine.state)
        sim._engine.add_observer(toggle_cov)

        def process():
            for _ in range(16):
                yield Tick()

        sim.add_clock(1e-6)
        sim.add_testbench(process)
        sim.run()

        results = toggle_cov.get_results()
        print("[Regular] Toggle coverage results:")
        for signal_name, toggles in results.items():
            print(f"{signal_name}: 0→1={toggles['0->1']}, 1→0={toggles['1->0']}")

        self.assertTrue(results["out"]["0->1"], "Expected at least one 0→1 toggle on 'out'")
        self.assertTrue(results["out"]["1->0"], "Expected at least one 1→0 toggle on 'out'")

    def test_toggle_coverage_irregular(self):
        dut = IrregularToggleDUT()
        sim = Simulator(dut)

        toggle_cov = ToggleCoverageObserver(sim._engine.state)
        sim._engine.add_observer(toggle_cov)

        def process():
            for _ in range(16):
                yield Tick()

        sim.add_clock(1e-6)
        sim.add_testbench(process)
        sim.run()

        results = toggle_cov.get_results()
        print("[Irregular] Toggle coverage results:")
        for signal_name, toggles in results.items():
            print(f"{signal_name}: 0→1={toggles['0->1']}, 1→0={toggles['1->0']}")

        self.assertTrue(results["out"]["0->1"], "Expected at least one 0→1 toggle on 'out'")
        self.assertTrue(results["out"]["1->0"], "Expected at least one 1→0 toggle on 'out'")
        self.assertGreaterEqual(results["out"]["0->1"], 1)
        self.assertGreaterEqual(results["out"]["1->0"], 1)

