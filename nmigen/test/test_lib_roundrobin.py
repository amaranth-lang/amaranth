# nmigen: UnusedElaboratable=no
import unittest
from .utils import *
from ..hdl import *
from ..asserts import *
from ..sim.pysim import *
from ..lib.roundrobin import *


class RoundRobinTestCase(unittest.TestCase):
    def test_width(self):
        dut = RoundRobin(width=32)
        self.assertEqual(dut.width, 32)
        self.assertEqual(len(dut.requests), 32)
        self.assertEqual(len(dut.grant), 5)

    def test_wrong_width(self):
        with self.assertRaisesRegex(ValueError, r"Width must be a positive integer, not 'foo'"):
            dut = RoundRobin(width="foo")
        with self.assertRaisesRegex(ValueError, r"Width must be a positive integer, not -1"):
            dut = RoundRobin(width=-1)


class RoundRobinSimulationTestCase(unittest.TestCase):
    def test_width_one(self):
        dut = RoundRobin(width=1)
        sim = Simulator(dut)
        def process():
            yield dut.requests.eq(0)
            yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 0)

            yield dut.requests.eq(1)
            yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 0)
        sim.add_process(process)
        with sim.write_vcd("test.vcd"):
            sim.run()

    def test_transitions(self):
        dut = RoundRobin(width=3)
        sim = Simulator(dut)
        def process():
            yield dut.requests.eq(0b111)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 1)

            yield dut.requests.eq(0b110)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 2)

            yield dut.requests.eq(0b010)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 1)

            yield dut.requests.eq(0b011)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 0)

            yield dut.requests.eq(0b001)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 0)

            yield dut.requests.eq(0b101)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 2)

            yield dut.requests.eq(0b100)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 2)

            yield dut.requests.eq(0b000)
            yield; yield Delay(1e-8)

            yield dut.requests.eq(0b001)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.grant), 0)
        sim.add_sync_process(process)
        sim.add_clock(1e-6)
        with sim.write_vcd("test.vcd"):
            sim.run()
