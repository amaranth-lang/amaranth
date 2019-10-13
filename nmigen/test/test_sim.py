from contextlib import contextmanager

from .utils import *
from .._utils import flatten, union
from ..hdl.ast import *
from ..hdl.cd import  *
from ..hdl.mem import *
from ..hdl.rec import *
from ..hdl.dsl import  *
from ..hdl.ir import *
from ..back.pysim import *


class SimulatorUnitTestCase(FHDLTestCase):
    def assertStatement(self, stmt, inputs, output, reset=0):
        inputs = [Value.cast(i) for i in inputs]
        output = Value.cast(output)

        isigs = [Signal(i.shape(), name=n) for i, n in zip(inputs, "abcd")]
        osig  = Signal(output.shape(), name="y", reset=reset)

        stmt = stmt(osig, *isigs)
        frag = Fragment()
        frag.add_statements(stmt)
        for signal in flatten(s._lhs_signals() for s in Statement.cast(stmt)):
            frag.add_driver(signal)

        with Simulator(frag,
                vcd_file =open("test.vcd",  "w"),
                gtkw_file=open("test.gtkw", "w"),
                traces=[*isigs, osig]) as sim:
            def process():
                for isig, input in zip(isigs, inputs):
                    yield isig.eq(input)
                yield Delay()
                self.assertEqual((yield osig), output.value)
            sim.add_process(process)
            sim.run()

    def test_invert(self):
        stmt = lambda y, a: y.eq(~a)
        self.assertStatement(stmt, [C(0b0000, 4)], C(0b1111, 4))
        self.assertStatement(stmt, [C(0b1010, 4)], C(0b0101, 4))
        self.assertStatement(stmt, [C(0,      4)], C(-1,     4))

    def test_neg(self):
        stmt = lambda y, a: y.eq(-a)
        self.assertStatement(stmt, [C(0b0000, 4)], C(0b0000, 4))
        self.assertStatement(stmt, [C(0b0001, 4)], C(0b1111, 4))
        self.assertStatement(stmt, [C(0b1010, 4)], C(0b0110, 4))
        self.assertStatement(stmt, [C(1,      4)], C(-1,     4))
        self.assertStatement(stmt, [C(5,      4)], C(-5,     4))

    def test_bool(self):
        stmt = lambda y, a: y.eq(a.bool())
        self.assertStatement(stmt, [C(0, 4)], C(0))
        self.assertStatement(stmt, [C(1, 4)], C(1))
        self.assertStatement(stmt, [C(2, 4)], C(1))

    def test_any(self):
        stmt = lambda y, a: y.eq(a.any())
        self.assertStatement(stmt, [C(0b00, 2)], C(0))
        self.assertStatement(stmt, [C(0b01, 2)], C(1))
        self.assertStatement(stmt, [C(0b10, 2)], C(1))
        self.assertStatement(stmt, [C(0b11, 2)], C(1))

    def test_all(self):
        stmt = lambda y, a: y.eq(a.all())
        self.assertStatement(stmt, [C(0b00, 2)], C(0))
        self.assertStatement(stmt, [C(0b01, 2)], C(0))
        self.assertStatement(stmt, [C(0b10, 2)], C(0))
        self.assertStatement(stmt, [C(0b11, 2)], C(1))

    def test_xor_unary(self):
        stmt = lambda y, a: y.eq(a.xor())
        self.assertStatement(stmt, [C(0b00, 2)], C(0))
        self.assertStatement(stmt, [C(0b01, 2)], C(1))
        self.assertStatement(stmt, [C(0b10, 2)], C(1))
        self.assertStatement(stmt, [C(0b11, 2)], C(0))

    def test_add(self):
        stmt = lambda y, a, b: y.eq(a + b)
        self.assertStatement(stmt, [C(0,  4), C(1,  4)], C(1,   4))
        self.assertStatement(stmt, [C(-5, 4), C(-5, 4)], C(-10, 5))

    def test_sub(self):
        stmt = lambda y, a, b: y.eq(a - b)
        self.assertStatement(stmt, [C(2,  4), C(1,  4)], C(1,   4))
        self.assertStatement(stmt, [C(0,  4), C(1,  4)], C(-1,  4))
        self.assertStatement(stmt, [C(0,  4), C(10, 4)], C(-10, 5))

    def test_mul(self):
        stmt = lambda y, a, b: y.eq(a * b)
        self.assertStatement(stmt, [C(2,  4), C(1,  4)], C(2,   8))
        self.assertStatement(stmt, [C(2,  4), C(2,  4)], C(4,   8))
        self.assertStatement(stmt, [C(7,  4), C(7,  4)], C(49,  8))

    def test_floordiv(self):
        stmt = lambda y, a, b: y.eq(a // b)
        self.assertStatement(stmt, [C(2,  4), C(1,  4)], C(2,   8))
        self.assertStatement(stmt, [C(2,  4), C(2,  4)], C(1,   8))
        self.assertStatement(stmt, [C(7,  4), C(2,  4)], C(3,   8))

    def test_and(self):
        stmt = lambda y, a, b: y.eq(a & b)
        self.assertStatement(stmt, [C(0b1100, 4), C(0b1010, 4)], C(0b1000, 4))

    def test_or(self):
        stmt = lambda y, a, b: y.eq(a | b)
        self.assertStatement(stmt, [C(0b1100, 4), C(0b1010, 4)], C(0b1110, 4))

    def test_xor_binary(self):
        stmt = lambda y, a, b: y.eq(a ^ b)
        self.assertStatement(stmt, [C(0b1100, 4), C(0b1010, 4)], C(0b0110, 4))

    def test_shl(self):
        stmt = lambda y, a, b: y.eq(a << b)
        self.assertStatement(stmt, [C(0b1001, 4), C(0)],  C(0b1001,    5))
        self.assertStatement(stmt, [C(0b1001, 4), C(3)],  C(0b1001000, 7))
        self.assertStatement(stmt, [C(0b1001, 4), C(-2)], C(0b10,      7))

    def test_shr(self):
        stmt = lambda y, a, b: y.eq(a >> b)
        self.assertStatement(stmt, [C(0b1001, 4), C(0)],  C(0b1001,    4))
        self.assertStatement(stmt, [C(0b1001, 4), C(2)],  C(0b10,      4))
        self.assertStatement(stmt, [C(0b1001, 4), C(-2)], C(0b100100,  5))

    def test_eq(self):
        stmt = lambda y, a, b: y.eq(a == b)
        self.assertStatement(stmt, [C(0, 4), C(0, 4)], C(1))
        self.assertStatement(stmt, [C(0, 4), C(1, 4)], C(0))
        self.assertStatement(stmt, [C(1, 4), C(0, 4)], C(0))

    def test_ne(self):
        stmt = lambda y, a, b: y.eq(a != b)
        self.assertStatement(stmt, [C(0, 4), C(0, 4)], C(0))
        self.assertStatement(stmt, [C(0, 4), C(1, 4)], C(1))
        self.assertStatement(stmt, [C(1, 4), C(0, 4)], C(1))

    def test_lt(self):
        stmt = lambda y, a, b: y.eq(a < b)
        self.assertStatement(stmt, [C(0, 4), C(0, 4)], C(0))
        self.assertStatement(stmt, [C(0, 4), C(1, 4)], C(1))
        self.assertStatement(stmt, [C(1, 4), C(0, 4)], C(0))

    def test_ge(self):
        stmt = lambda y, a, b: y.eq(a >= b)
        self.assertStatement(stmt, [C(0, 4), C(0, 4)], C(1))
        self.assertStatement(stmt, [C(0, 4), C(1, 4)], C(0))
        self.assertStatement(stmt, [C(1, 4), C(0, 4)], C(1))

    def test_gt(self):
        stmt = lambda y, a, b: y.eq(a > b)
        self.assertStatement(stmt, [C(0, 4), C(0, 4)], C(0))
        self.assertStatement(stmt, [C(0, 4), C(1, 4)], C(0))
        self.assertStatement(stmt, [C(1, 4), C(0, 4)], C(1))

    def test_le(self):
        stmt = lambda y, a, b: y.eq(a <= b)
        self.assertStatement(stmt, [C(0, 4), C(0, 4)], C(1))
        self.assertStatement(stmt, [C(0, 4), C(1, 4)], C(1))
        self.assertStatement(stmt, [C(1, 4), C(0, 4)], C(0))

    def test_mux(self):
        stmt = lambda y, a, b, c: y.eq(Mux(c, a, b))
        self.assertStatement(stmt, [C(2, 4), C(3, 4), C(0)], C(3, 4))
        self.assertStatement(stmt, [C(2, 4), C(3, 4), C(1)], C(2, 4))

    def test_slice(self):
        stmt1 = lambda y, a: y.eq(a[2])
        self.assertStatement(stmt1, [C(0b10110100, 8)], C(0b1,  1))
        stmt2 = lambda y, a: y.eq(a[2:4])
        self.assertStatement(stmt2, [C(0b10110100, 8)], C(0b01, 2))

    def test_slice_lhs(self):
        stmt1 = lambda y, a: y[2].eq(a)
        self.assertStatement(stmt1, [C(0b0,  1)], C(0b11111011, 8), reset=0b11111111)
        stmt2 = lambda y, a: y[2:4].eq(a)
        self.assertStatement(stmt2, [C(0b01, 2)], C(0b11110111, 8), reset=0b11111011)

    def test_bit_select(self):
        stmt = lambda y, a, b: y.eq(a.bit_select(b, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(0)], C(0b100, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(2)], C(0b101, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(3)], C(0b110, 3))

    def test_bit_select_lhs(self):
        stmt = lambda y, a, b: y.bit_select(a, 3).eq(b)
        self.assertStatement(stmt, [C(0), C(0b100, 3)], C(0b11111100, 8), reset=0b11111111)
        self.assertStatement(stmt, [C(2), C(0b101, 3)], C(0b11110111, 8), reset=0b11111111)
        self.assertStatement(stmt, [C(3), C(0b110, 3)], C(0b11110111, 8), reset=0b11111111)

    def test_word_select(self):
        stmt = lambda y, a, b: y.eq(a.word_select(b, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(0)], C(0b100, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(1)], C(0b110, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(2)], C(0b010, 3))

    def test_word_select_lhs(self):
        stmt = lambda y, a, b: y.word_select(a, 3).eq(b)
        self.assertStatement(stmt, [C(0), C(0b100, 3)], C(0b11111100, 8), reset=0b11111111)
        self.assertStatement(stmt, [C(1), C(0b101, 3)], C(0b11101111, 8), reset=0b11111111)
        self.assertStatement(stmt, [C(2), C(0b110, 3)], C(0b10111111, 8), reset=0b11111111)

    def test_cat(self):
        stmt = lambda y, *xs: y.eq(Cat(*xs))
        self.assertStatement(stmt, [C(0b10, 2), C(0b01, 2)], C(0b0110, 4))

    def test_cat_lhs(self):
        l = Signal(3)
        m = Signal(3)
        n = Signal(3)
        stmt = lambda y, a: [Cat(l, m, n).eq(a), y.eq(Cat(n, m, l))]
        self.assertStatement(stmt, [C(0b100101110, 9)], C(0b110101100, 9))

    def test_record(self):
        rec = Record([
            ("l", 1),
            ("m", 2),
        ])
        stmt = lambda y, a: [rec.eq(a), y.eq(rec)]
        self.assertStatement(stmt, [C(0b101, 3)], C(0b101, 3))

    def test_repl(self):
        stmt = lambda y, a: y.eq(Repl(a, 3))
        self.assertStatement(stmt, [C(0b10, 2)], C(0b101010, 6))

    def test_array(self):
        array = Array([1, 4, 10])
        stmt = lambda y, a: y.eq(array[a])
        self.assertStatement(stmt, [C(0)], C(1))
        self.assertStatement(stmt, [C(1)], C(4))
        self.assertStatement(stmt, [C(2)], C(10))

    def test_array_oob(self):
        array = Array([1, 4, 10])
        stmt = lambda y, a: y.eq(array[a])
        self.assertStatement(stmt, [C(3)], C(10))
        self.assertStatement(stmt, [C(4)], C(10))

    def test_array_lhs(self):
        l = Signal(3, reset=1)
        m = Signal(3, reset=4)
        n = Signal(3, reset=7)
        array = Array([l, m, n])
        stmt = lambda y, a, b: [array[a].eq(b), y.eq(Cat(*array))]
        self.assertStatement(stmt, [C(0), C(0b000)], C(0b111100000))
        self.assertStatement(stmt, [C(1), C(0b010)], C(0b111010001))
        self.assertStatement(stmt, [C(2), C(0b100)], C(0b100100001))

    def test_array_lhs_oob(self):
        l = Signal(3)
        m = Signal(3)
        n = Signal(3)
        array = Array([l, m, n])
        stmt = lambda y, a, b: [array[a].eq(b), y.eq(Cat(*array))]
        self.assertStatement(stmt, [C(3), C(0b001)], C(0b001000000))
        self.assertStatement(stmt, [C(4), C(0b010)], C(0b010000000))

    def test_array_index(self):
        array = Array(Array(x * y for y in range(10)) for x in range(10))
        stmt = lambda y, a, b: y.eq(array[a][b])
        for x in range(10):
            for y in range(10):
                self.assertStatement(stmt, [C(x), C(y)], C(x * y))

    def test_array_attr(self):
        from collections import namedtuple
        pair = namedtuple("pair", ("p", "n"))

        array = Array(pair(x, -x) for x in range(10))
        stmt = lambda y, a: y.eq(array[a].p + array[a].n)
        for i in range(10):
            self.assertStatement(stmt, [C(i)], C(0))


class SimulatorIntegrationTestCase(FHDLTestCase):
    @contextmanager
    def assertSimulation(self, module, deadline=None):
        with Simulator(module) as sim:
            yield sim
            if deadline is None:
                sim.run()
            else:
                sim.run_until(deadline)

    def setUp_counter(self):
        self.count = Signal(3, reset=4)
        self.sync  = ClockDomain()

        self.m = Module()
        self.m.d.sync  += self.count.eq(self.count + 1)
        self.m.domains += self.sync

    def test_counter_process(self):
        self.setUp_counter()
        with self.assertSimulation(self.m) as sim:
            def process():
                self.assertEqual((yield self.count), 4)
                yield Delay(1e-6)
                self.assertEqual((yield self.count), 4)
                yield self.sync.clk.eq(1)
                self.assertEqual((yield self.count), 5)
                yield Delay(1e-6)
                self.assertEqual((yield self.count), 5)
                yield self.sync.clk.eq(0)
                self.assertEqual((yield self.count), 5)
                for _ in range(3):
                    yield Delay(1e-6)
                    yield self.sync.clk.eq(1)
                    yield Delay(1e-6)
                    yield self.sync.clk.eq(0)
                self.assertEqual((yield self.count), 0)
            sim.add_process(process)

    def test_counter_clock_and_sync_process(self):
        self.setUp_counter()
        with self.assertSimulation(self.m) as sim:
            sim.add_clock(1e-6, domain="sync")
            def process():
                self.assertEqual((yield self.count), 4)
                self.assertEqual((yield self.sync.clk), 1)
                yield
                self.assertEqual((yield self.count), 5)
                self.assertEqual((yield self.sync.clk), 1)
                for _ in range(3):
                    yield
                self.assertEqual((yield self.count), 0)
            sim.add_sync_process(process)

    def setUp_alu(self):
        self.a = Signal(8)
        self.b = Signal(8)
        self.o = Signal(8)
        self.x = Signal(8)
        self.s = Signal(2)
        self.sync = ClockDomain(reset_less=True)

        self.m = Module()
        self.m.d.comb += self.x.eq(self.a ^ self.b)
        with self.m.Switch(self.s):
            with self.m.Case(0):
                self.m.d.sync += self.o.eq(self.a + self.b)
            with self.m.Case(1):
                self.m.d.sync += self.o.eq(self.a - self.b)
            with self.m.Case():
                self.m.d.sync += self.o.eq(0)
        self.m.domains += self.sync

    def test_alu(self):
        self.setUp_alu()
        with self.assertSimulation(self.m) as sim:
            sim.add_clock(1e-6)
            def process():
                yield self.a.eq(5)
                yield self.b.eq(1)
                yield
                self.assertEqual((yield self.x), 4)
                yield
                self.assertEqual((yield self.o), 6)
                yield self.s.eq(1)
                yield
                yield
                self.assertEqual((yield self.o), 4)
                yield self.s.eq(2)
                yield
                yield
                self.assertEqual((yield self.o), 0)
            sim.add_sync_process(process)

    def setUp_multiclock(self):
        self.sys = ClockDomain()
        self.pix = ClockDomain()

        self.m = Module()
        self.m.domains += self.sys, self.pix

    def test_multiclock(self):
        self.setUp_multiclock()
        with self.assertSimulation(self.m) as sim:
            sim.add_clock(1e-6, domain="sys")
            sim.add_clock(0.3e-6, domain="pix")

            def sys_process():
                yield Passive()
                yield
                yield
                self.fail()
            def pix_process():
                yield
                yield
                yield
            sim.add_sync_process(sys_process, domain="sys")
            sim.add_sync_process(pix_process, domain="pix")

    def setUp_lhs_rhs(self):
        self.i = Signal(8)
        self.o = Signal(8)

        self.m = Module()
        self.m.d.comb += self.o.eq(self.i)

    def test_complex_lhs_rhs(self):
        self.setUp_lhs_rhs()
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.i.eq(0b10101010)
                yield self.i[:4].eq(-1)
                yield Delay()
                self.assertEqual((yield self.i[:4]), 0b1111)
                self.assertEqual((yield self.i), 0b10101111)
            sim.add_process(process)

    def test_run_until(self):
        m = Module()
        s = Signal()
        m.d.sync += s.eq(0)
        with self.assertSimulation(m, deadline=100e-6) as sim:
            sim.add_clock(1e-6)
            def process():
                for _ in range(101):
                    yield Delay(1e-6)
                self.fail()
            sim.add_process(process)

    def test_add_process_wrong(self):
        with self.assertSimulation(Module()) as sim:
            with self.assertRaises(TypeError,
                    msg="Cannot add a process 1 because it is not a generator or "
                        "a generator function"):
                sim.add_process(1)

    def test_add_clock_wrong_twice(self):
        m = Module()
        s = Signal()
        m.d.sync += s.eq(0)
        with self.assertSimulation(m) as sim:
            sim.add_clock(1)
            with self.assertRaises(ValueError,
                    msg="Domain 'sync' already has a clock driving it"):
                sim.add_clock(1)

    def test_add_clock_wrong_missing(self):
        m = Module()
        with self.assertSimulation(m) as sim:
            with self.assertRaises(ValueError,
                    msg="Domain 'sync' is not present in simulation"):
                sim.add_clock(1)

    def test_add_clock_if_exists(self):
        m = Module()
        with self.assertSimulation(m) as sim:
            sim.add_clock(1, if_exists=True)

    def test_eq_signal_unused_wrong(self):
        self.setUp_lhs_rhs()
        self.s = Signal()
        with self.assertSimulation(self.m) as sim:
            def process():
                with self.assertRaisesRegex(ValueError,
                        regex=r"Process .+? sent a request to set signal \(sig s\), "
                              r"which is not a part of simulation"):
                    yield self.s.eq(0)
                yield Delay()
            sim.add_process(process)

    def test_eq_signal_comb_wrong(self):
        self.setUp_lhs_rhs()
        with self.assertSimulation(self.m) as sim:
            def process():
                with self.assertRaisesRegex(ValueError,
                        regex=r"Process .+? sent a request to set signal \(sig o\), "
                              r"which is a part of combinatorial assignment in simulation"):
                    yield self.o.eq(0)
                yield Delay()
            sim.add_process(process)

    def test_command_wrong(self):
        with self.assertSimulation(Module()) as sim:
            def process():
                with self.assertRaisesRegex(TypeError,
                        regex=r"Received unsupported command 1 from process .+?"):
                    yield 1
                yield Delay()
            sim.add_process(process)

    def setUp_memory(self, rd_synchronous=True, rd_transparent=True, wr_granularity=None):
        self.m = Module()
        self.memory = Memory(width=8, depth=4, init=[0xaa, 0x55])
        self.m.submodules.rdport = self.rdport = \
            self.memory.read_port(domain="sync" if rd_synchronous else "comb",
                                  transparent=rd_transparent)
        self.m.submodules.wrport = self.wrport = \
            self.memory.write_port(granularity=wr_granularity)

    def test_memory_init(self):
        self.setUp_memory()
        with self.assertSimulation(self.m) as sim:
            def process():
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield self.rdport.addr.eq(1)
                yield
                yield
                self.assertEqual((yield self.rdport.data), 0x55)
                yield self.rdport.addr.eq(2)
                yield
                yield
                self.assertEqual((yield self.rdport.data), 0x00)
            sim.add_clock(1e-6)
            sim.add_sync_process(process)

    def test_memory_write(self):
        self.setUp_memory()
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.wrport.addr.eq(4)
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(1)
                yield
                yield self.wrport.en.eq(0)
                yield self.rdport.addr.eq(4)
                yield
                self.assertEqual((yield self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_sync_process(process)

    def test_memory_write_granularity(self):
        self.setUp_memory(wr_granularity=4)
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.wrport.data.eq(0x50)
                yield self.wrport.en.eq(0b00)
                yield
                yield self.wrport.en.eq(0)
                yield
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield self.wrport.en.eq(0b10)
                yield
                yield self.wrport.en.eq(0)
                yield
                self.assertEqual((yield self.rdport.data), 0x5a)
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(0b01)
                yield
                yield self.wrport.en.eq(0)
                yield
                self.assertEqual((yield self.rdport.data), 0x53)
            sim.add_clock(1e-6)
            sim.add_sync_process(process)

    def test_memory_read_before_write(self):
        self.setUp_memory(rd_transparent=False)
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(1)
                yield
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield Delay(1e-6) # let comb propagate
                self.assertEqual((yield self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_sync_process(process)

    def test_memory_write_through(self):
        self.setUp_memory(rd_transparent=True)
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(1)
                yield
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield Delay(1e-6) # let comb propagate
                self.assertEqual((yield self.rdport.data), 0x33)
                yield
                yield self.rdport.addr.eq(1)
                yield Delay(1e-6) # let comb propagate
                self.assertEqual((yield self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_sync_process(process)

    def test_memory_async_read_write(self):
        self.setUp_memory(rd_synchronous=False)
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.rdport.addr.eq(0)
                yield Delay()
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield self.rdport.addr.eq(1)
                yield Delay()
                self.assertEqual((yield self.rdport.data), 0x55)
                yield self.rdport.addr.eq(0)
                yield self.wrport.addr.eq(0)
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(1)
                yield Tick("sync")
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield Delay(1e-6) # let comb propagate
                self.assertEqual((yield self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_process(process)

    def test_memory_read_only(self):
        self.m = Module()
        self.memory = Memory(width=8, depth=4, init=[0xaa, 0x55])
        self.m.submodules.rdport = self.rdport = self.memory.read_port()
        with self.assertSimulation(self.m) as sim:
            def process():
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield self.rdport.addr.eq(1)
                yield
                yield
                self.assertEqual((yield self.rdport.data), 0x55)
            sim.add_clock(1e-6)
            sim.add_sync_process(process)

    def test_sample_helpers(self):
        m = Module()
        s = Signal(2)
        def mk(x):
            y = Signal.like(x)
            m.d.comb += y.eq(x)
            return y
        p0, r0, f0, s0 = mk(Past(s, 0)), mk(Rose(s)),    mk(Fell(s)),    mk(Stable(s))
        p1, r1, f1, s1 = mk(Past(s)),    mk(Rose(s, 1)), mk(Fell(s, 1)), mk(Stable(s, 1))
        p2, r2, f2, s2 = mk(Past(s, 2)), mk(Rose(s, 2)), mk(Fell(s, 2)), mk(Stable(s, 2))
        p3, r3, f3, s3 = mk(Past(s, 3)), mk(Rose(s, 3)), mk(Fell(s, 3)), mk(Stable(s, 3))
        with self.assertSimulation(m) as sim:
            def process_gen():
                yield s.eq(0b10)
                yield
                yield
                yield s.eq(0b01)
                yield
            def process_check():
                yield
                yield
                yield

                self.assertEqual((yield p0), 0b01)
                self.assertEqual((yield p1), 0b10)
                self.assertEqual((yield p2), 0b10)
                self.assertEqual((yield p3), 0b00)

                self.assertEqual((yield s0), 0b0)
                self.assertEqual((yield s1), 0b1)
                self.assertEqual((yield s2), 0b0)
                self.assertEqual((yield s3), 0b1)

                self.assertEqual((yield r0), 0b01)
                self.assertEqual((yield r1), 0b00)
                self.assertEqual((yield r2), 0b10)
                self.assertEqual((yield r3), 0b00)

                self.assertEqual((yield f0), 0b10)
                self.assertEqual((yield f1), 0b00)
                self.assertEqual((yield f2), 0b00)
                self.assertEqual((yield f3), 0b00)
            sim.add_clock(1e-6)
            sim.add_sync_process(process_gen)
            sim.add_sync_process(process_check)

    def test_wrong_not_run(self):
        with self.assertWarns(UserWarning,
                msg="Simulation created, but not run"):
            with Simulator(Fragment()) as sim:
                pass
