import unittest
from .utils import *
from ..hdl import *
from ..asserts import *
from ..sim.pysim import *
from ..lib.roundrobin import *

class RoundRobinSimulationTestCase(unittest.TestCase):
    def test_transitions(self):
        m = Module()
        m.submodules.dut = dut = RoundRobin(3)

        sim = Simulator(m)
        def process():
            yield dut.requests.eq(0b11)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 1)

            yield dut.requests.eq(0b01)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 0)

            yield dut.requests.eq(0b01)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 0)

            yield dut.requests.eq(0b10)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 1)

            yield dut.requests.eq(0b01)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 0)
        sim.add_process(process)
        sim.add_clock(1e-6)
        with sim.write_vcd("test.vcd"):
            sim.run()
