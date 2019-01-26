from .tools import *
from ..hdl.ast import *
from ..hdl.cd import *
from ..hdl.dsl import *
from ..back.pysim import *
from ..lib.cdc import *


class MultiRegTestCase(FHDLTestCase):
    def test_basic(self):
        i = Signal()
        o = Signal()
        frag = MultiReg(i, o)
        with Simulator(frag) as sim:
            sim.add_clock(1e-6)
            def process():
                self.assertEqual((yield o), 0)
                yield i.eq(1)
                yield Tick()
                self.assertEqual((yield o), 0)
                yield Tick()
                self.assertEqual((yield o), 0)
                yield Tick()
                self.assertEqual((yield o), 1)
            sim.add_process(process)
            sim.run()

    def test_reset_value(self):
        i = Signal(reset=1)
        o = Signal()
        frag = MultiReg(i, o, reset=1)
        with Simulator(frag) as sim:
            sim.add_clock(1e-6)
            def process():
                self.assertEqual((yield o), 1)
                yield i.eq(0)
                yield Tick()
                self.assertEqual((yield o), 1)
                yield Tick()
                self.assertEqual((yield o), 1)
                yield Tick()
                self.assertEqual((yield o), 0)
            sim.add_process(process)
            sim.run()


class ResetSynchronizerTestCase(FHDLTestCase):
    def test_basic(self):
        arst = Signal()
        m = Module()
        m.domains += ClockDomain("sync")
        m.submodules += ResetSynchronizer(arst)
        s = Signal(reset=1)
        m.d.sync += s.eq(0)

        with Simulator(m, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            def process():
                # initial reset
                self.assertEqual((yield s), 1)
                yield Tick(); yield Delay(1e-8)
                self.assertEqual((yield s), 1)
                yield Tick(); yield Delay(1e-8)
                self.assertEqual((yield s), 1)
                yield Tick(); yield Delay(1e-8)
                self.assertEqual((yield s), 0)
                yield Tick(); yield Delay(1e-8)

                yield arst.eq(1)
                yield Delay(1e-8)
                self.assertEqual((yield s), 1)
                yield Tick(); yield Delay(1e-8)
                self.assertEqual((yield s), 1)
                yield arst.eq(0)
                yield Tick(); yield Delay(1e-8)
                self.assertEqual((yield s), 1)
                yield Tick(); yield Delay(1e-8)
                self.assertEqual((yield s), 1)
                yield Tick(); yield Delay(1e-8)
                self.assertEqual((yield s), 0)
                yield Tick(); yield Delay(1e-8)
            sim.add_process(process)
            sim.run()
