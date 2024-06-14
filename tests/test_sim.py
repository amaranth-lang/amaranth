import os
import warnings
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from textwrap import dedent

from amaranth._utils import flatten
from amaranth.hdl._ast import *
from amaranth.hdl._cd import  *
with warnings.catch_warnings():
    warnings.filterwarnings(action="ignore", category=DeprecationWarning)
    from amaranth.hdl.rec import *
from amaranth.hdl._dsl import *
from amaranth.hdl._mem import MemoryData
from amaranth.hdl._ir import *
from amaranth.sim import *
from amaranth.sim._pyeval import eval_format
from amaranth.lib.memory import Memory
from amaranth.lib import enum, data, wiring

from .utils import *
from amaranth._utils import _ignore_deprecated


class SimulatorUnitTestCase(FHDLTestCase):
    def assertStatement(self, stmt, inputs, output, init=0):
        inputs = [Value.cast(i) for i in inputs]
        output = Value.cast(output)

        isigs = [Signal(i.shape(), name=n) for i, n in zip(inputs, "abcd")]
        osig  = Signal(output.shape(), name="y", init=init)

        stmt = stmt(osig, *isigs)
        frag = Fragment()
        frag.add_statements("comb", stmt)

        sim = Simulator(frag)
        async def process(ctx):
            for isig, input in zip(isigs, inputs):
                ctx.set(isig, ctx.get(input))
            self.assertEqual(ctx.get(osig), output.value)
        sim.add_testbench(process)
        with sim.write_vcd("test.vcd", "test.gtkw", traces=[*isigs, osig]):
            sim.run()

        frag = Fragment()
        sim = Simulator(frag)
        async def process(ctx):
            for isig, input in zip(isigs, inputs):
                ctx.set(isig, ctx.get(input))
            if isinstance(stmt, Assign):
                ctx.set(stmt.lhs, ctx.get(stmt.rhs))
            else:
                for s in stmt:
                    ctx.set(s.lhs, ctx.get(s.rhs))
            self.assertEqual(ctx.get(osig), output.value)
        sim.add_testbench(process)
        with sim.write_vcd("test.vcd", "test.gtkw", traces=[*isigs, osig]):
            sim.run()


    def test_invert(self):
        stmt = lambda y, a: y.eq(~a)
        self.assertStatement(stmt, [C(0b0000, 4)], C(0b1111, 4))
        self.assertStatement(stmt, [C(0b1010, 4)], C(0b0101, 4))
        self.assertStatement(stmt, [C(0,      4)], C(-1,     4))
        self.assertStatement(stmt, [C(0b0000, signed(4))], C(-1, signed(4)))
        self.assertStatement(stmt, [C(0b1010, signed(4))], C(0b0101, signed(4)))

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

    def test_as_unsigned(self):
        stmt = lambda y, a, b: y.eq(a.as_unsigned() == b)
        self.assertStatement(stmt, [C(0b01, signed(2)), C(0b0001, unsigned(4))], C(1))
        self.assertStatement(stmt, [C(0b11, signed(2)), C(0b0011, unsigned(4))], C(1))

    def test_as_unsigned_lhs(self):
        stmt = lambda y, a: y.as_unsigned().eq(a)
        self.assertStatement(stmt, [C(0b01, unsigned(2))], C(0b0001, signed(4)))

    def test_as_signed(self):
        stmt = lambda y, a, b: y.eq(a.as_signed() == b)
        self.assertStatement(stmt, [C(0b01, unsigned(2)), C(0b0001, signed(4))], C(1))
        self.assertStatement(stmt, [C(0b11, unsigned(2)), C(0b1111, signed(4))], C(1))

    def test_as_signed_issue_502(self):
        stmt = lambda y, a: y.eq(a.as_signed())
        self.assertStatement(stmt, [C(0b01, unsigned(2))], C(0b0001, signed(4)))
        self.assertStatement(stmt, [C(0b11, unsigned(2))], C(0b1111, signed(4)))

    def test_as_signed_lhs(self):
        stmt = lambda y, a: y.as_signed().eq(a)
        self.assertStatement(stmt, [C(0b01, unsigned(2))], C(0b0001, signed(4)))

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
        self.assertStatement(stmt, [C(2,  4), C(0,  4)], C(0,   8))
        self.assertStatement(stmt, [C(2,  4), C(1,  4)], C(2,   8))
        self.assertStatement(stmt, [C(2,  4), C(2,  4)], C(1,   8))
        self.assertStatement(stmt, [C(7,  4), C(2,  4)], C(3,   8))

    def test_floordiv_neg(self):
        stmt = lambda y, a, b: y.eq(a // b)
        self.assertStatement(stmt, [C(-5, 4), C( 2, 4)], C(-3, 8))
        self.assertStatement(stmt, [C(-5, 4), C(-2, 4)], C( 2, 8))
        self.assertStatement(stmt, [C( 5, 4), C( 2, 4)], C( 2, 8))
        self.assertStatement(stmt, [C( 5, 4), C(-2, 4)], C(-3, 8))

    def test_mod(self):
        stmt = lambda y, a, b: y.eq(a % b)
        self.assertStatement(stmt, [C(2,  4), C(0,  4)], C(0,   8))
        self.assertStatement(stmt, [C(2,  4), C(1,  4)], C(0,   8))
        self.assertStatement(stmt, [C(2,  4), C(2,  4)], C(0,   8))
        self.assertStatement(stmt, [C(7,  4), C(2,  4)], C(1,   8))

    def test_mod_neg(self):
        stmt = lambda y, a, b: y.eq(a % b)
        self.assertStatement(stmt, [C(-5, 4), C( 3, 4)], C( 1, 8))
        self.assertStatement(stmt, [C(-5, 4), C(-3, 4)], C(-2, 8))
        self.assertStatement(stmt, [C( 5, 4), C( 3, 4)], C( 2, 8))
        self.assertStatement(stmt, [C( 5, 4), C(-3, 4)], C(-1, 8))

    def test_and(self):
        stmt = lambda y, a, b: y.eq(a & b)
        self.assertStatement(stmt, [C(0b1100, 4), C(0b1010, 4)], C(0b1000, 4))
        self.assertStatement(stmt, [C(0b1010, 4), C(0b10, signed(2))], C(0b1010, 4))
        stmt = lambda y, a: y.eq(a)
        self.assertStatement(stmt, [C(0b1010, 4) & C(-2, 2).as_unsigned()], C(0b0010, 4))

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

    def test_shr(self):
        stmt = lambda y, a, b: y.eq(a >> b)
        self.assertStatement(stmt, [C(0b1001, 4), C(0)],  C(0b1001,    4))
        self.assertStatement(stmt, [C(0b1001, 4), C(2)],  C(0b10,      4))

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
        stmt = lambda y, a: y.eq(a)
        self.assertStatement(stmt, [Mux(0, C(0b1010, 4), C(0b10, 2).as_signed())], C(0b1110, 4))
        self.assertStatement(stmt, [Mux(0, C(0b1010, 4), C(-2, 2).as_unsigned())], C(0b0010, 4))

    def test_mux_invert(self):
        stmt = lambda y, a, b, c: y.eq(Mux(~c, a, b))
        self.assertStatement(stmt, [C(2, 4), C(3, 4), C(0)], C(2, 4))
        self.assertStatement(stmt, [C(2, 4), C(3, 4), C(1)], C(3, 4))

    def test_mux_wide(self):
        stmt = lambda y, a, b, c: y.eq(Mux(c, a, b))
        self.assertStatement(stmt, [C(2, 4), C(3, 4), C(0, 2)], C(3, 4))
        self.assertStatement(stmt, [C(2, 4), C(3, 4), C(1, 2)], C(2, 4))
        self.assertStatement(stmt, [C(2, 4), C(3, 4), C(2, 2)], C(2, 4))

    def test_abs(self):
        stmt = lambda y, a: y.eq(abs(a))
        self.assertStatement(stmt, [C(3,  unsigned(8))], C(3,  unsigned(8)))
        self.assertStatement(stmt, [C(-3, unsigned(8))], C(-3, unsigned(8)))
        self.assertStatement(stmt, [C(3,  signed(8))],   C(3,  signed(8)))
        self.assertStatement(stmt, [C(-3, signed(8))],   C(3,  signed(8)))

    def test_slice(self):
        stmt1 = lambda y, a: y.eq(a[2])
        self.assertStatement(stmt1, [C(0b10110100, 8)], C(0b1,  1))
        stmt2 = lambda y, a: y.eq(a[2:4])
        self.assertStatement(stmt2, [C(0b10110100, 8)], C(0b01, 2))

    def test_slice_lhs(self):
        stmt1 = lambda y, a: y[2].eq(a)
        self.assertStatement(stmt1, [C(0b0,  1)], C(0b11111011, 8), init=0b11111111)
        stmt2 = lambda y, a: y[2:4].eq(a)
        self.assertStatement(stmt2, [C(0b01, 2)], C(0b11110111, 8), init=0b11111011)

    def test_bit_select(self):
        stmt = lambda y, a, b: y.eq(a.bit_select(b, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(0)], C(0b100, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(2)], C(0b101, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(3)], C(0b110, 3))

    def test_bit_select_lhs(self):
        stmt = lambda y, a, b: y.bit_select(a, 3).eq(b)
        self.assertStatement(stmt, [C(0), C(0b100, 3)], C(0b11111100, 8), init=0b11111111)
        self.assertStatement(stmt, [C(2), C(0b101, 3)], C(0b11110111, 8), init=0b11111111)
        self.assertStatement(stmt, [C(3), C(0b110, 3)], C(0b11110111, 8), init=0b11111111)

    def test_word_select(self):
        stmt = lambda y, a, b: y.eq(a.word_select(b, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(0)], C(0b100, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(1)], C(0b110, 3))
        self.assertStatement(stmt, [C(0b10110100, 8), C(2)], C(0b010, 3))

    def test_word_select_lhs(self):
        stmt = lambda y, a, b: y.word_select(a, 3).eq(b)
        self.assertStatement(stmt, [C(0), C(0b100, 3)], C(0b11111100, 8), init=0b11111111)
        self.assertStatement(stmt, [C(1), C(0b101, 3)], C(0b11101111, 8), init=0b11111111)
        self.assertStatement(stmt, [C(2), C(0b110, 3)], C(0b10111111, 8), init=0b11111111)

    def test_cat(self):
        stmt = lambda y, *xs: y.eq(Cat(*xs))
        self.assertStatement(stmt, [C(0b10, 2), C(0b01, 2)], C(0b0110, 4))

    def test_cat_lhs(self):
        l = Signal(3)
        m = Signal(3)
        n = Signal(3)
        stmt = lambda y, a: [Cat(l, m, n).eq(a), y.eq(Cat(n, m, l))]
        self.assertStatement(stmt, [C(0b100101110, 9)], C(0b110101100, 9))

    def test_cat_slice_lhs(self):
        l = Signal(3)
        m = Signal(3)
        n = Signal(3)
        o = Signal(3)
        p = Signal(3)
        stmt = lambda y, a: [Cat(l, m, n, o, p).eq(-1), Cat(l, m, n, o, p)[4:11].eq(a), y.eq(Cat(p, o, n, m, l))]
        self.assertStatement(stmt, [C(0b0000000, 7)], C(0b111001000100111, 15))
        self.assertStatement(stmt, [C(0b1001011, 7)], C(0b111111010110111, 15))
        self.assertStatement(stmt, [C(0b1111111, 7)], C(0b111111111111111, 15))

    def test_nested_cat_lhs(self):
        l = Signal(3)
        m = Signal(3)
        n = Signal(3)
        stmt = lambda y, a: [Cat(Cat(l, Cat(m)), n).eq(a), y.eq(Cat(n, m, l))]
        self.assertStatement(stmt, [C(0b100101110, 9)], C(0b110101100, 9))

    def test_record(self):
        rec = Record([
            ("l", 1),
            ("m", 2),
        ])
        stmt = lambda y, a: [rec.eq(a), y.eq(rec)]
        self.assertStatement(stmt, [C(0b101, 3)], C(0b101, 3))

    def test_replicate(self):
        stmt = lambda y, a: y.eq(a.replicate(3))
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
        self.assertStatement(stmt, [C(3)], C(0))
        self.assertStatement(stmt, [C(4)], C(0))

    def test_array_lhs(self):
        l = Signal(3, init=1)
        m = Signal(3, init=4)
        n = Signal(3, init=7)
        array = Array([l, m, n])
        stmt = lambda y, a, b: [array[a].eq(b), y.eq(Cat(*array))]
        self.assertStatement(stmt, [C(0), C(0b000)], C(0b111100000))
        self.assertStatement(stmt, [C(1), C(0b010)], C(0b111010001))
        self.assertStatement(stmt, [C(2), C(0b100)], C(0b100100001))

    def test_array_lhs_heterogenous(self):
        l = Signal(1, init=1)
        m = Signal(3, init=4)
        n = Signal(5, init=7)
        array = Array([l, m, n])
        stmt = lambda y, a, b: [array[a].eq(b), y.eq(Cat(*array))]
        self.assertStatement(stmt, [C(0), C(0b000)], C(0b001111000, 9))
        self.assertStatement(stmt, [C(1), C(0b010)], C(0b001110101, 9))
        self.assertStatement(stmt, [C(2), C(0b100)], C(0b001001001, 9))

    def test_array_lhs_heterogenous_slice(self):
        l = Signal(1, init=1)
        m = Signal(3, init=4)
        n = Signal(5, init=7)
        array = Array([l, m, n])
        stmt = lambda y, a, b: [array[a].as_value()[2:].eq(b), y.eq(Cat(*array))]
        self.assertStatement(stmt, [C(0), C(0b000)], C(0b001111001, 9))
        self.assertStatement(stmt, [C(1), C(0b010)], C(0b001110001, 9))
        self.assertStatement(stmt, [C(2), C(0b100)], C(0b100111001, 9))

    def test_array_lhs_oob(self):
        l = Signal(3)
        m = Signal(3)
        n = Signal(3)
        array = Array([l, m, n])
        stmt = lambda y, a, b: [array[a].eq(b), y.eq(Cat(*array))]
        self.assertStatement(stmt, [C(3), C(0b001)], C(0))
        self.assertStatement(stmt, [C(4), C(0b010)], C(0))

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

    def test_shift_left(self):
        stmt1 = lambda y, a: y.eq(a.shift_left(1))
        self.assertStatement(stmt1, [C(0b10100010, 8)], C(   0b101000100, 9))
        stmt2 = lambda y, a: y.eq(a.shift_left(4))
        self.assertStatement(stmt2, [C(0b10100010, 8)], C(0b101000100000, 12))

    def test_shift_right(self):
        stmt1 = lambda y, a: y.eq(a.shift_right(1))
        self.assertStatement(stmt1, [C(0b10100010, 8)], C(0b1010001, 7))
        stmt2 = lambda y, a: y.eq(a.shift_right(4))
        self.assertStatement(stmt2, [C(0b10100010, 8)], C(   0b1010, 4))

    def test_rotate_left(self):
        stmt = lambda y, a: y.eq(a.rotate_left(1))
        self.assertStatement(stmt, [C(0b1)], C(0b1))
        self.assertStatement(stmt, [C(0b1001000)], C(0b0010001))
        stmt = lambda y, a: y.eq(a.rotate_left(5))
        self.assertStatement(stmt, [C(0b1000000)], C(0b0010000))
        self.assertStatement(stmt, [C(0b1000001)], C(0b0110000))
        stmt = lambda y, a: y.eq(a.rotate_left(7))
        self.assertStatement(stmt, [C(0b1000000)], C(0b1000000))
        self.assertStatement(stmt, [C(0b1000001)], C(0b1000001))
        stmt = lambda y, a: y.eq(a.rotate_left(9))
        self.assertStatement(stmt, [C(0b1000000)], C(0b0000010))
        self.assertStatement(stmt, [C(0b1000001)], C(0b0000110))
        stmt = lambda y, a: y.eq(a.rotate_left(-1))
        self.assertStatement(stmt, [C(0b1)], C(0b1))
        self.assertStatement(stmt, [C(0b1001000)], C(0b0100100))
        stmt = lambda y, a: y.eq(a.rotate_left(-5))
        self.assertStatement(stmt, [C(0b1000000)], C(0b0000010))
        self.assertStatement(stmt, [C(0b1000001)], C(0b0000110))
        stmt = lambda y, a: y.eq(a.rotate_left(-7))
        self.assertStatement(stmt, [C(0b1000000)], C(0b1000000))
        self.assertStatement(stmt, [C(0b1000001)], C(0b1000001))
        stmt = lambda y, a: y.eq(a.rotate_left(-9))
        self.assertStatement(stmt, [C(0b1000000)], C(0b0010000))
        self.assertStatement(stmt, [C(0b1000001)], C(0b0110000))

    def test_rotate_right(self):
        stmt = lambda y, a: y.eq(a.rotate_right(1))
        self.assertStatement(stmt, [C(0b1)], C(0b1))
        self.assertStatement(stmt, [C(0b1001000)], C(0b0100100))
        stmt = lambda y, a: y.eq(a.rotate_right(5))
        self.assertStatement(stmt, [C(0b1000000)], C(0b0000010))
        self.assertStatement(stmt, [C(0b1000001)], C(0b0000110))
        stmt = lambda y, a: y.eq(a.rotate_right(7))
        self.assertStatement(stmt, [C(0b1000000)], C(0b1000000))
        self.assertStatement(stmt, [C(0b1000001)], C(0b1000001))
        stmt = lambda y, a: y.eq(a.rotate_right(9))
        self.assertStatement(stmt, [C(0b1000000)], C(0b0010000))
        self.assertStatement(stmt, [C(0b1000001)], C(0b0110000))
        stmt = lambda y, a: y.eq(a.rotate_right(-1))
        self.assertStatement(stmt, [C(0b1)], C(0b1))
        self.assertStatement(stmt, [C(0b1001000)], C(0b0010001))
        stmt = lambda y, a: y.eq(a.rotate_right(-5))
        self.assertStatement(stmt, [C(0b1000000)], C(0b0010000))
        self.assertStatement(stmt, [C(0b1000001)], C(0b0110000))
        stmt = lambda y, a: y.eq(a.rotate_right(-7))
        self.assertStatement(stmt, [C(0b1000000)], C(0b1000000))
        self.assertStatement(stmt, [C(0b1000001)], C(0b1000001))
        stmt = lambda y, a: y.eq(a.rotate_right(-9))
        self.assertStatement(stmt, [C(0b1000000)], C(0b0000010))
        self.assertStatement(stmt, [C(0b1000001)], C(0b0000110))


class SimulatorIntegrationTestCase(FHDLTestCase):
    @contextmanager
    def assertSimulation(self, module, *, deadline=None, traces=[]):
        sim = Simulator(module)
        yield sim
        with sim.write_vcd("test.vcd", "test.gtkw", traces=traces):
            if deadline is None:
                sim.run()
            else:
                sim.run_until(deadline)

    def setUp_counter(self):
        self.count = Signal(3, init=4)
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
                self.assertEqual((yield self.count), 4)
                with _ignore_deprecated():
                    yield Settle()
                self.assertEqual((yield self.count), 5)
                yield Delay(1e-6)
                self.assertEqual((yield self.count), 5)
                yield self.sync.clk.eq(0)
                self.assertEqual((yield self.count), 5)
                with _ignore_deprecated():
                    yield Settle()
                self.assertEqual((yield self.count), 5)
                for _ in range(3):
                    yield Delay(1e-6)
                    yield self.sync.clk.eq(1)
                    yield Delay(1e-6)
                    yield self.sync.clk.eq(0)
                self.assertEqual((yield self.count), 0)
            with _ignore_deprecated():
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
            with _ignore_deprecated():
                sim.add_sync_process(process)

    def test_reset(self):
        self.setUp_counter()
        sim = Simulator(self.m)
        sim.add_clock(1e-6)
        times = 0
        async def testbench(ctx):
            nonlocal times
            await ctx.tick()
            self.assertEqual(ctx.get(self.count), 5)
            await ctx.tick()
            self.assertEqual(ctx.get(self.count), 6)
            await ctx.tick()
            self.assertEqual(ctx.get(self.count), 7)
            await ctx.tick()
            times += 1
        sim.add_testbench(testbench)
        sim.run()
        sim.reset()
        sim.run()
        self.assertEqual(times, 2)

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
            with self.m.Case():
                self.m.d.sync += self.o.eq(self.a * self.b)
            with self.m.Case(1):
                self.m.d.sync += self.o.eq(self.a - self.b)
            with self.m.Default():
                self.m.d.sync += self.o.eq(0)
        self.m.domains += self.sync

    def test_alu(self):
        self.setUp_alu()
        with self.assertSimulation(self.m) as sim:
            sim.add_clock(1e-6)
            def process():
                yield self.a.eq(5)
                yield self.b.eq(1)
                yield Tick()
                self.assertEqual((yield self.x), 4)
                yield Tick()
                self.assertEqual((yield self.o), 6)
                yield self.s.eq(1)
                yield Tick()
                yield Tick()
                self.assertEqual((yield self.o), 4)
                yield self.s.eq(2)
                yield Tick()
                yield Tick()
                self.assertEqual((yield self.o), 0)
            with _ignore_deprecated():
                sim.add_process(process)

    def test_alu_bench(self):
        self.setUp_alu()
        with self.assertSimulation(self.m) as sim:
            sim.add_clock(1e-6)
            async def testbench(ctx):
                ctx.set(self.a, 5)
                ctx.set(self.b, 1)
                self.assertEqual(ctx.get(self.x), 4)
                await ctx.tick()
                self.assertEqual(ctx.get(self.o), 6)
                ctx.set(self.s, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(self.o), 4)
                ctx.set(self.s, 2)
                await ctx.tick()
                self.assertEqual(ctx.get(self.o), 0)
            sim.add_testbench(testbench)

    def setUp_clock_phase(self):
        self.m = Module()
        self.phase0 = self.m.domains.phase0 = ClockDomain()
        self.phase90 = self.m.domains.phase90 = ClockDomain()
        self.phase180 = self.m.domains.phase180 = ClockDomain()
        self.phase270 = self.m.domains.phase270 = ClockDomain()
        self.check = self.m.domains.check = ClockDomain()

        self.expected = [
            [0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1],
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0],
        ]

    def test_clock_phase(self):
        self.setUp_clock_phase()
        with self.assertSimulation(self.m) as sim:
            period=1
            sim.add_clock(period/8, phase=0,          domain="check")
            sim.add_clock(period,   phase=0*period/4, domain="phase0")
            sim.add_clock(period,   phase=1*period/4, domain="phase90")
            sim.add_clock(period,   phase=2*period/4, domain="phase180")
            sim.add_clock(period,   phase=3*period/4, domain="phase270")

            async def proc(ctx):
                clocks = [
                    self.phase0.clk,
                    self.phase90.clk,
                    self.phase180.clk,
                    self.phase270.clk
                ]
                for i in range(16):
                    await ctx.tick("check")
                    for j, c in enumerate(clocks):
                        self.assertEqual(ctx.get(c), self.expected[j][i])

            sim.add_process(proc)

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

            async def sys_process(ctx):
                await ctx.tick("sys")
                await ctx.tick("sys")
                self.fail()
            async def pix_process(ctx):
                await ctx.tick("pix")
                await ctx.tick("pix")
                await ctx.tick("pix")
            sim.add_testbench(sys_process, background=True)
            sim.add_testbench(pix_process)

    def setUp_lhs_rhs(self):
        self.i = Signal(8)
        self.o = Signal(8)

        self.m = Module()
        self.m.d.comb += self.o.eq(self.i)

    def test_complex_lhs_rhs(self):
        self.setUp_lhs_rhs()
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                ctx.set(self.i, 0b10101010)
                ctx.set(self.i[:4], -1)
                self.assertEqual(ctx.get(self.i[:4]), 0b1111)
                self.assertEqual(ctx.get(self.i), 0b10101111)
            sim.add_testbench(testbench)

    def test_run_until(self):
        m = Module()
        s = Signal()
        m.d.sync += s.eq(0)
        with self.assertSimulation(m, deadline=100e-6) as sim:
            sim.add_clock(1e-6)
            async def process(ctx):
                for _ in range(101):
                    await ctx.delay(1e-6)
                self.fail()
            sim.add_testbench(process)

    def test_run_until_fail(self):
        m = Module()
        s = Signal()
        m.d.sync += s.eq(0)
        with self.assertRaises(AssertionError):
            with self.assertSimulation(m, deadline=100e-6) as sim:
                sim.add_clock(1e-6)
                async def process(ctx):
                    for _ in range(99):
                        await ctx.delay(1e-6)
                    self.fail()
                sim.add_testbench(process)

    def test_add_process_wrong(self):
        with self.assertSimulation(Module()) as sim:
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot add a process 1 because it is not an async function or "
                    r"generator function$"):
                sim.add_process(1)

    def test_add_process_wrong_generator(self):
        with self.assertSimulation(Module()) as sim:
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot add a process <.+?> because it is not an async function or "
                    r"generator function$"):
                def process():
                    yield Delay()
                sim.add_process(process())

    def test_add_testbench_wrong(self):
        with self.assertSimulation(Module()) as sim:
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot add a testbench 1 because it is not an async function or "
                    r"generator function$"):
                sim.add_testbench(1)

    def test_add_testbench_wrong_generator(self):
        with self.assertSimulation(Module()) as sim:
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot add a testbench <.+?> because it is not an async function or "
                    r"generator function$"):
                def testbench():
                    yield Delay()
                sim.add_testbench(testbench())

    def test_add_clock_wrong_twice(self):
        m = Module()
        s = Signal()
        m.d.sync += s.eq(0)
        with self.assertSimulation(m) as sim:
            sim.add_clock(1)
            with self.assertRaisesRegex(DriverConflict,
                    r"^Domain 'sync' already has a clock driving it$"):
                sim.add_clock(1)

    def test_add_clock_wrong_missing(self):
        m = Module()
        with self.assertSimulation(m) as sim:
            with self.assertRaisesRegex(NameError,
                    r"^Domain 'sync' is not present in simulation$"):
                sim.add_clock(1)

    def test_add_clock_if_exists(self):
        m = Module()
        with self.assertSimulation(m) as sim:
            sim.add_clock(1, if_exists=True)

    def test_command_wrong(self):
        survived = False
        with self.assertSimulation(Module()) as sim:
            def process():
                nonlocal survived
                with self.assertRaisesRegex(TypeError,
                        r"Received unsupported command 1 from process .+?"):
                    yield 1
                survived = True
            with _ignore_deprecated():
                sim.add_process(process)
        self.assertTrue(survived)

    def test_sync_command_wrong(self):
        survived = False
        m = Module()
        dummy = Signal()
        m.d.sync += dummy.eq(1)
        with self.assertSimulation(m) as sim:
            def process():
                nonlocal survived
                with self.assertRaisesRegex(TypeError,
                        r"Received unsupported command 1 from process .+?"):
                    yield 1
                survived = True
            with _ignore_deprecated():
                sim.add_sync_process(process)
            sim.add_clock(1e-6)
        self.assertTrue(survived)

    def test_value_castable(self):
        class MyValue(ValueCastable):
            def as_value(self):
                return Signal()

            def shape():
                return unsigned(1)

        a = Array([1,2,3])
        a[MyValue()]

    def test_bench_command_wrong(self):
        survived = False
        with self.assertSimulation(Module()) as sim:
            def process():
                nonlocal survived
                with self.assertWarnsRegex(DeprecationWarning,
                        r"The `Settle` command is deprecated"):
                    settle = Settle()
                with self.assertRaisesRegex(TypeError,
                        r"Command \(settle\) is not allowed in testbenches"):
                    yield settle
                survived = True
            with _ignore_deprecated():
                sim.add_testbench(process)
        self.assertTrue(survived)

    def setUp_memory(self, rd_synchronous=True, rd_transparent=False, wr_granularity=None):
        self.m = Module()
        self.memory = self.m.submodules.memory = Memory(shape=8, depth=4, init=[0xaa, 0x55])
        self.wrport = self.memory.write_port(granularity=wr_granularity)
        self.rdport = self.memory.read_port(domain="sync" if rd_synchronous else "comb",
                                            transparent_for=[self.wrport] if rd_transparent else [])

    def test_memory_init(self):
        self.setUp_memory()
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                ctx.set(self.rdport.addr, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0x55)
                ctx.set(self.rdport.addr, 2)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0x00)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_write(self):
        self.setUp_memory()
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                ctx.set(self.wrport.addr, 4)
                ctx.set(self.wrport.data, 0x33)
                ctx.set(self.wrport.en, 1)
                await ctx.tick()
                ctx.set(self.wrport.en, 0)
                ctx.set(self.rdport.addr, 4)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_write_granularity(self):
        self.setUp_memory(wr_granularity=4)
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                ctx.set(self.wrport.data, 0x50)
                ctx.set(self.wrport.en, 0b00)
                await ctx.tick()
                ctx.set(self.wrport.en, 0)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0xaa)
                ctx.set(self.wrport.en, 0b10)
                await ctx.tick()
                ctx.set(self.wrport.en, 0)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0x5a)
                ctx.set(self.wrport.data, 0x33)
                ctx.set(self.wrport.en, 0b01)
                await ctx.tick()
                ctx.set(self.wrport.en, 0)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0x53)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_read_before_write(self):
        self.setUp_memory(rd_transparent=False)
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                ctx.set(self.wrport.data, 0x33)
                ctx.set(self.wrport.en, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0xaa)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_write_through(self):
        self.setUp_memory(rd_transparent=True)
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                await ctx.tick()
                ctx.set(self.wrport.data, 0x33)
                ctx.set(self.wrport.en, 1)
                self.assertEqual(ctx.get(self.rdport.data), 0xaa)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0x33)
                await ctx.tick()
                ctx.set(self.rdport.addr, 1)
                self.assertEqual(ctx.get(self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_async_read_write(self):
        self.setUp_memory(rd_synchronous=False)
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                ctx.set(self.rdport.addr, 0)
                self.assertEqual(ctx.get(self.rdport.data), 0xaa)
                ctx.set(self.rdport.addr, 1)
                self.assertEqual(ctx.get(self.rdport.data), 0x55)
                ctx.set(self.rdport.addr, 0)
                ctx.set(self.wrport.addr, 0)
                ctx.set(self.wrport.data, 0x33)
                ctx.set(self.wrport.en, 1)
                self.assertEqual(ctx.get(self.rdport.data), 0xaa)
                await ctx.tick("sync")
                self.assertEqual(ctx.get(self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_read_only(self):
        self.m = Module()
        self.m.submodules.memory = self.memory = Memory(shape=8, depth=4, init=[0xaa, 0x55])
        self.rdport = self.memory.read_port()
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0xaa)
                ctx.set(self.rdport.addr, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(self.rdport.data), 0x55)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_comb_bench_process(self):
        m = Module()
        a = Signal(init=1)
        b = Signal()
        m.d.comb += b.eq(a)
        with self.assertSimulation(m) as sim:
            async def testbench(ctx):
                self.assertEqual(ctx.get(a), 1)
                self.assertEqual(ctx.get(b), 1)
                ctx.set(a, 0)
                self.assertEqual(ctx.get(a), 0)
                self.assertEqual(ctx.get(b), 0)
            sim.add_testbench(testbench)

    def test_sync_bench_process(self):
        m = Module()
        a = Signal(init=1)
        b = Signal()
        m.d.sync += b.eq(a)
        t = Signal()
        m.d.sync += t.eq(~t)
        with self.assertSimulation(m) as sim:
            async def testbench(ctx):
                self.assertEqual(ctx.get(a), 1)
                self.assertEqual(ctx.get(b), 0)
                self.assertEqual(ctx.get(t), 0)
                await ctx.tick()
                self.assertEqual(ctx.get(a), 1)
                self.assertEqual(ctx.get(b), 1)
                self.assertEqual(ctx.get(t), 1)
                await ctx.tick()
                self.assertEqual(ctx.get(a), 1)
                self.assertEqual(ctx.get(b), 1)
                self.assertEqual(ctx.get(t), 0)
                ctx.set(a, 0)
                self.assertEqual(ctx.get(a), 0)
                self.assertEqual(ctx.get(b), 1)
                await ctx.tick()
                self.assertEqual(ctx.get(a), 0)
                self.assertEqual(ctx.get(b), 0)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_transparency_simple(self):
        m = Module()
        init = [0x11, 0x22, 0x33, 0x44]
        m.submodules.memory = memory = Memory(shape=8, depth=4, init=init)
        wrport = memory.write_port(granularity=8)
        rdport = memory.read_port(transparent_for=[wrport])
        with self.assertSimulation(m) as sim:
            async def testbench(ctx):
                ctx.set(rdport.addr, 0)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x11)
                ctx.set(rdport.addr, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x22)
                ctx.set(wrport.addr, 0)
                ctx.set(wrport.data, 0x44444444)
                ctx.set(wrport.en, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x22)
                ctx.set(wrport.addr, 1)
                ctx.set(wrport.data, 0x55)
                ctx.set(wrport.en, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x55)
                ctx.set(wrport.addr, 1)
                ctx.set(wrport.data, 0x66)
                ctx.set(wrport.en, 1)
                ctx.set(rdport.en, 0)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x55)
                ctx.set(wrport.addr, 2)
                ctx.set(wrport.data, 0x77)
                ctx.set(wrport.en, 1)
                ctx.set(rdport.en, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x66)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_transparency_multibit(self):
        m = Module()
        init = [0x11111111, 0x22222222, 0x33333333, 0x44444444]
        m.submodules.memory = memory = Memory(shape=32, depth=4, init=init)
        wrport = memory.write_port(granularity=8)
        rdport = memory.read_port(transparent_for=[wrport])
        with self.assertSimulation(m) as sim:
            async def testbench(ctx):
                ctx.set(rdport.addr, 0)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x11111111)
                ctx.set(rdport.addr, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x22222222)
                ctx.set(wrport.addr, 0)
                ctx.set(wrport.data, 0x44444444)
                ctx.set(wrport.en, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x22222222)
                ctx.set(wrport.addr, 1)
                ctx.set(wrport.data, 0x55555555)
                ctx.set(wrport.en, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x22222255)
                ctx.set(wrport.addr, 1)
                ctx.set(wrport.data, 0x66666666)
                ctx.set(wrport.en, 2)
                ctx.set(rdport.en, 0)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x22222255)
                ctx.set(wrport.addr, 1)
                ctx.set(wrport.data, 0x77777777)
                ctx.set(wrport.en, 4)
                ctx.set(rdport.en, 1)
                await ctx.tick()
                self.assertEqual(ctx.get(rdport.data), 0x22776655)
            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_access(self):
        self.setUp_memory()
        with self.assertSimulation(self.m) as sim:
            async def testbench(ctx):
                self.assertEqual(ctx.get(self.memory.data[1]), 0x55)
                self.assertEqual(ctx.get(self.memory.data[1]), 0x55)
                self.assertEqual(ctx.get(self.memory.data[2]), 0x00)
                ctx.set(self.memory.data[1], Const(0x33))
                self.assertEqual(ctx.get(self.memory.data[1]), 0x33)
                ctx.set(self.memory.data[1][2:5], Const(0x7))
                self.assertEqual(ctx.get(self.memory.data[1]), 0x3f)
                ctx.set(self.wrport.addr, 3)
                ctx.set(self.wrport.data, 0x22)
                ctx.set(self.wrport.en, 1)
                self.assertEqual(ctx.get(self.memory.data[3]), 0)
                await ctx.tick()
                self.assertEqual(ctx.get(self.memory.data[3]), 0x22)

            sim.add_clock(1e-6)
            sim.add_testbench(testbench)

    def test_memory_access_sync(self):
        self.setUp_memory()
        with self.assertSimulation(self.m) as sim:
            def process():
                self.assertEqual((yield self.memory.data[1]), 0x55)
                self.assertEqual((yield self.memory.data[1]), 0x55)
                self.assertEqual((yield self.memory.data[2]), 0x00)
                yield self.memory.data[1].eq(Const(0x33))
                self.assertEqual((yield self.memory.data[1]), 0x55)
                yield Tick()
                self.assertEqual((yield self.memory.data[1]), 0x33)

            sim.add_clock(1e-6)
            with _ignore_deprecated():
                sim.add_process(process)

    def test_vcd_wrong_nonzero_time(self):
        s = Signal()
        m = Module()
        m.d.sync += s.eq(s)
        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.run_until(1e-5)
        with self.assertRaisesRegex(ValueError,
                r"^Cannot start writing waveforms after advancing simulation time$"):
            with open(os.path.devnull, "w") as f:
                with sim.write_vcd(f):
                    pass

    def test_vcd_private_signal(self):
        sim = Simulator(Module())
        with self.assertRaisesRegex(TypeError,
                r"^Cannot trace signal with private name$"):
            with open(os.path.devnull, "w") as f:
                with sim.write_vcd(f, traces=(Signal(name=""),)):
                    pass

        sim = Simulator(Module())
        with self.assertRaisesRegex(TypeError,
                r"^Cannot trace signal with private name \(within \(cat \(sig x\) \(sig\)\)\)$"):
            with open(os.path.devnull, "w") as f:
                with sim.write_vcd(f, traces=(Cat(Signal(name="x"), Signal(name="")),)):
                    pass

    def test_no_negated_boolean_warning(self):
        m = Module()
        a = Signal()
        b = Signal()
        m.d.comb += a.eq(~(b == b))
        with warnings.catch_warnings(record=True) as warns:
            Simulator(m).run()
            self.assertEqual(warns, [])

    def test_large_expr_parser_overflow(self):
        m = Module()
        a = Signal()

        op = a
        for _ in range(50):
            op = (op ^ 1)

        op = op & op

        m.d.comb += a.eq(op)
        Simulator(m)

    def test_switch_zero(self):
        m = Module()
        a = Signal(0)
        o = Signal()
        with m.Switch(a):
            with m.Case(""):
                m.d.comb += o.eq(1)
        with self.assertSimulation(m) as sim:
            async def testbench(ctx):
                self.assertEqual(ctx.get(o), 1)
            sim.add_testbench(testbench)

    def test_print(self):
        m = Module()
        ctr = Signal(16)
        m.d.sync += ctr.eq(ctr + 1)
        with m.If(ctr % 3 == 0):
            m.d.sync += Print(Format("Counter: {ctr:03d}", ctr=ctr))
        output = StringIO()
        with redirect_stdout(output):
            with self.assertSimulation(m) as sim:
                sim.add_clock(1e-6, domain="sync")
                async def testbench(ctx):
                    await ctx.delay(1e-5)
                sim.add_testbench(testbench)
        self.assertEqual(output.getvalue(), dedent("""\
            Counter: 000
            Counter: 003
            Counter: 006
            Counter: 009
        """))

    def test_print_str(self):
        def enc(s):
            return Cat(
                Const(b, 8)
                for b in s.encode()
            )

        m = Module()
        ctr = Signal(16)
        m.d.sync += ctr.eq(ctr + 1)
        msg = Signal(8 * 8)
        with m.If(ctr == 0):
            m.d.comb += msg.eq(enc("zero"))
        with m.Else():
            m.d.comb += msg.eq(enc("non-zero"))
        with m.If(ctr % 3 == 0):
            m.d.sync += Print(Format("Counter: {:>8s}", msg))
        output = StringIO()
        with redirect_stdout(output):
            with self.assertSimulation(m) as sim:
                sim.add_clock(1e-6, domain="sync")
                async def testbench(ctx):
                    await ctx.delay(1e-5)
                sim.add_testbench(testbench)
        self.assertEqual(output.getvalue(), dedent("""\
            Counter:     zero
            Counter: non-zero
            Counter: non-zero
            Counter: non-zero
        """))

    def test_print_enum(self):
        class MyEnum(enum.Enum, shape=unsigned(2)):
            A = 0
            B = 1
            CDE = 2

        sig = Signal(MyEnum)
        ctr = Signal(2)
        m = Module()
        m.d.comb += sig.eq(ctr)
        m.d.sync += [
            Print(sig),
            ctr.eq(ctr + 1),
        ]
        output = StringIO()
        with redirect_stdout(output):
            with self.assertSimulation(m) as sim:
                sim.add_clock(1e-6, domain="sync")
                async def testbench(ctx):
                    await ctx.tick().repeat(4)
                sim.add_testbench(testbench)
        self.assertEqual(output.getvalue(), dedent("""\
            A
            B
            CDE
            [unknown]
        """))


    def test_assert(self):
        m = Module()
        ctr = Signal(16)
        m.d.sync += ctr.eq(ctr + 1)
        m.d.sync += Assert(ctr < 4, Format("Counter too large: {}", ctr))
        with self.assertRaisesRegex(AssertionError,
                r"^Assertion violated: Counter too large: 4$"):
            with self.assertSimulation(m) as sim:
                sim.add_clock(1e-6, domain="sync")
                async def testbench(ctx):
                    await ctx.delay(1e-5)
                sim.add_testbench(testbench)

    def test_assume(self):
        m = Module()
        ctr = Signal(16)
        m.d.sync += ctr.eq(ctr + 1)
        m.d.comb += Assume(ctr < 4)
        with self.assertRaisesRegex(AssertionError,
                r"^Assumption violated$"):
            with self.assertSimulation(m) as sim:
                sim.add_clock(1e-6, domain="sync")
                async def testbench(ctx):
                    await ctx.delay(1e-5)
                sim.add_testbench(testbench)

    def test_cover(self):
        m = Module()
        ctr = Signal(16)
        m.d.sync += ctr.eq(ctr + 1)
        cover = Cover(ctr % 3 == 0, Format("Counter: {ctr:03d}", ctr=ctr))
        m.d.sync += cover
        m.d.sync += Cover(ctr % 3 == 1)
        output = StringIO()
        with redirect_stdout(output):
            with self.assertSimulation(m) as sim:
                sim.add_clock(1e-6, domain="sync")
                async def testbench(ctx):
                    await ctx.delay(1e-5)
                sim.add_testbench(testbench)
        self.assertRegex(output.getvalue(), dedent(r"""
            Coverage hit at .*test_sim\.py:\d+: Counter: 000
            Coverage hit at .*test_sim\.py:\d+: Counter: 003
            Coverage hit at .*test_sim\.py:\d+: Counter: 006
            Coverage hit at .*test_sim\.py:\d+: Counter: 009
        """).lstrip())

    def test_testbench_preemption(self):
        sig = Signal(8)
        def testbench_1():
            yield sig[0:4].eq(0b1010)
            yield sig[4:8].eq(0b0101)
        def testbench_2():
            yield Passive()
            while True:
                val = yield sig
                assert val in (0, 0b01011010), f"{val=:#010b}"
                yield Delay(0)
        sim = Simulator(Module())
        with _ignore_deprecated():
            sim.add_testbench(testbench_1)
            sim.add_testbench(testbench_2)
        with sim.write_vcd("test.vcd", fs_per_delta=1):
            sim.run()

    def test_eval_format(self):
        class MyEnum(enum.Enum, shape=2):
            A = 0
            B = 1
            C = 2

        sig = Signal(8)
        sig2 = Signal(MyEnum)
        sig3 = Signal(data.StructLayout({"a": signed(3), "b": 2}))
        sig4 = Signal(data.ArrayLayout(2, 4))
        sig5 = Signal(32, init=0x44434241)

        async def testbench(ctx):
            state = sim._engine._state
            ctx.set(sig, 123)
            self.assertEqual(eval_format(state, sig._format), "123")
            self.assertEqual(eval_format(state, Format("{:#04x}", sig)), "0x7b")
            self.assertEqual(eval_format(state, Format("sig={}", sig)), "sig=123")

            self.assertEqual(eval_format(state, sig2.as_value()._format), "A")
            ctx.set(sig2, 1)
            self.assertEqual(eval_format(state, sig2.as_value()._format), "B")
            ctx.set(sig2.as_value(), 3)
            self.assertEqual(eval_format(state, sig2.as_value()._format), "[unknown]")

            ctx.set(sig3, {"a": -4, "b": 1})
            self.assertEqual(eval_format(state, sig3.as_value()._format), "{a=-4, b=1}")

            ctx.set(sig4, [2, 3, 1, 0])
            self.assertEqual(eval_format(state, sig4.as_value()._format), "[2, 3, 1, 0]")

            self.assertEqual(eval_format(state, Format("{:s}", sig5)), "ABCD")
            self.assertEqual(eval_format(state, Format("{:<5s}", sig5)), "ABCD ")

        with self.assertSimulation(Module(), traces=[sig, sig2, sig3, sig4, sig5]) as sim:
            sim.add_testbench(testbench)

    def test_decoder(self):
        def decoder(val):
            return f".oO{val}Oo."

        sig = Signal(2, decoder=decoder)

        async def testbench(ctx):
            await ctx.delay(1e-6)
            ctx.set(sig, 1)
            await ctx.delay(1e-6)
            ctx.set(sig, 2)
            await ctx.delay(1e-6)

        with self.assertSimulation(Module(), traces=[sig]) as sim:
            sim.add_testbench(testbench)

    def test_mem_shape(self):
        class MyEnum(enum.Enum, shape=2):
            A = 0
            B = 1
            C = 2

        mem1 = MemoryData(shape=8, depth=4, init=[1, 2, 3])
        mem2 = MemoryData(shape=MyEnum, depth=4, init=[MyEnum.A, MyEnum.B, MyEnum.C])
        mem3 = MemoryData(shape=data.StructLayout({"a": signed(3), "b": 2}), depth=4, init=[{"a": 2, "b": 1}])

        async def testbench(ctx):
            await ctx.delay(1e-6)
            ctx.set(mem1[0], 4)
            ctx.set(mem2[3], MyEnum.C)
            ctx.set(mem3[2], {"a": -1, "b": 2})
            await ctx.delay(1e-6)

        with self.assertSimulation(Module(), traces=[mem1, mem2, mem3]) as sim:
            sim.add_testbench(testbench)


class SimulatorTracesTestCase(FHDLTestCase):
    def assertDef(self, traces, flat_traces):
        frag = Fragment()

        async def testbench(ctx):
            await ctx.delay(1e-6)

        sim = Simulator(frag)
        sim.add_testbench(testbench)
        with sim.write_vcd("test.vcd", "test.gtkw", traces=traces):
            sim.run()

    def test_signal(self):
        a = Signal()
        self.assertDef(a, [a])

    def test_list(self):
        a = Signal()
        self.assertDef([a], [a])

    def test_tuple(self):
        a = Signal()
        self.assertDef((a,), [a])

    def test_dict(self):
        a = Signal()
        self.assertDef({"a": a}, [a])

    def test_struct_view(self):
        a = Signal(data.StructLayout({"a": 1, "b": 3}))
        self.assertDef(a, [a])

    def test_interface(self):
        sig = wiring.Signature({
            "a": wiring.In(1),
            "b": wiring.Out(3),
            "c": wiring.Out(2).array(4),
            "d": wiring.In(wiring.Signature({"e": wiring.In(5)}))
        })
        a = sig.create()
        self.assertDef(a, [a])


class SimulatorRegressionTestCase(FHDLTestCase):
    def test_bug_325(self):
        dut = Module()
        dut.d.comb += Signal().eq(Cat())
        Simulator(dut).run()

    def test_bug_473(self):
        sim = Simulator(Module())
        async def testbench(ctx):
            self.assertEqual(ctx.get(-(Const(0b11, 2).as_signed())), 1)
        sim.add_testbench(testbench)
        sim.run()

    def test_bug_595(self):
        dut = Module()
        dummy = Signal()
        with dut.FSM(name="name with space"):
            with dut.State(0):
                dut.d.comb += dummy.eq(1)
        sim = Simulator(dut)
        with self.assertRaisesRegex(NameError,
                r"^Signal 'bench\.top\.name with space_state' contains a whitespace character$"):
            with open(os.path.devnull, "w") as f:
                with sim.write_vcd(f):
                    sim.run()

    def test_bug_588(self):
        dut = Module()
        a = Signal(32)
        b = Signal(32)
        z = Signal(32)
        dut.d.comb += z.eq(a << b)
        with self.assertRaisesRegex(OverflowError,
                r"^Value defined at .+?[\\/]test_sim\.py:\d+ is 4294967327 bits wide, "
                r"which is unlikely to simulate in reasonable time$"):
            Simulator(dut)

    def test_bug_566(self):
        dut = Module()
        dut.d.sync += Signal().eq(0)
        sim = Simulator(dut)
        with self.assertWarnsRegex(UserWarning,
                r"^Adding a clock that drives a clock domain object named 'sync', which is "
                r"distinct from an identically named domain in the simulated design$"):
            sim.add_clock(1e-6, domain=ClockDomain("sync"))

    def test_bug_826(self):
        sim = Simulator(Module())
        async def testbench(ctx):
            self.assertEqual(ctx.get(C(0b0000, 4) | ~C(1, 1)), 0b0000)
            self.assertEqual(ctx.get(C(0b1111, 4) & ~C(1, 1)), 0b0000)
            self.assertEqual(ctx.get(C(0b1111, 4) ^ ~C(1, 1)), 0b1111)
        sim.add_testbench(testbench)
        sim.run()

    def test_comb_assign(self):
        c = Signal()
        m = Module()
        m.d.comb += c.eq(1)
        sim = Simulator(m)
        async def testbench(ctx):
            with self.assertRaisesRegex(DriverConflict,
                    r"^Combinationally driven signals cannot be overriden by testbenches$"):
                ctx.set(c, 0)
        sim.add_testbench(testbench)
        sim.run()

    def test_comb_clock_conflict(self):
        c = Signal()
        m = Module()
        m.d.comb += ClockSignal().eq(c)
        sim = Simulator(m)
        with self.assertRaisesRegex(DriverConflict,
                r"^Clock signal is already driven by combinational logic$"):
            sim.add_clock(1e-6)

    def test_initial(self):
        a = Signal(4, init=3)
        m = Module()
        sim = Simulator(m)
        fired = 0

        async def process(ctx):
            nonlocal fired
            async for val_a, in ctx.changed(a):
                self.assertEqual(val_a, 3)
                fired += 1

        sim.add_process(process)
        sim.run()
        self.assertEqual(fired, 1)

    def test_sample(self):
        m = Module()
        m.domains.sync = cd_sync = ClockDomain()
        a = Signal(4)
        b = Signal(4)
        sim = Simulator(m)

        async def bench_a(ctx):
            _, _, av, bv = await ctx.tick().sample(a, b)
            ctx.set(a, 5)
            self.assertEqual(av, 1)
            self.assertEqual(bv, 2)

        async def bench_b(ctx):
            _, _, av, bv = await ctx.tick().sample(a, b)
            ctx.set(b, 6)
            self.assertEqual(av, 1)
            self.assertEqual(bv, 2)

        async def bench_c(ctx):
            ctx.set(a, 1)
            ctx.set(b, 2)
            ctx.set(cd_sync.clk, 1)
            ctx.set(a, 3)
            ctx.set(b, 4)

        sim.add_testbench(bench_a)
        sim.add_testbench(bench_b)
        sim.add_testbench(bench_c)
        sim.run()

    def test_latch(self):
        q = Signal(4)
        d = Signal(4)
        g = Signal()

        async def latch(ctx):
            async for dv, gv in ctx.changed(d, g):
                if gv:
                    ctx.set(q, dv)

        async def testbench(ctx):
            ctx.set(d, 1)
            self.assertEqual(ctx.get(q), 0)
            ctx.set(g, 1)
            self.assertEqual(ctx.get(q), 1)
            ctx.set(d, 2)
            self.assertEqual(ctx.get(q), 2)
            ctx.set(g, 0)
            self.assertEqual(ctx.get(q), 2)
            ctx.set(d, 3)
            self.assertEqual(ctx.get(q), 2)

        sim = Simulator(Module())
        sim.add_process(latch)
        sim.add_testbench(testbench)
        sim.run()

    def test_edge(self):
        a = Signal(4)
        b = Signal(4)

        log = []

        async def monitor(ctx):
            async for res in ctx.posedge(a[0]).negedge(a[1]).sample(b):
                log.append(res)

        async def testbench(ctx):
            ctx.set(b, 8)
            ctx.set(a, 0)
            ctx.set(b, 9)
            ctx.set(a, 1)
            ctx.set(b, 10)
            ctx.set(a, 2)
            ctx.set(b, 11)
            ctx.set(a, 3)
            ctx.set(b, 12)
            ctx.set(a, 4)
            ctx.set(b, 13)
            ctx.set(a, 6)
            ctx.set(b, 14)
            ctx.set(a, 5)

        sim = Simulator(Module())
        sim.add_process(monitor)
        sim.add_testbench(testbench)
        sim.run()

        self.assertEqual(log, [
            (True, False, 9),
            (True, False, 11),
            (False, True, 12),
            (True, True, 14)
        ])

    def test_delay(self):
        log = []

        async def monitor(ctx):
            async for res in ctx.delay(1).delay(2).delay(1):
                log.append(res)

        async def testbench(ctx):
            await ctx.delay(4)

        sim = Simulator(Module())
        sim.add_process(monitor)
        sim.add_testbench(testbench)
        sim.run()

        self.assertEqual(log, [
            (True, False, True),
            (True, False, True),
            (True, False, True),
            (True, False, True),
        ])


    def test_timeout(self):
        a = Signal()

        log = []

        async def monitor(ctx):
            async for res in ctx.posedge(a).delay(1.5):
                log.append(res)

        async def testbench(ctx):
            await ctx.delay(0.5)
            ctx.set(a, 1)
            await ctx.delay(0.5)
            ctx.set(a, 0)
            await ctx.delay(0.5)
            ctx.set(a, 1)
            await ctx.delay(1)
            ctx.set(a, 0)
            await ctx.delay(1)
            ctx.set(a, 1)

        sim = Simulator(Module())
        sim.add_process(monitor)
        sim.add_testbench(testbench)
        sim.run()

        self.assertEqual(log, [
            (True, False),
            (True, False),
            (False, True),
            (True, False),
        ])

    def test_struct(self):
        class MyStruct(data.Struct):
            x: unsigned(4)
            y: signed(4)

        a = Signal(MyStruct)
        b = Signal(MyStruct)

        m = Module()
        m.domains.sync = ClockDomain()

        log = []

        async def adder(ctx):
            async for av, in ctx.changed(a):
                ctx.set(b, {
                    "x": av.y,
                    "y": av.x
                })

        async def monitor(ctx):
            async for _, _, bv in ctx.tick().sample(b):
                log.append(bv)

        async def testbench(ctx):
            ctx.set(a.x, 1)
            ctx.set(a.y, 2)
            self.assertEqual(ctx.get(b.x), 2)
            self.assertEqual(ctx.get(b.y), 1)
            self.assertEqual(ctx.get(b), MyStruct.const({"x": 2, "y": 1}))
            await ctx.tick()
            ctx.set(a, MyStruct.const({"x": 3, "y": 4}))
            await ctx.tick()

        sim = Simulator(m)
        sim.add_process(adder)
        sim.add_process(monitor)
        sim.add_testbench(testbench)
        sim.add_clock(1e-6)
        sim.run()

        self.assertEqual(log, [
            MyStruct.const({"x": 2, "y": 1}),
            MyStruct.const({"x": 4, "y": 3}),
        ])

    def test_valuecastable(self):
        a = Signal(4)
        b = Signal(4)
        t = Signal()
        idx = Signal()
        arr = Array([a, b])

        async def process(ctx):
            async for _ in ctx.posedge(t):
                ctx.set(arr[idx], 1)

        async def testbench(ctx):
            self.assertEqual(ctx.get(arr[idx]), 0)
            ctx.set(t, 1)
            self.assertEqual(ctx.get(a), 1)
            ctx.set(idx, 1)
            ctx.set(arr[idx], 2)
            self.assertEqual(ctx.get(b), 2)

        sim = Simulator(Module())
        sim.add_process(process)
        sim.add_testbench(testbench)
        sim.run()

    def test_tick_repeat_until(self):
        ctr = Signal(4)
        m = Module()
        m.domains.sync = cd_sync = ClockDomain()
        m.d.sync += ctr.eq(ctr + 1)

        async def testbench(ctx):
            _, _, val, = await ctx.tick(cd_sync).sample(ctr)
            self.assertEqual(val, 0)
            self.assertEqual(ctx.get(ctr), 1)
            val, = await ctx.tick(cd_sync).sample(ctr).until(ctr == 4)
            self.assertEqual(val, 4)
            self.assertEqual(ctx.get(ctr), 5)
            val, = await ctx.tick(cd_sync).sample(ctr).repeat(3)
            self.assertEqual(val, 7)
            self.assertEqual(ctx.get(ctr), 8)

        sim = Simulator(m)
        sim.add_testbench(testbench)
        sim.add_clock(1e-6)
        sim.run()

    def test_critical(self):
        ctr = Signal(4)
        m = Module()
        m.domains.sync = cd_sync = ClockDomain()
        m.d.sync += ctr.eq(ctr + 1)

        last_ctr = 0

        async def testbench(ctx):
            await ctx.tick().repeat(7)

        async def bgbench(ctx):
            nonlocal last_ctr
            while True:
                await ctx.tick()
                with ctx.critical():
                    await ctx.tick().repeat(2)
                    last_ctr = ctx.get(ctr)

        sim = Simulator(m)
        sim.add_testbench(testbench)
        sim.add_testbench(bgbench, background=True)
        sim.add_clock(1e-6)
        sim.run()

        self.assertEqual(last_ctr, 9)

    def test_async_reset(self):
        ctr = Signal(4)
        m = Module()
        m.domains.sync = cd_sync = ClockDomain(async_reset=True)
        m.d.sync += ctr.eq(ctr + 1)

        log = []

        async def monitor(ctx):
            async for res in ctx.tick().sample(ctr):
                log.append(res)

        async def testbench(ctx):
            await ctx.posedge(cd_sync.clk)
            await ctx.posedge(cd_sync.clk)
            await ctx.negedge(cd_sync.clk)
            ctx.set(cd_sync.rst, True)
            await ctx.negedge(cd_sync.clk)
            ctx.set(cd_sync.rst, False)
            await ctx.posedge(cd_sync.clk)
            await ctx.posedge(cd_sync.clk)

        async def repeat_bench(ctx):
            with self.assertRaises(DomainReset):
                await ctx.tick().repeat(4)

        async def until_bench(ctx):
            with self.assertRaises(DomainReset):
                await ctx.tick().until(ctr == 3)

        sim = Simulator(m)
        sim.add_process(monitor)
        sim.add_testbench(testbench)
        sim.add_testbench(repeat_bench)
        sim.add_testbench(until_bench)
        sim.add_clock(1e-6)
        sim.run()

        self.assertEqual(log, [
            (True, False, 0),
            (True, False, 1),
            (False, True, 2),
            (True, True, 0),
            (True, False, 0),
            (True, False, 1),
        ])

    def test_sync_reset(self):
        ctr = Signal(4)
        m = Module()
        m.domains.sync = cd_sync = ClockDomain()
        m.d.sync += ctr.eq(ctr + 1)

        log = []

        async def monitor(ctx):
            async for res in ctx.tick().sample(ctr):
                log.append(res)

        async def testbench(ctx):
            await ctx.posedge(cd_sync.clk)
            await ctx.posedge(cd_sync.clk)
            await ctx.negedge(cd_sync.clk)
            ctx.set(cd_sync.rst, True)
            await ctx.negedge(cd_sync.clk)
            ctx.set(cd_sync.rst, False)
            await ctx.posedge(cd_sync.clk)
            await ctx.posedge(cd_sync.clk)

        sim = Simulator(m)
        sim.add_process(monitor)
        sim.add_testbench(testbench)
        sim.add_clock(1e-6)
        sim.run()

        self.assertEqual(log, [
            (True, False, 0),
            (True, False, 1),
            (True, True, 2),
            (True, False, 0),
            (True, False, 1),
        ])

    def test_broken_multiedge(self):
        a = Signal()

        broken_trigger_hit = False

        async def testbench(ctx):
            await ctx.delay(1)
            ctx.set(a, 1)
            ctx.set(a, 0)
            ctx.set(a, 1)
            ctx.set(a, 0)
            await ctx.delay(1)

        async def monitor(ctx):
            nonlocal broken_trigger_hit
            try:
                async for _ in ctx.edge(a, 1):
                    pass
            except BrokenTrigger:
                broken_trigger_hit = True

        sim = Simulator(Module())
        sim.add_testbench(testbench)
        sim.add_testbench(monitor, background=True)
        sim.run()

        self.assertTrue(broken_trigger_hit)

    def test_broken_other_trigger(self):
        m = Module()
        m.domains.sync = ClockDomain()

        async def testbench(ctx):
            with self.assertRaises(BrokenTrigger):
                async for _ in ctx.tick():
                    await ctx.delay(2)

        sim = Simulator(m)
        sim.add_testbench(testbench)
        sim.add_clock(1)
        sim.run()

    def test_abandon_delay(self):
        ctr = Signal(4)
        m = Module()
        m.domains.sync = ClockDomain()
        m.d.sync += ctr.eq(ctr + 1)

        async def testbench(ctx):
            async for _ in ctx.delay(1).delay(1):
                break

            await ctx.tick()
            await ctx.tick()
            self.assertEqual(ctx.get(ctr), 2)

        sim = Simulator(m)
        sim.add_testbench(testbench)
        sim.add_clock(4)
        sim.run()

    def test_abandon_changed(self):
        ctr = Signal(4)
        a = Signal()
        m = Module()
        m.domains.sync = ClockDomain()
        m.d.sync += ctr.eq(ctr + 1)

        async def testbench(ctx):
            async for _ in ctx.changed(a):
                break

            await ctx.tick()
            await ctx.tick()
            self.assertEqual(ctx.get(ctr), 2)

        async def change(ctx):
            await ctx.delay(1)
            ctx.set(a, 1)
            await ctx.delay(1)
            ctx.set(a, 0)
            await ctx.delay(1)
            ctx.set(a, 1)

        sim = Simulator(m)
        sim.add_testbench(testbench)
        sim.add_testbench(change)
        sim.add_clock(4)
        sim.run()

    def test_trigger_wrong(self):
        a = Signal(4)
        m = Module()
        m.domains.sync = cd_sync = ClockDomain()

        reached_tb = False
        reached_proc = False

        async def process(ctx):
            nonlocal reached_proc
            with self.assertRaisesRegex(TypeError,
                    r"^`\.get\(\)` cannot be used to sample values in simulator processes; "
                    r"use `\.sample\(\)` on a trigger object instead$"):
                ctx.get(a)
            reached_proc = True

        async def testbench(ctx):
            nonlocal reached_tb
            with self.assertRaisesRegex(TypeError,
                    r"^Change trigger can only be used with a signal, not \(~ \(sig a\)\)$"):
                await ctx.changed(~a)
            with self.assertRaisesRegex(TypeError,
                    r"^Edge trigger can only be used with a single-bit signal or "
                    r"a single-bit slice of a signal, not \(sig a\)$"):
                await ctx.posedge(a)
            with self.assertRaisesRegex(ValueError,
                    r"^Edge trigger polarity must be 0 or 1, not 2$"):
                await ctx.edge(a[0], 2)
            with self.assertRaisesRegex(TypeError,
                    r"^Condition must be a value-like object, not 'meow'$"):
                await ctx.tick().until("meow")
            with self.assertRaisesRegex(ValueError,
                    r"^Repeat count must be a positive integer, not 0$"):
                await ctx.tick().repeat(0)
            with self.assertRaisesRegex(ValueError,
                    r"^Combinational domain does not have a clock$"):
                await ctx.tick("comb")
            with self.assertRaisesRegex(NameError,
                    r"^Clock domain named 'sync2' does not exist$"):
                await ctx.tick("sync2")
            with self.assertRaisesRegex(ValueError,
                    r"^Context cannot be provided if a clock domain is specified directly$"):
                await ctx.tick(cd_sync, context=m)
            with self.assertRaisesRegex(ValueError,
                    r"^Delay cannot be negative$"):
                await ctx.delay(-1)
            s = Signal(data.StructLayout({"a": unsigned(1)}))
            with self.assertRaisesRegex(TypeError,
                    r"^The shape of a condition may only be `signed` or `unsigned`, not StructLayout.*$"):
                await ctx.tick().until(s)
            reached_tb = True

        sim = Simulator(m)
        sim.add_process(process)
        sim.add_testbench(testbench)
        sim.run()

        self.assertTrue(reached_tb)
        self.assertTrue(reached_proc)

    def test_bug_1363(self):
        sim = Simulator(Module())
        with self.assertRaisesRegex(TypeError,
                r"^Cannot add a testbench <.+?> because it is not an async function or "
                r"generator function$"):
            async def testbench():
                yield Delay()
            sim.add_testbench(testbench())

    def test_issue_1368(self):
        sim = Simulator(Module())
        async def testbench(ctx):
            sim.add_clock(1e-6)
        sim.add_testbench(testbench)
        with self.assertRaisesRegex(RuntimeError,
                r"^Cannot add a clock to a running simulation$"):
            sim.run()

        sim = Simulator(Module())
        async def testbench(ctx):
            async def testbench2(ctx):
                pass
            sim.add_testbench(testbench2)
        sim.add_testbench(testbench)
        with self.assertRaisesRegex(RuntimeError,
                r"^Cannot add a testbench to a running simulation$"):
            sim.run()

        sim = Simulator(Module())
        async def process(ctx):
            async def process2(ctx):
                pass
            sim.add_process(process2)
        sim.add_process(process)
        with self.assertRaisesRegex(RuntimeError,
                r"^Cannot add a process to a running simulation$"):
            sim.run()

        async def process_empty(ctx):
            pass
        sim = Simulator(Module())
        sim.run()
        sim.reset()
        sim.add_process(process_empty) # should succeed
        sim.run() # suppress 'coroutine was never awaited' warning
