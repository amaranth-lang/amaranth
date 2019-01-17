from .tools import *
from ..hdl.ast import *
from ..hdl.dsl import *
from ..back.pysim import *
from ..lib.fifo import *


class FIFOSmokeTestCase(FHDLTestCase):
    def assertSyncFIFOWorks(self, fifo):
        with Simulator(fifo) as sim:
            sim.add_clock(1e-6)
            def process():
                yield from fifo.write(1)
                yield from fifo.write(2)
                yield
                self.assertEqual((yield from fifo.read()), 1)
                self.assertEqual((yield from fifo.read()), 2)
            sim.add_sync_process(process)
            sim.run()

    def test_sync_fwft(self):
        fifo = SyncFIFO(width=8, depth=4, fwft=True)
        self.assertSyncFIFOWorks(SyncFIFO(width=8, depth=4))

    def test_sync_not_fwft(self):
        fifo = SyncFIFO(width=8, depth=4, fwft=False)
        self.assertSyncFIFOWorks(SyncFIFO(width=8, depth=4))

    def test_sync_buffered(self):
        fifo = SyncFIFO(width=8, depth=4, fwft=True)
        self.assertSyncFIFOWorks(SyncFIFOBuffered(width=8, depth=4))


class SyncFIFOInvariants:
    def __init__(self, fifo):
        self.fifo = fifo

    def get_fragment(self, platform):
        m = Module()
        m.submodules.dut = fifo = self.fifo

        with m.If(Fell(ResetSignal())):
            m.d.comb += [
                Assert(fifo.level == 0),
                Assert(~fifo.readable),
                Assert(fifo.writable),
            ]
        with m.Elif(~ResetSignal()):
            m.d.comb += Assert(fifo.level == (Past(fifo.level)
                                + (Past(fifo.writable) & Past(fifo.we) & ~Past(fifo.replace))
                                - (Past(fifo.readable) & Past(fifo.re))))
            with m.If(fifo.level != 0):
                m.d.comb += Assert(fifo.readable)
            with m.If(fifo.level != fifo.depth):
                m.d.comb += Assert(fifo.writable)

            with m.If(Past(1)):
                with m.If(~Past(fifo.re)):
                    # Unless `re` is asserted, output should not change, other than for the case of
                    # an empty FWFT queue, or an FWFT queue with a single entry being replaced.
                    if fifo.fwft:
                        with m.If((fifo.level == 1) & Past(fifo.we) &
                                  (Past(fifo.writable) | Past(fifo.replace))):
                            m.d.comb += Assert(fifo.dout == Past(fifo.din))
                        with m.Else():
                            m.d.comb += Assert(fifo.dout == Past(fifo.dout))
                    else:
                        m.d.comb += Assert(fifo.dout == Past(fifo.dout))

        return m.lower(platform)


class SyncFIFOBufferedInvariants:
    def __init__(self, fifo):
        self.fifo = fifo

    def get_fragment(self, platform):
        m = Module()
        m.submodules.dut = fifo = self.fifo

        with m.If(Fell(ResetSignal())):
            m.d.comb += [
                Assert(fifo.level == 0),
                Assert(~fifo.readable),
                Assert(fifo.writable),
            ]
        with m.Elif(~ResetSignal()):
            m.d.comb += Assert(fifo.level == (Past(fifo.level)
                                + (Past(fifo.writable) & Past(fifo.we))
                                - (Past(fifo.readable) & Past(fifo.re))))
            with m.If(fifo.level == 0):
                m.d.comb += Assert(~fifo.readable)
            with m.If(fifo.level == 1):
                # When there is one entry in the queue, it might be either in the inner unbuffered
                # queue memory, or in its output register.
                with m.If(Past(fifo.readable)):
                    # On the previous cycle, there was an entry in output register.
                    with m.If(Past(fifo.level) == 1):
                        # It was the only entry in the queue, so it's only there if it was
                        # not read.
                        m.d.comb += Assert(fifo.readable == ~Past(fifo.re))
                    with m.Else():
                        # There were more entries in the queue, which would refil the output
                        # register, if necessary.
                        m.d.comb += Assert(fifo.readable)
                with m.Elif(~Fell(ResetSignal(), 1)):
                    # On the previous cycle, there was no entry in the output register, so there is
                    # one only if it was written two cycles back.
                    m.d.comb += Assert(fifo.readable == Past(fifo.we, 2))
            with m.If(fifo.level > 1):
                m.d.comb += Assert(fifo.readable)
            with m.If(fifo.level != fifo.depth):
                m.d.comb += Assert(fifo.writable)

            with m.If(~Past(fifo.re)):
                # Unless `re` is asserted, output should not change, other than for the case of
                # an empty FWFT queue, where it changes with latency 1.
                with m.If(fifo.readable & ~Past(fifo.readable) &
                          Past(fifo.we, 2) & Past(fifo.writable, 2)):
                    m.d.comb += Assert(fifo.dout == Past(fifo.din, 2))
                with m.Else():
                    m.d.comb += Assert(fifo.dout == Past(fifo.dout))

        return m.lower(platform)


class FIFOFormalCase(FHDLTestCase):
    def test_sync_fwft_pot(self):
        fifo = SyncFIFO(width=8, depth=4, fwft=True)
        self.assertFormal(SyncFIFOInvariants(fifo),
                          mode="prove", depth=fifo.depth * 2)

    def test_sync_fwft_npot(self):
        fifo = SyncFIFO(width=8, depth=5, fwft=True)
        self.assertFormal(SyncFIFOInvariants(fifo),
                          mode="prove", depth=fifo.depth * 2)

    def test_sync_not_fwft_pot(self):
        fifo = SyncFIFO(width=8, depth=4, fwft=False)
        self.assertFormal(SyncFIFOInvariants(fifo),
                          mode="prove", depth=fifo.depth * 2)

    def test_sync_not_fwft_npot(self):
        fifo = SyncFIFO(width=8, depth=5, fwft=False)
        self.assertFormal(SyncFIFOInvariants(fifo),
                          mode="prove", depth=fifo.depth * 2)

    def test_sync_buffered_pot(self):
        fifo = SyncFIFOBuffered(width=8, depth=4)
        self.assertFormal(SyncFIFOBufferedInvariants(fifo),
                          mode="prove", depth=fifo.depth * 2)

    def test_sync_buffered_potp1(self):
        fifo = SyncFIFOBuffered(width=8, depth=5)
        self.assertFormal(SyncFIFOBufferedInvariants(fifo),
                          mode="prove", depth=fifo.depth * 2)

    def test_sync_buffered_potm1(self):
        fifo = SyncFIFOBuffered(width=8, depth=3)
        self.assertFormal(SyncFIFOBufferedInvariants(fifo),
                          mode="prove", depth=fifo.depth * 2)
