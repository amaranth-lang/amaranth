from .utils import *
from ..hdl import *
from ..asserts import *
from ..sim.pysim import *
from ..lib.roundrobin import *

class RoundRobinIndividualSpec(Elaboratable):
    def __init__(self, n):
        self.n = n

    def elaborate(self, platform):
        m = Module()

        m.submodules.dut = dut = RoundRobin(self.n)

        for i in range(self.n):
            m.d.sync += Assert((Past(dut.requests) == (1 << i)).implies(dut.grant == i))

        return m

class RoundRobinTestCase(FHDLTestCase):
    def test_individual(self):
        self.assertFormal(RoundRobinIndividualSpec(1))
        self.assertFormal(RoundRobinIndividualSpec(10))

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
