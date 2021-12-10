# amaranth: UnusedElaboratable=no

from amaranth.hdl import *
from amaranth.asserts import *
from amaranth.sim import *
from amaranth.lib.fifo import *

from .utils import *


class FIFOTestCase(FHDLTestCase):
    def test_depth_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^FIFO width must be a non-negative integer, not -1$"):
            FIFOInterface(width=-1, depth=8, fwft=True)
        with self.assertRaisesRegex(TypeError,
                r"^FIFO depth must be a non-negative integer, not -1$"):
            FIFOInterface(width=8, depth=-1, fwft=True)

    def test_sync_depth(self):
        self.assertEqual(SyncFIFO(width=8, depth=0).depth, 0)
        self.assertEqual(SyncFIFO(width=8, depth=1).depth, 1)
        self.assertEqual(SyncFIFO(width=8, depth=2).depth, 2)

    def test_sync_buffered_depth(self):
        self.assertEqual(SyncFIFOBuffered(width=8, depth=0).depth, 0)
        self.assertEqual(SyncFIFOBuffered(width=8, depth=1).depth, 1)
        self.assertEqual(SyncFIFOBuffered(width=8, depth=2).depth, 2)

    def test_async_depth(self):
        self.assertEqual(AsyncFIFO(width=8, depth=0 ).depth, 0)
        self.assertEqual(AsyncFIFO(width=8, depth=1 ).depth, 1)
        self.assertEqual(AsyncFIFO(width=8, depth=2 ).depth, 2)
        self.assertEqual(AsyncFIFO(width=8, depth=3 ).depth, 4)
        self.assertEqual(AsyncFIFO(width=8, depth=4 ).depth, 4)
        self.assertEqual(AsyncFIFO(width=8, depth=15).depth, 16)
        self.assertEqual(AsyncFIFO(width=8, depth=16).depth, 16)
        self.assertEqual(AsyncFIFO(width=8, depth=17).depth, 32)

    def test_async_depth_wrong(self):
        with self.assertRaisesRegex(ValueError,
                (r"^AsyncFIFO only supports depths that are powers of 2; "
                    r"requested exact depth 15 is not$")):
            AsyncFIFO(width=8, depth=15, exact_depth=True)

    def test_async_buffered_depth(self):
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=0 ).depth, 0)
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=1 ).depth, 2)
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=2 ).depth, 2)
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=3 ).depth, 3)
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=4 ).depth, 5)
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=15).depth, 17)
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=16).depth, 17)
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=17).depth, 17)
        self.assertEqual(AsyncFIFOBuffered(width=8, depth=18).depth, 33)

    def test_async_buffered_depth_wrong(self):
        with self.assertRaisesRegex(ValueError,
                (r"^AsyncFIFOBuffered only supports depths that are one higher than powers of 2; "
                    r"requested exact depth 16 is not$")):
            AsyncFIFOBuffered(width=8, depth=16, exact_depth=True)

class FIFOModel(Elaboratable, FIFOInterface):
    """
    Non-synthesizable first-in first-out queue, implemented naively as a chain of registers.
    """
    def __init__(self, *, width, depth, fwft, r_domain, w_domain):
        super().__init__(width=width, depth=depth, fwft=fwft)

        self.r_domain = r_domain
        self.w_domain = w_domain

        self.level = Signal(range(self.depth + 1))
        self.r_level = Signal(range(self.depth + 1))
        self.w_level = Signal(range(self.depth + 1))

    def elaborate(self, platform):
        m = Module()

        storage = Memory(width=self.width, depth=self.depth)
        w_port  = m.submodules.w_port = storage.write_port(domain=self.w_domain)
        r_port  = m.submodules.r_port = storage.read_port (domain="comb")

        produce = Signal(range(self.depth))
        consume = Signal(range(self.depth))

        m.d.comb += self.r_rdy.eq(self.level > 0)
        m.d.comb += r_port.addr.eq((consume + 1) % self.depth)
        if self.fwft:
            m.d.comb += self.r_data.eq(r_port.data)
        with m.If(self.r_en & self.r_rdy):
            if not self.fwft:
                m.d[self.r_domain] += self.r_data.eq(r_port.data)
            m.d[self.r_domain] += consume.eq(r_port.addr)

        m.d.comb += self.w_rdy.eq(self.level < self.depth)
        m.d.comb += w_port.data.eq(self.w_data)
        with m.If(self.w_en & self.w_rdy):
            m.d.comb += w_port.addr.eq((produce + 1) % self.depth)
            m.d.comb += w_port.en.eq(1)
            m.d[self.w_domain] += produce.eq(w_port.addr)

        with m.If(ResetSignal(self.r_domain) | ResetSignal(self.w_domain)):
            m.d.sync += self.level.eq(0)
        with m.Else():
            m.d.sync += self.level.eq(self.level
                + (self.w_rdy & self.w_en)
                - (self.r_rdy & self.r_en))

        m.d.comb += [
            self.r_level.eq(self.level),
            self.w_level.eq(self.level),
        ]
        m.d.comb += Assert(ResetSignal(self.r_domain) == ResetSignal(self.w_domain))

        return m


class FIFOModelEquivalenceSpec(Elaboratable):
    """
    The first-in first-out queue model equivalence specification: for any inputs and control
    signals, the behavior of the implementation under test exactly matches the ideal model,
    except for behavior not defined by the model.
    """
    def __init__(self, fifo, r_domain, w_domain):
        self.fifo = fifo

        self.r_domain = r_domain
        self.w_domain = w_domain

    def elaborate(self, platform):
        m = Module()
        m.submodules.dut  = dut  = self.fifo
        m.submodules.gold = gold = FIFOModel(width=dut.width, depth=dut.depth, fwft=dut.fwft,
                                             r_domain=self.r_domain, w_domain=self.w_domain)

        m.d.comb += [
            gold.r_en.eq(dut.r_rdy & dut.r_en),
            gold.w_en.eq(dut.w_en),
            gold.w_data.eq(dut.w_data),
        ]

        m.d.comb += Assert(dut.r_rdy.implies(gold.r_rdy))
        m.d.comb += Assert(dut.w_rdy.implies(gold.w_rdy))
        m.d.comb += Assert(dut.r_level == gold.r_level)
        m.d.comb += Assert(dut.w_level == gold.w_level)

        if dut.fwft:
            m.d.comb += Assert(dut.r_rdy
                               .implies(dut.r_data == gold.r_data))
        else:
            m.d.comb += Assert((Past(dut.r_rdy, domain=self.r_domain) &
                                Past(dut.r_en, domain=self.r_domain))
                               .implies(dut.r_data == gold.r_data))

        return m


class FIFOContractSpec(Elaboratable):
    """
    The first-in first-out queue contract specification: if two elements are written to the queue
    consecutively, they must be read out consecutively at some later point, no matter all other
    circumstances, with the exception of reset.
    """
    def __init__(self, fifo, *, r_domain, w_domain, bound):
        self.fifo     = fifo
        self.r_domain = r_domain
        self.w_domain = w_domain
        self.bound    = bound

    def elaborate(self, platform):
        m = Module()
        m.submodules.dut = fifo = self.fifo

        m.domains += ClockDomain("sync")
        m.d.comb += ResetSignal().eq(0)
        if self.w_domain != "sync":
            m.domains += ClockDomain(self.w_domain)
            m.d.comb += ResetSignal(self.w_domain).eq(0)
        if self.r_domain != "sync":
            m.domains += ClockDomain(self.r_domain)
            m.d.comb += ResetSignal(self.r_domain).eq(0)

        entry_1 = AnyConst(fifo.width)
        entry_2 = AnyConst(fifo.width)

        with m.FSM(domain=self.w_domain) as write_fsm:
            with m.State("WRITE-1"):
                with m.If(fifo.w_rdy):
                    m.d.comb += [
                        fifo.w_data.eq(entry_1),
                        fifo.w_en.eq(1)
                    ]
                    m.next = "WRITE-2"
            with m.State("WRITE-2"):
                with m.If(fifo.w_rdy):
                    m.d.comb += [
                        fifo.w_data.eq(entry_2),
                        fifo.w_en.eq(1)
                    ]
                    m.next = "DONE"
            with m.State("DONE"):
                pass

        with m.FSM(domain=self.r_domain) as read_fsm:
            read_1 = Signal(fifo.width)
            read_2 = Signal(fifo.width)
            with m.State("READ"):
                m.d.comb += fifo.r_en.eq(1)
                if fifo.fwft:
                    r_rdy = fifo.r_rdy
                else:
                    r_rdy = Past(fifo.r_rdy, domain=self.r_domain)
                with m.If(r_rdy):
                    m.d.sync += [
                        read_1.eq(read_2),
                        read_2.eq(fifo.r_data),
                    ]
                with m.If((read_1 == entry_1) & (read_2 == entry_2)):
                    m.next = "DONE"
            with m.State("DONE"):
                pass

        with m.If(Initial()):
            m.d.comb += Assume(write_fsm.ongoing("WRITE-1"))
            m.d.comb += Assume(read_fsm.ongoing("READ"))
        with m.If(Past(Initial(), self.bound - 1)):
            m.d.comb += Assert(read_fsm.ongoing("DONE"))

        with m.If(ResetSignal(domain=self.w_domain)):
            m.d.comb += Assert(~fifo.r_rdy)

        if self.w_domain != "sync" or self.r_domain != "sync":
            m.d.comb += Assume(Rose(ClockSignal(self.w_domain)) |
                               Rose(ClockSignal(self.r_domain)))

        return m


class FIFOFormalCase(FHDLTestCase):
    def check_sync_fifo(self, fifo):
        self.assertFormal(FIFOModelEquivalenceSpec(fifo, r_domain="sync", w_domain="sync"),
                          mode="bmc", depth=fifo.depth + 1)
        self.assertFormal(FIFOContractSpec(fifo, r_domain="sync", w_domain="sync",
                                           bound=fifo.depth * 2 + 1),
                          mode="hybrid", depth=fifo.depth * 2 + 1)

    def test_sync_fwft_pot(self):
        self.check_sync_fifo(SyncFIFO(width=8, depth=4, fwft=True))

    def test_sync_fwft_npot(self):
        self.check_sync_fifo(SyncFIFO(width=8, depth=5, fwft=True))

    def test_sync_not_fwft_pot(self):
        self.check_sync_fifo(SyncFIFO(width=8, depth=4, fwft=False))

    def test_sync_not_fwft_npot(self):
        self.check_sync_fifo(SyncFIFO(width=8, depth=5, fwft=False))

    def test_sync_buffered_pot(self):
        self.check_sync_fifo(SyncFIFOBuffered(width=8, depth=4))

    def test_sync_buffered_potp1(self):
        self.check_sync_fifo(SyncFIFOBuffered(width=8, depth=5))

    def test_sync_buffered_potm1(self):
        self.check_sync_fifo(SyncFIFOBuffered(width=8, depth=3))

    def check_async_fifo(self, fifo):
        # TODO: properly doing model equivalence checking on this likely requires multiclock,
        # which is not really documented nor is it clear how to use it.
        # self.assertFormal(FIFOModelEquivalenceSpec(fifo, r_domain="read", w_domain="write"),
        #                   mode="bmc", depth=fifo.depth * 3 + 1)
        self.assertFormal(FIFOContractSpec(fifo, r_domain="read", w_domain="write",
                                           bound=fifo.depth * 4 + 1),
                          mode="hybrid", depth=fifo.depth * 4 + 1)

    def test_async(self):
        self.check_async_fifo(AsyncFIFO(width=8, depth=4))

    def test_async_buffered(self):
        self.check_async_fifo(AsyncFIFOBuffered(width=8, depth=4))


# we need this testcase because we cant do model equivalence checking on the async fifos (at the moment)
class AsyncFIFOSimCase(FHDLTestCase):
    def test_async_fifo_r_level_latency(self):
        fifo = AsyncFIFO(width=32, depth=10, r_domain="sync", w_domain="sync")

        ff_syncronizer_latency = 2

        def testbench():
            for i in range(10):
                yield fifo.w_data.eq(i)
                yield fifo.w_en.eq(1)
                yield

                if (i - ff_syncronizer_latency) > 0:
                    self.assertEqual((yield fifo.r_level), i - ff_syncronizer_latency)
                else:
                    self.assertEqual((yield fifo.r_level), 0)

        simulator = Simulator(fifo)
        simulator.add_clock(100e-6)
        simulator.add_sync_process(testbench)
        simulator.run()

    def check_async_fifo_level(self, fifo, fill_in, expected_level, read=False):
        write_done = Signal()

        def write_process():
            for i in range(fill_in):
                yield fifo.w_data.eq(i)
                yield fifo.w_en.eq(1)
                yield Tick("write")
            yield fifo.w_en.eq(0)
            yield Tick("write")
            yield Tick("write")
            self.assertEqual((yield fifo.w_level), expected_level)
            yield write_done.eq(1)

        def read_process():
            if read:
                yield fifo.r_en.eq(1)
            while not (yield write_done):
                yield Tick("read")
            self.assertEqual((yield fifo.r_level), expected_level)

        simulator = Simulator(fifo)
        simulator.add_clock(100e-6, domain="write")
        simulator.add_sync_process(write_process, domain="write")
        simulator.add_clock(50e-6, domain="read")
        simulator.add_sync_process(read_process, domain="read")
        with simulator.write_vcd("test.vcd"):
            simulator.run()

    def test_async_fifo_level(self):
        fifo = AsyncFIFO(width=32, depth=8, r_domain="read", w_domain="write")
        self.check_async_fifo_level(fifo, fill_in=5, expected_level=5)

    def test_async_fifo_level_full(self):
        fifo = AsyncFIFO(width=32, depth=8, r_domain="read", w_domain="write")
        self.check_async_fifo_level(fifo, fill_in=10, expected_level=8)

    def test_async_buffered_fifo_level(self):
        fifo = AsyncFIFOBuffered(width=32, depth=9, r_domain="read", w_domain="write")
        self.check_async_fifo_level(fifo, fill_in=5, expected_level=5)

    def test_async_buffered_fifo_level_only_three(self):
        fifo = AsyncFIFOBuffered(width=32, depth=9, r_domain="read", w_domain="write")
        self.check_async_fifo_level(fifo, fill_in=3, expected_level=3)

    def test_async_buffered_fifo_level_full(self):
        fifo = AsyncFIFOBuffered(width=32, depth=9, r_domain="read", w_domain="write")
        self.check_async_fifo_level(fifo, fill_in=10, expected_level=9)

    def test_async_buffered_fifo_level_empty(self):
        fifo = AsyncFIFOBuffered(width=32, depth=9, r_domain="read", w_domain="write")
        self.check_async_fifo_level(fifo, fill_in=0, expected_level=0, read=True)
