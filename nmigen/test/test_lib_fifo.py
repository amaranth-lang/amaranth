from .tools import *
from ..hdl.ast import *
from ..hdl.dsl import *
from ..hdl.ir import *
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


class FIFOContract:
    def __init__(self, fifo, fwft, bound):
        self.fifo  = fifo
        self.fwft  = fwft
        self.bound = bound

    def get_fragment(self, platform):
        m = Module()
        m.submodules.dut = fifo = self.fifo

        m.d.comb += ResetSignal().eq(0)
        if hasattr(fifo, "replace"):
            m.d.comb += fifo.replace.eq(0)

        entry_1 = AnyConst(fifo.width)
        entry_2 = AnyConst(fifo.width)

        with m.FSM() as write_fsm:
            with m.State("WRITE-1"):
                with m.If(fifo.writable):
                    m.d.comb += [
                        fifo.din.eq(entry_1),
                        fifo.we.eq(1)
                    ]
                    m.next = "WRITE-2"
            with m.State("WRITE-2"):
                with m.If(fifo.writable):
                    m.d.comb += [
                        fifo.din.eq(entry_2),
                        fifo.we.eq(1)
                    ]
                    m.next = "DONE"

        with m.FSM() as read_fsm:
            read_1 = Signal(fifo.width)
            read_2 = Signal(fifo.width)
            with m.State("READ"):
                m.d.comb += fifo.re.eq(1)
                with m.If(fifo.readable if fifo.fwft else Past(fifo.readable)):
                    m.d.sync += [
                        read_1.eq(read_2),
                        read_2.eq(fifo.dout),
                    ]
                with m.If((read_1 == entry_1) & (read_2 == entry_2)):
                    m.next = "DONE"

        cycle = Signal(max=self.bound + 1, reset=1)
        m.d.sync += cycle.eq(cycle + 1)
        with m.If(cycle == self.bound):
            m.d.comb += Assert(read_fsm.ongoing("DONE"))

        initstate = Signal()
        m.submodules += Instance("$initstate", o_Y=initstate)
        with m.If(initstate):
            m.d.comb += Assume(write_fsm.ongoing("WRITE-1"))
            m.d.comb += Assume(read_fsm.ongoing("READ"))
            m.d.comb += Assume(cycle == 1)

        return m.lower(platform)


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
    def check_fifo(self, fifo, invariants_cls):
        self.assertFormal(FIFOContract(fifo, fwft=fifo.fwft, bound=fifo.depth * 2 + 1),
                          mode="hybrid", depth=fifo.depth * 2 + 1)
        self.assertFormal(invariants_cls(fifo),
                          mode="prove", depth=fifo.depth * 2)

    def test_sync_fwft_pot(self):
        self.check_fifo(SyncFIFO(width=8, depth=4, fwft=True), SyncFIFOInvariants)

    def test_sync_fwft_npot(self):
        self.check_fifo(SyncFIFO(width=8, depth=5, fwft=True), SyncFIFOInvariants)

    def test_sync_not_fwft_pot(self):
        self.check_fifo(SyncFIFO(width=8, depth=4, fwft=False), SyncFIFOInvariants)

    def test_sync_not_fwft_npot(self):
        self.check_fifo(SyncFIFO(width=8, depth=5, fwft=False), SyncFIFOInvariants)

    def test_sync_buffered_pot(self):
        self.check_fifo(SyncFIFOBuffered(width=8, depth=4), SyncFIFOBufferedInvariants)

    def test_sync_buffered_potp1(self):
        self.check_fifo(SyncFIFOBuffered(width=8, depth=5), SyncFIFOBufferedInvariants)

    def test_sync_buffered_potm1(self):
        self.check_fifo(SyncFIFOBuffered(width=8, depth=3), SyncFIFOBufferedInvariants)
