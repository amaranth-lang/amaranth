# amaranth: UnusedElaboratable=no

from amaranth.hdl import *
from amaranth.sim import *
from amaranth.lib.cdc import *

from .utils import *


class FFSynchronizerTestCase(FHDLTestCase):
    def test_stages_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Synchronization stage count must be a positive integer, not 0$"):
            FFSynchronizer(Signal(), Signal(), stages=0)
        with self.assertRaisesRegex(ValueError,
                r"^Synchronization stage count may not safely be less than 2$"):
            FFSynchronizer(Signal(), Signal(), stages=1)

    def test_basic(self):
        i = Signal()
        o = Signal()
        frag = FFSynchronizer(i, o)

        sim = Simulator(frag)
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
        frag = FFSynchronizer(i, o, reset=1)

        sim = Simulator(frag)
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


class AsyncFFSynchronizerTestCase(FHDLTestCase):
    def test_stages_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Synchronization stage count must be a positive integer, not 0$"):
            ResetSynchronizer(Signal(), stages=0)
        with self.assertRaisesRegex(ValueError,
                r"^Synchronization stage count may not safely be less than 2$"):
            ResetSynchronizer(Signal(), stages=1)

    def test_edge_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^AsyncFFSynchronizer async edge must be one of 'pos' or 'neg', not 'xxx'$"):
            AsyncFFSynchronizer(Signal(), Signal(), o_domain="sync", async_edge="xxx")

    def test_width_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^AsyncFFSynchronizer input width must be 1, not 2$"):
            AsyncFFSynchronizer(Signal(2), Signal(), o_domain="sync")
        with self.assertRaisesRegex(ValueError,
                r"^AsyncFFSynchronizer output width must be 1, not 2$"):
            AsyncFFSynchronizer(Signal(), Signal(2), o_domain="sync")

    def test_pos_edge(self):
        i = Signal()
        o = Signal()
        m = Module()
        m.domains += ClockDomain("sync")
        m.submodules += AsyncFFSynchronizer(i, o)

        sim = Simulator(m)
        sim.add_clock(1e-6)
        def process():
            # initial reset
            self.assertEqual((yield i), 0)
            self.assertEqual((yield o), 1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 0)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 0)
            yield Tick(); yield Delay(1e-8)

            yield i.eq(1)
            yield Delay(1e-8)
            self.assertEqual((yield o), 1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 1)
            yield i.eq(0)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 0)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 0)
            yield Tick(); yield Delay(1e-8)
        sim.add_process(process)
        with sim.write_vcd("test.vcd"):
            sim.run()

    def test_neg_edge(self):
        i = Signal(reset=1)
        o = Signal()
        m = Module()
        m.domains += ClockDomain("sync")
        m.submodules += AsyncFFSynchronizer(i, o, async_edge="neg")

        sim = Simulator(m)
        sim.add_clock(1e-6)
        def process():
            # initial reset
            self.assertEqual((yield i), 1)
            self.assertEqual((yield o), 1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 0)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 0)
            yield Tick(); yield Delay(1e-8)

            yield i.eq(0)
            yield Delay(1e-8)
            self.assertEqual((yield o), 1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 1)
            yield i.eq(1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 1)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 0)
            yield Tick(); yield Delay(1e-8)
            self.assertEqual((yield o), 0)
            yield Tick(); yield Delay(1e-8)
        sim.add_process(process)
        with sim.write_vcd("test.vcd"):
            sim.run()


class ResetSynchronizerTestCase(FHDLTestCase):
    def test_stages_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Synchronization stage count must be a positive integer, not 0$"):
            ResetSynchronizer(Signal(), stages=0)
        with self.assertRaisesRegex(ValueError,
                r"^Synchronization stage count may not safely be less than 2$"):
            ResetSynchronizer(Signal(), stages=1)

    def test_basic(self):
        arst = Signal()
        m = Module()
        m.domains += ClockDomain("sync")
        m.submodules += ResetSynchronizer(arst)
        s = Signal(reset=1)
        m.d.sync += s.eq(0)

        sim = Simulator(m)
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
            self.assertEqual((yield s), 0)
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
        with sim.write_vcd("test.vcd"):
            sim.run()


# TODO: test with distinct clocks
class PulseSynchronizerTestCase(FHDLTestCase):
    def test_stages_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Synchronization stage count must be a positive integer, not 0$"):
            PulseSynchronizer("w", "r", stages=0)
        with self.assertRaisesRegex(ValueError,
                r"^Synchronization stage count may not safely be less than 2$"):
            PulseSynchronizer("w", "r", stages=1)

    def test_smoke(self):
        m = Module()
        m.domains += ClockDomain("sync")
        ps = m.submodules.dut = PulseSynchronizer("sync", "sync")

        sim = Simulator(m)
        sim.add_clock(1e-6)
        def process():
            yield ps.i.eq(0)
            # TODO: think about reset
            for n in range(5):
                yield Tick()
            # Make sure no pulses are generated in quiescent state
            for n in range(3):
                yield Tick()
                self.assertEqual((yield ps.o), 0)
            # Check conservation of pulses
            accum = 0
            for n in range(10):
                yield ps.i.eq(1 if n < 4 else 0)
                yield Tick()
                accum += yield ps.o
            self.assertEqual(accum, 4)
        sim.add_process(process)
        sim.run()
