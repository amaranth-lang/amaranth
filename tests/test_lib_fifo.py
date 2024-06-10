# amaranth: UnusedElaboratable=no

import warnings

from amaranth.hdl import *
from amaranth.asserts import Initial, AnyConst
from amaranth.sim import *
from amaranth.lib.fifo import *
from amaranth.lib.memory import *

from .utils import *
from amaranth._utils import _ignore_deprecated


class FIFOTestCase(FHDLTestCase):
    def test_depth_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^FIFO width must be a non-negative integer, not -1$"):
            FIFOInterface(width=-1, depth=8)
        with self.assertRaisesRegex(TypeError,
                r"^FIFO depth must be a non-negative integer, not -1$"):
            FIFOInterface(width=8, depth=-1)

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
    def __init__(self, *, width, depth, r_domain, w_domain):
        super().__init__(width=width, depth=depth)

        self.r_domain = r_domain
        self.w_domain = w_domain

        self.level = Signal(range(self.depth + 1))
        self.r_level = Signal(range(self.depth + 1))
        self.w_level = Signal(range(self.depth + 1))

    def elaborate(self, platform):
        m = Module()

        storage = m.submodules.storage = Memory(shape=self.width, depth=self.depth, init=[])
        w_port  = storage.write_port(domain=self.w_domain)
        r_port  = storage.read_port (domain="comb")

        produce = Signal(range(self.depth))
        consume = Signal(range(self.depth))

        m.d.comb += self.r_rdy.eq(self.level > 0)
        m.d.comb += r_port.addr.eq((consume + 1) % self.depth)
        m.d.comb += self.r_data.eq(r_port.data)
        with m.If(self.r_en & self.r_rdy):
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
    def __init__(self, fifo, *, is_async=False):
        self.fifo = fifo
        self.is_async = is_async

        if is_async:
            self.cd_read = ClockDomain()
            self.cd_write = ClockDomain()
        else:
            self.cd_sync = ClockDomain()
            self.cd_read = self.cd_write = self.cd_sync

    @_ignore_deprecated
    def elaborate(self, platform):
        m = Module()

        if self.is_async:
            m.domains += self.cd_read
            m.domains += self.cd_write
        else:
            m.domains += self.cd_sync

        m.submodules.dut  = dut  = self.fifo
        m.submodules.gold = gold = FIFOModel(width=dut.width, depth=dut.depth,
                                             r_domain=self.cd_read.name,
                                             w_domain=self.cd_write.name)

        m.d.comb += [
            gold.r_en.eq(dut.r_rdy & dut.r_en),
            gold.w_en.eq(dut.w_en),
            gold.w_data.eq(dut.w_data),
        ]

        with m.If(dut.r_rdy):
            m.d.comb += Assert(gold.r_rdy)
        with m.If(dut.w_rdy):
            m.d.comb += Assert(gold.w_rdy)
        m.d.comb += Assert(dut.r_level == gold.r_level)
        m.d.comb += Assert(dut.w_level == gold.w_level)

        with m.If(dut.r_rdy):
            m.d.comb += Assert(dut.r_data == gold.r_data)

        return m


class FIFOContractSpec(Elaboratable):
    """
    The first-in first-out queue contract specification: if two elements are written to the queue
    consecutively, they must be read out consecutively at some later point, no matter all other
    circumstances, with the exception of reset.
    """
    def __init__(self, fifo, *, is_async=False, bound):
        self.fifo     = fifo
        self.is_async = is_async
        self.bound    = bound

        self.cd_sync = ClockDomain()
        if is_async:
            self.cd_read = ClockDomain()
            self.cd_write = ClockDomain()
        else:
            self.cd_read = self.cd_write = self.cd_sync

    @_ignore_deprecated
    def elaborate(self, platform):
        m = Module()
        m.submodules.dut = fifo = self.fifo

        m.domains += self.cd_sync
        m.d.comb += self.cd_sync.rst.eq(0)
        if self.is_async:
            m.domains += self.cd_read
            m.domains += self.cd_write
            m.d.comb += self.cd_write.rst.eq(0)
            m.d.comb += self.cd_read.rst.eq(0)

        entry_1 = AnyConst(fifo.width)
        entry_2 = AnyConst(fifo.width)

        with m.FSM(domain=self.cd_write.name) as write_fsm:
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

        with m.FSM(domain=self.cd_read.name) as read_fsm:
            read_1 = Signal(fifo.width)
            read_2 = Signal(fifo.width)
            with m.State("READ"):
                m.d.comb += fifo.r_en.eq(1)
                with m.If(fifo.r_rdy):
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

        cycle = Signal(range(self.bound + 1))
        m.d.sync += cycle.eq(cycle + 1)
        with m.If(Initial()):
            m.d.comb += Assume(cycle == 0)
        with m.If(cycle == self.bound):
            m.d.comb += Assert(read_fsm.ongoing("DONE"))

        with m.If(self.cd_write.rst):
            m.d.comb += Assert(~fifo.r_rdy)

        if self.is_async:
            # rose_w_domain_clk = Rose(self.cd_write.clk)
            past_w_domain_clk = Signal()
            m.d.sync += past_w_domain_clk.eq(self.cd_write.clk)
            rose_w_domain_clk = (past_w_domain_clk == 0) & (self.cd_write.clk == 1)
            # rose_r_domain_clk = Rose(self.cd_read.clk)
            past_r_domain_clk = Signal()
            m.d.sync += past_r_domain_clk.eq(self.cd_read.clk)
            rose_r_domain_clk = (past_r_domain_clk == 0) & (self.cd_read.clk == 1)

            m.d.comb += Assume(rose_w_domain_clk | rose_r_domain_clk)

        return m


class FIFOFormalCase(FHDLTestCase):
    def check_sync_fifo(self, fifo):
        spec_equiv = FIFOModelEquivalenceSpec(fifo, is_async=False)
        self.assertFormal(spec_equiv, [
                              spec_equiv.cd_sync.clk, spec_equiv.cd_sync.rst,
                              fifo.w_en, fifo.w_data, fifo.r_en,
                          ], mode="bmc", depth=fifo.depth + 1)
        spec_contract = FIFOContractSpec(fifo, is_async=False, bound=fifo.depth * 2 + 1)
        self.assertFormal(spec_contract, [spec_contract.cd_sync.clk],
                          mode="hybrid", depth=fifo.depth * 2 + 1)

    def test_sync_pot(self):
        self.check_sync_fifo(SyncFIFO(width=8, depth=4))

    def test_sync_npot(self):
        self.check_sync_fifo(SyncFIFO(width=8, depth=5))

    def test_sync_buffered_pot(self):
        self.check_sync_fifo(SyncFIFOBuffered(width=8, depth=4))

    def test_sync_buffered_potp1(self):
        self.check_sync_fifo(SyncFIFOBuffered(width=8, depth=5))

    def test_sync_buffered_potm1(self):
        self.check_sync_fifo(SyncFIFOBuffered(width=8, depth=3))

    def test_sync_buffered_one(self):
        self.check_sync_fifo(SyncFIFOBuffered(width=8, depth=1))

    def check_async_fifo(self, fifo):
        # TODO: properly doing model equivalence checking on this likely requires multiclock,
        # which is not really documented nor is it clear how to use it.
        # spec_equiv = FIFOModelEquivalenceSpec(fifo, is_async=True)
        # self.assertFormal(spec_equiv, [
        #                       spec_equiv.cd_write.clk, spec_equiv.cd_write.rst,
        #                       spec_equiv.cd_read.clk, spec_equiv.cd_read.rst,
        #                       fifo.w_en, fifo.w_data, fifo.r_en,
        #                   ],
        #                   mode="bmc", depth=fifo.depth * 3 + 1)
        spec_contract = FIFOContractSpec(fifo, is_async=True, bound=fifo.depth * 4 + 1)
        self.assertFormal(spec_contract, [
                              spec_contract.cd_sync.clk,
                              spec_contract.cd_write.clk,
                              spec_contract.cd_read.clk,
                          ], mode="hybrid", depth=fifo.depth * 4 + 1)

    def test_async(self):
        self.check_async_fifo(AsyncFIFO(width=8, depth=4))

    def test_async_buffered(self):
        self.check_async_fifo(AsyncFIFOBuffered(width=8, depth=4))


# we need this testcase because we cant do model equivalence checking on the async fifos (at the moment)
class AsyncFIFOSimCase(FHDLTestCase):
    def test_async_fifo_r_level_latency(self):
        fifo = AsyncFIFO(width=32, depth=10, r_domain="sync", w_domain="sync")

        ff_syncronizer_latency = 2

        async def testbench(ctx):
            for i in range(10):
                ctx.set(fifo.w_data, i)
                ctx.set(fifo.w_en, 1)
                _, _, r_level = await ctx.tick().sample(fifo.r_level)

                if (i - ff_syncronizer_latency) > 0:
                    self.assertEqual(r_level, i - ff_syncronizer_latency)
                else:
                    self.assertEqual(r_level, 0)

        simulator = Simulator(fifo)
        simulator.add_clock(100e-6)
        simulator.add_testbench(testbench)
        simulator.run()

    def check_async_fifo_level(self, fifo, fill_in, expected_level, read=False):
        write_done = Signal()

        async def testbench_write(ctx):
            for i in range(fill_in):
                ctx.set(fifo.w_data, i)
                ctx.set(fifo.w_en, 1)
                await ctx.tick("write")
            ctx.set(fifo.w_en, 0)
            await ctx.tick ("write")
            self.assertEqual(ctx.get(fifo.w_level), expected_level)
            ctx.set(write_done, 1)

        async def testbench_read(ctx):
            if read:
                ctx.set(fifo.r_en, 1)
            while not ctx.get(write_done):
                await ctx.tick("read")
            self.assertEqual(ctx.get(fifo.r_level), expected_level)

        simulator = Simulator(fifo)
        simulator.add_clock(100e-6, domain="write")
        simulator.add_testbench(testbench_write)
        simulator.add_clock(50e-6, domain="read")
        simulator.add_testbench(testbench_read)
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
