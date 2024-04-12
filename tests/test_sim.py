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
from amaranth.hdl._dsl import  *
from amaranth.hdl._ir import *
from amaranth.sim import *
from amaranth.sim._pyeval import eval_format
from amaranth.lib.memory import Memory
from amaranth.lib import enum, data

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
        def process():
            for isig, input in zip(isigs, inputs):
                yield isig.eq(input)
            self.assertEqual((yield osig), output.value)
        sim.add_testbench(process)
        with sim.write_vcd("test.vcd", "test.gtkw", traces=[*isigs, osig]):
            sim.run()

        frag = Fragment()
        sim = Simulator(frag)
        def process():
            for isig, input in zip(isigs, inputs):
                yield isig.eq(input)
            yield Delay(0)
            if isinstance(stmt, Assign):
                yield stmt
            else:
                yield from stmt
            yield Delay(0)
            self.assertEqual((yield osig), output.value)
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
    def assertSimulation(self, module, *, deadline=None):
        sim = Simulator(module)
        yield sim
        with sim.write_vcd("test.vcd", "test.gtkw"):
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
        def process():
            nonlocal times
            yield Tick()
            self.assertEqual((yield self.count), 4)
            yield Tick()
            self.assertEqual((yield self.count), 5)
            yield Tick()
            self.assertEqual((yield self.count), 6)
            yield Tick()
            times += 1
        sim.add_process(process)
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
            sim.add_process(process)

    def test_alu_bench(self):
        self.setUp_alu()
        with self.assertSimulation(self.m) as sim:
            sim.add_clock(1e-6)
            def process():
                yield self.a.eq(5)
                yield self.b.eq(1)
                self.assertEqual((yield self.x), 4)
                yield Tick()
                self.assertEqual((yield self.o), 6)
                yield self.s.eq(1)
                yield Tick()
                self.assertEqual((yield self.o), 4)
                yield self.s.eq(2)
                yield Tick()
                self.assertEqual((yield self.o), 0)
            sim.add_testbench(process)

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

            def proc():
                clocks = [
                    self.phase0.clk,
                    self.phase90.clk,
                    self.phase180.clk,
                    self.phase270.clk
                ]
                for i in range(16):
                    yield Tick("check")
                    for j, c in enumerate(clocks):
                        self.assertEqual((yield c), self.expected[j][i])

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

            def sys_process():
                yield Passive()
                yield Tick("sys")
                yield Tick("sys")
                self.fail()
            def pix_process():
                yield Tick("pix")
                yield Tick("pix")
                yield Tick("pix")
            sim.add_testbench(sys_process)
            sim.add_testbench(pix_process)

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
                self.assertEqual((yield self.i[:4]), 0b1111)
                self.assertEqual((yield self.i), 0b10101111)
            sim.add_testbench(process)

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
            sim.add_testbench(process)

    def test_run_until_fail(self):
        m = Module()
        s = Signal()
        m.d.sync += s.eq(0)
        with self.assertRaises(AssertionError):
            with self.assertSimulation(m, deadline=100e-6) as sim:
                    sim.add_clock(1e-6)
                    def process():
                        for _ in range(99):
                            yield Delay(1e-6)
                        self.fail()
                    sim.add_testbench(process)

    def test_add_process_wrong(self):
        with self.assertSimulation(Module()) as sim:
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot add a process 1 because it is not a generator function$"):
                sim.add_process(1)

    def test_add_process_wrong_generator(self):
        with self.assertSimulation(Module()) as sim:
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot add a process <.+?> because it is not a generator function$"):
                def process():
                    yield Delay()
                sim.add_process(process())

    def test_add_clock_wrong_twice(self):
        m = Module()
        s = Signal()
        m.d.sync += s.eq(0)
        with self.assertSimulation(m) as sim:
            sim.add_clock(1)
            with self.assertRaisesRegex(ValueError,
                    r"^Domain 'sync' already has a clock driving it$"):
                sim.add_clock(1)

    def test_add_clock_wrong_missing(self):
        m = Module()
        with self.assertSimulation(m) as sim:
            with self.assertRaisesRegex(ValueError,
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
            def process():
                yield self.rdport.addr.eq(1)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0x55)
                yield self.rdport.addr.eq(2)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0x00)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_write(self):
        self.setUp_memory()
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.wrport.addr.eq(4)
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(1)
                yield Tick()
                yield self.wrport.en.eq(0)
                yield self.rdport.addr.eq(4)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_write_granularity(self):
        self.setUp_memory(wr_granularity=4)
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.wrport.data.eq(0x50)
                yield self.wrport.en.eq(0b00)
                yield Tick()
                yield self.wrport.en.eq(0)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield self.wrport.en.eq(0b10)
                yield Tick()
                yield self.wrport.en.eq(0)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0x5a)
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(0b01)
                yield Tick()
                yield self.wrport.en.eq(0)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0x53)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_read_before_write(self):
        self.setUp_memory(rd_transparent=False)
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(1)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_write_through(self):
        self.setUp_memory(rd_transparent=True)
        with self.assertSimulation(self.m) as sim:
            def process():
                yield Tick()
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(1)
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0x33)
                yield Tick()
                yield self.rdport.addr.eq(1)
                self.assertEqual((yield self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_async_read_write(self):
        self.setUp_memory(rd_synchronous=False)
        with self.assertSimulation(self.m) as sim:
            def process():
                yield self.rdport.addr.eq(0)
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield self.rdport.addr.eq(1)
                self.assertEqual((yield self.rdport.data), 0x55)
                yield self.rdport.addr.eq(0)
                yield self.wrport.addr.eq(0)
                yield self.wrport.data.eq(0x33)
                yield self.wrport.en.eq(1)
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield Tick("sync")
                self.assertEqual((yield self.rdport.data), 0x33)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_read_only(self):
        self.m = Module()
        self.m.submodules.memory = self.memory = Memory(shape=8, depth=4, init=[0xaa, 0x55])
        self.rdport = self.memory.read_port()
        with self.assertSimulation(self.m) as sim:
            def process():
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0xaa)
                yield self.rdport.addr.eq(1)
                yield Tick()
                self.assertEqual((yield self.rdport.data), 0x55)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_comb_bench_process(self):
        m = Module()
        a = Signal(init=1)
        b = Signal()
        m.d.comb += b.eq(a)
        with self.assertSimulation(m) as sim:
            def process():
                self.assertEqual((yield a), 1)
                self.assertEqual((yield b), 1)
                yield a.eq(0)
                self.assertEqual((yield a), 0)
                self.assertEqual((yield b), 0)
            sim.add_testbench(process)

    def test_sync_bench_process(self):
        m = Module()
        a = Signal(init=1)
        b = Signal()
        m.d.sync += b.eq(a)
        t = Signal()
        m.d.sync += t.eq(~t)
        with self.assertSimulation(m) as sim:
            def process():
                self.assertEqual((yield a), 1)
                self.assertEqual((yield b), 0)
                self.assertEqual((yield t), 0)
                yield Tick()
                self.assertEqual((yield a), 1)
                self.assertEqual((yield b), 1)
                self.assertEqual((yield t), 1)
                yield Tick()
                self.assertEqual((yield a), 1)
                self.assertEqual((yield b), 1)
                self.assertEqual((yield t), 0)
                yield a.eq(0)
                self.assertEqual((yield a), 0)
                self.assertEqual((yield b), 1)
                yield Tick()
                self.assertEqual((yield a), 0)
                self.assertEqual((yield b), 0)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_transparency_simple(self):
        m = Module()
        init = [0x11, 0x22, 0x33, 0x44]
        m.submodules.memory = memory = Memory(shape=8, depth=4, init=init)
        wrport = memory.write_port(granularity=8)
        rdport = memory.read_port(transparent_for=[wrport])
        with self.assertSimulation(m) as sim:
            def process():
                yield rdport.addr.eq(0)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x11)
                yield rdport.addr.eq(1)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x22)
                yield wrport.addr.eq(0)
                yield wrport.data.eq(0x44444444)
                yield wrport.en.eq(1)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x22)
                yield wrport.addr.eq(1)
                yield wrport.data.eq(0x55)
                yield wrport.en.eq(1)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x55)
                yield wrport.addr.eq(1)
                yield wrport.data.eq(0x66)
                yield wrport.en.eq(1)
                yield rdport.en.eq(0)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x55)
                yield wrport.addr.eq(2)
                yield wrport.data.eq(0x77)
                yield wrport.en.eq(1)
                yield rdport.en.eq(1)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x66)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_transparency_multibit(self):
        m = Module()
        init = [0x11111111, 0x22222222, 0x33333333, 0x44444444]
        m.submodules.memory = memory = Memory(shape=32, depth=4, init=init)
        wrport = memory.write_port(granularity=8)
        rdport = memory.read_port(transparent_for=[wrport])
        with self.assertSimulation(m) as sim:
            def process():
                yield rdport.addr.eq(0)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x11111111)
                yield rdport.addr.eq(1)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x22222222)
                yield wrport.addr.eq(0)
                yield wrport.data.eq(0x44444444)
                yield wrport.en.eq(1)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x22222222)
                yield wrport.addr.eq(1)
                yield wrport.data.eq(0x55555555)
                yield wrport.en.eq(1)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x22222255)
                yield wrport.addr.eq(1)
                yield wrport.data.eq(0x66666666)
                yield wrport.en.eq(2)
                yield rdport.en.eq(0)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x22222255)
                yield wrport.addr.eq(1)
                yield wrport.data.eq(0x77777777)
                yield wrport.en.eq(4)
                yield rdport.en.eq(1)
                yield Tick()
                self.assertEqual((yield rdport.data), 0x22776655)
            sim.add_clock(1e-6)
            sim.add_testbench(process)

    def test_memory_access(self):
        self.setUp_memory()
        with self.assertSimulation(self.m) as sim:
            def process():
                self.assertEqual((yield self.memory.data[1]), 0x55)
                self.assertEqual((yield self.memory.data[1]), 0x55)
                self.assertEqual((yield self.memory.data[2]), 0x00)
                yield self.memory.data[1].eq(Const(0x33))
                self.assertEqual((yield self.memory.data[1]), 0x33)
                yield self.memory.data[1][2:5].eq(Const(0x7))
                self.assertEqual((yield self.memory.data[1]), 0x3f)
                yield self.wrport.addr.eq(3)
                yield self.wrport.data.eq(0x22)
                yield self.wrport.en.eq(1)
                self.assertEqual((yield self.memory.data[3]), 0)
                yield Tick()
                self.assertEqual((yield self.memory.data[3]), 0x22)

            sim.add_clock(1e-6)
            sim.add_testbench(process)

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
            def process():
                self.assertEqual((yield o), 1)
            sim.add_testbench(process)

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
                def process():
                    yield Delay(1e-5)
                sim.add_testbench(process)
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
                def process():
                    yield Delay(1e-5)
                sim.add_testbench(process)
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
                def process():
                    yield Tick()
                    yield Tick()
                    yield Tick()
                    yield Tick()
                sim.add_testbench(process)
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
                def process():
                    yield Delay(1e-5)
                sim.add_testbench(process)

    def test_assume(self):
        m = Module()
        ctr = Signal(16)
        m.d.sync += ctr.eq(ctr + 1)
        m.d.comb += Assume(ctr < 4)
        with self.assertRaisesRegex(AssertionError,
                r"^Assumption violated$"):
            with self.assertSimulation(m) as sim:
                sim.add_clock(1e-6, domain="sync")
                def process():
                    yield Delay(1e-5)
                sim.add_testbench(process)

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
                def process():
                    yield Delay(1e-5)
                sim.add_testbench(process)
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
        sim.add_testbench(testbench_1)
        sim.add_testbench(testbench_2)
        with sim.write_vcd("test.vcd", fs_per_delta=1):
            sim.run()

    def test_process_name_collision(self):
        def testbench():
            yield Passive()
        sim = Simulator(Module())
        sim.add_testbench(testbench)
        sim.add_testbench(testbench)
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

        def testbench():
            state = sim._engine._state
            yield sig.eq(123)
            self.assertEqual(eval_format(state, sig._format), "123")
            self.assertEqual(eval_format(state, Format("{:#04x}", sig)), "0x7b")
            self.assertEqual(eval_format(state, Format("sig={}", sig)), "sig=123")

            self.assertEqual(eval_format(state, sig2.as_value()._format), "A")
            yield sig2.eq(1)
            self.assertEqual(eval_format(state, sig2.as_value()._format), "B")
            yield sig2.eq(3)
            self.assertEqual(eval_format(state, sig2.as_value()._format), "[unknown]")

            yield sig3.eq(0xc)
            self.assertEqual(eval_format(state, sig3.as_value()._format), "{a=-4, b=1}")

            yield sig4.eq(0x1e)
            self.assertEqual(eval_format(state, sig4.as_value()._format), "[2, 3, 1, 0]")

            self.assertEqual(eval_format(state, Format("{:s}", sig5)), "ABCD")
            self.assertEqual(eval_format(state, Format("{:<5s}", sig5)), "ABCD ")

        sim = Simulator(Module())
        sim.add_testbench(testbench)
        with sim.write_vcd("test.vcd", fs_per_delta=1):
            sim.run()

class SimulatorRegressionTestCase(FHDLTestCase):
    def test_bug_325(self):
        dut = Module()
        dut.d.comb += Signal().eq(Cat())
        Simulator(dut).run()

    def test_bug_473(self):
        sim = Simulator(Module())
        def process():
            self.assertEqual((yield -(Const(0b11, 2).as_signed())), 1)
        sim.add_testbench(process)
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
                r"^Adding a clock process that drives a clock domain object named 'sync', "
                r"which is distinct from an identically named domain in the simulated design$"):
            sim.add_clock(1e-6, domain=ClockDomain("sync"))

    def test_bug_826(self):
        sim = Simulator(Module())
        def process():
            self.assertEqual((yield C(0b0000, 4) | ~C(1, 1)), 0b0000)
            self.assertEqual((yield C(0b1111, 4) & ~C(1, 1)), 0b0000)
            self.assertEqual((yield C(0b1111, 4) ^ ~C(1, 1)), 0b1111)
        sim.add_testbench(process)
        sim.run()
