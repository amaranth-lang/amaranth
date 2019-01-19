from .tools import *
from ..hdl.ast import *
from ..hdl.dsl import *
from ..hdl.mem import *
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


class FIFOModel(FIFOInterface):
    """
    Non-synthesizable first-in first-out queue, implemented naively as a chain of registers.
    """
    def __init__(self, width, depth, fwft):
        super().__init__(width, depth)

        self.fwft    = fwft

        self.replace = Signal()
        self.level   = Signal(max=self.depth + 1)

    def get_fragment(self, platform):
        m = Module()

        storage = Memory(self.width, self.depth)
        wrport  = m.submodules.wrport = storage.write_port()
        rdport  = m.submodules.rdport = storage.read_port(synchronous=False)

        produce = Signal(max=self.depth)
        consume = Signal(max=self.depth)

        m.d.comb += self.readable.eq(self.level > 0)
        m.d.comb += rdport.addr.eq((consume + 1) % self.depth)
        if self.fwft:
            m.d.comb += self.dout.eq(rdport.data)
        with m.If(self.re & self.readable):
            if not self.fwft:
                m.d.sync += self.dout.eq(rdport.data)
            m.d.sync += consume.eq(rdport.addr)

        m.d.comb += self.writable.eq(self.level < self.depth)
        m.d.comb += wrport.data.eq(self.din)
        with m.If(self.we):
            with m.If(~self.replace & self.writable):
                m.d.comb += wrport.addr.eq((produce + 1) % self.depth)
                m.d.comb += wrport.en.eq(1)
                m.d.sync += produce.eq(wrport.addr)
            with m.If(self.replace):
                # The result of trying to replace an element in an empty queue is irrelevant.
                # The result of trying to replace the element that is currently being read
                # is undefined.
                m.d.comb += Assume(self.level > 0)
                m.d.comb += wrport.addr.eq(produce)
                m.d.comb += wrport.en.eq(1)

        m.d.sync += self.level.eq(self.level
            + (self.writable & self.we & ~self.replace)
            - (self.readable & self.re))

        return m.lower(platform)


class FIFOModelEquivalenceSpec:
    """
    The first-in first-out queue model equivalence specification: for any inputs and control
    signals, the behavior of the implementation under test exactly matches the ideal model,
    except for behavior not defined by the model.
    """
    def __init__(self, fifo):
        self.fifo = fifo

    def get_fragment(self, platform):
        m = Module()
        m.submodules.dut  = dut  = self.fifo
        m.submodules.gold = gold = FIFOModel(dut.width, dut.depth, dut.fwft)

        m.d.comb += [
            gold.re.eq(dut.readable & dut.re),
            gold.we.eq(dut.we),
            gold.din.eq(dut.din),
        ]
        if hasattr(dut, "replace"):
            m.d.comb += gold.replace.eq(dut.replace)
        else:
            m.d.comb += gold.replace.eq(0)

        m.d.comb += Assert(dut.readable.implies(gold.readable))
        if dut.fwft:
            m.d.comb += Assert(dut.readable
                               .implies(dut.dout == gold.dout))
        else:
            m.d.comb += Assert((Past(dut.readable) & Past(dut.re))
                               .implies(dut.dout == gold.dout))

        m.d.comb += Assert(dut.writable == gold.writable)

        if hasattr(dut, "level"):
            m.d.comb += Assert(dut.level == gold.level)

        return m.lower(platform)


class FIFOContractSpec:
    """
    The first-in first-out queue contract specification: if two elements are written to the queue
    consecutively, they must be read out consecutively at some later point, no matter all other
    circumstances, with the exception of reset.
    """
    def __init__(self, fifo, bound):
        self.fifo  = fifo
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

        initstate = Signal()
        m.submodules += Instance("$initstate", o_Y=initstate)
        with m.If(initstate):
            m.d.comb += Assume(write_fsm.ongoing("WRITE-1"))
            m.d.comb += Assume(read_fsm.ongoing("READ"))
        with m.If(Past(initstate, self.bound - 1)):
            m.d.comb += Assert(read_fsm.ongoing("DONE"))

        return m.lower(platform)


class FIFOFormalCase(FHDLTestCase):
    def check_fifo(self, fifo):
        self.assertFormal(FIFOModelEquivalenceSpec(fifo),
                          mode="bmc", depth=fifo.depth + 1)
        self.assertFormal(FIFOContractSpec(fifo, bound=fifo.depth * 2 + 1),
                          mode="hybrid", depth=fifo.depth * 2 + 1)

    def test_sync_fwft_pot(self):
        self.check_fifo(SyncFIFO(width=8, depth=4, fwft=True))

    def test_sync_fwft_npot(self):
        self.check_fifo(SyncFIFO(width=8, depth=5, fwft=True))

    def test_sync_not_fwft_pot(self):
        self.check_fifo(SyncFIFO(width=8, depth=4, fwft=False))

    def test_sync_not_fwft_npot(self):
        self.check_fifo(SyncFIFO(width=8, depth=5, fwft=False))

    def test_sync_buffered_pot(self):
        self.check_fifo(SyncFIFOBuffered(width=8, depth=4))

    def test_sync_buffered_potp1(self):
        self.check_fifo(SyncFIFOBuffered(width=8, depth=5))

    def test_sync_buffered_potm1(self):
        self.check_fifo(SyncFIFOBuffered(width=8, depth=3))
