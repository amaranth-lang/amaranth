import unittest

from nmigen.fhdl.ast import *


class ValueTestCase(unittest.TestCase):
    def test_wrap(self):
        self.assertIsInstance(Value.wrap(0), Const)
        self.assertIsInstance(Value.wrap(True), Const)
        c = Const(0)
        self.assertIs(Value.wrap(c), c)
        with self.assertRaises(TypeError):
            Value.wrap("str")

    def test_bool(self):
        with self.assertRaises(TypeError):
            if Const(0):
                pass

    def test_len(self):
        self.assertEqual(len(Const(10)), 4)

    def test_getitem_int(self):
        s1 = Const(10)[0]
        self.assertIsInstance(s1, Slice)
        self.assertEqual(s1.start, 0)
        self.assertEqual(s1.end, 1)
        s2 = Const(10)[-1]
        self.assertIsInstance(s2, Slice)
        self.assertEqual(s2.start, 3)
        self.assertEqual(s2.end, 4)
        with self.assertRaises(IndexError):
            Const(10)[5]

    def test_getitem_slice(self):
        s1 = Const(10)[1:3]
        self.assertIsInstance(s1, Slice)
        self.assertEqual(s1.start, 1)
        self.assertEqual(s1.end, 3)
        s2 = Const(10)[1:-2]
        self.assertIsInstance(s2, Slice)
        self.assertEqual(s2.start, 1)
        self.assertEqual(s2.end, 2)
        s3 = Const(31)[::2]
        self.assertIsInstance(s3, Cat)
        self.assertIsInstance(s3.operands[0], Slice)
        self.assertEqual(s3.operands[0].start, 0)
        self.assertEqual(s3.operands[0].end, 1)
        self.assertIsInstance(s3.operands[1], Slice)
        self.assertEqual(s3.operands[1].start, 2)
        self.assertEqual(s3.operands[1].end, 3)
        self.assertIsInstance(s3.operands[2], Slice)
        self.assertEqual(s3.operands[2].start, 4)
        self.assertEqual(s3.operands[2].end, 5)

    def test_getitem_wrong(self):
        with self.assertRaises(TypeError):
            Const(31)["str"]


class ConstTestCase(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(Const(0).shape(),   (0, False))
        self.assertEqual(Const(1).shape(),   (1, False))
        self.assertEqual(Const(10).shape(),  (4, False))
        self.assertEqual(Const(-10).shape(), (4, True))

        self.assertEqual(Const(1, 4).shape(),         (4, False))
        self.assertEqual(Const(1, (4, True)).shape(), (4, True))

        with self.assertRaises(TypeError):
            Const(1, -1)

    def test_value(self):
        self.assertEqual(Const(10).value, 10)

    def test_repr(self):
        self.assertEqual(repr(Const(10)),  "(const 4'd10)")
        self.assertEqual(repr(Const(-10)), "(const 4'sd-10)")

    def test_hash(self):
        with self.assertRaises(TypeError):
            hash(Const(0))


class OperatorTestCase(unittest.TestCase):
    def test_invert(self):
        v = ~Const(0, 4)
        self.assertEqual(repr(v), "(~ (const 4'd0))")
        self.assertEqual(v.shape(), (4, False))

    def test_neg(self):
        v1 = -Const(0, (4, False))
        self.assertEqual(repr(v1), "(- (const 4'd0))")
        self.assertEqual(v1.shape(), (5, True))
        v2 = -Const(0, (4, True))
        self.assertEqual(repr(v2), "(- (const 4'sd0))")
        self.assertEqual(v2.shape(), (4, True))

    def test_add(self):
        v1 = Const(0, (4, False)) + Const(0, (6, False))
        self.assertEqual(repr(v1), "(+ (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (7, False))
        v2 = Const(0, (4, True)) + Const(0, (6, True))
        self.assertEqual(v2.shape(), (7, True))
        v3 = Const(0, (4, True)) + Const(0, (4, False))
        self.assertEqual(v3.shape(), (6, True))
        v4 = Const(0, (4, False)) + Const(0, (4, True))
        self.assertEqual(v4.shape(), (6, True))
        v5 = 10 + Const(0, 4)
        self.assertEqual(v5.shape(), (5, False))

    def test_sub(self):
        v1 = Const(0, (4, False)) - Const(0, (6, False))
        self.assertEqual(repr(v1), "(- (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (7, False))
        v2 = Const(0, (4, True)) - Const(0, (6, True))
        self.assertEqual(v2.shape(), (7, True))
        v3 = Const(0, (4, True)) - Const(0, (4, False))
        self.assertEqual(v3.shape(), (6, True))
        v4 = Const(0, (4, False)) - Const(0, (4, True))
        self.assertEqual(v4.shape(), (6, True))
        v5 = 10 - Const(0, 4)
        self.assertEqual(v5.shape(), (5, False))

    def test_mul(self):
        v1 = Const(0, (4, False)) * Const(0, (6, False))
        self.assertEqual(repr(v1), "(* (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (10, False))
        v2 = Const(0, (4, True)) * Const(0, (6, True))
        self.assertEqual(v2.shape(), (9, True))
        v3 = Const(0, (4, True)) * Const(0, (4, False))
        self.assertEqual(v3.shape(), (8, True))
        v5 = 10 * Const(0, 4)
        self.assertEqual(v5.shape(), (8, False))

    def test_and(self):
        v1 = Const(0, (4, False)) & Const(0, (6, False))
        self.assertEqual(repr(v1), "(& (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (6, False))
        v2 = Const(0, (4, True)) & Const(0, (6, True))
        self.assertEqual(v2.shape(), (6, True))
        v3 = Const(0, (4, True)) & Const(0, (4, False))
        self.assertEqual(v3.shape(), (5, True))
        v4 = Const(0, (4, False)) & Const(0, (4, True))
        self.assertEqual(v4.shape(), (5, True))
        v5 = 10 & Const(0, 4)
        self.assertEqual(v5.shape(), (4, False))

    def test_or(self):
        v1 = Const(0, (4, False)) | Const(0, (6, False))
        self.assertEqual(repr(v1), "(| (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (6, False))
        v2 = Const(0, (4, True)) | Const(0, (6, True))
        self.assertEqual(v2.shape(), (6, True))
        v3 = Const(0, (4, True)) | Const(0, (4, False))
        self.assertEqual(v3.shape(), (5, True))
        v4 = Const(0, (4, False)) | Const(0, (4, True))
        self.assertEqual(v4.shape(), (5, True))
        v5 = 10 | Const(0, 4)
        self.assertEqual(v5.shape(), (4, False))

    def test_xor(self):
        v1 = Const(0, (4, False)) ^ Const(0, (6, False))
        self.assertEqual(repr(v1), "(^ (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (6, False))
        v2 = Const(0, (4, True)) ^ Const(0, (6, True))
        self.assertEqual(v2.shape(), (6, True))
        v3 = Const(0, (4, True)) ^ Const(0, (4, False))
        self.assertEqual(v3.shape(), (5, True))
        v4 = Const(0, (4, False)) ^ Const(0, (4, True))
        self.assertEqual(v4.shape(), (5, True))
        v5 = 10 ^ Const(0, 4)
        self.assertEqual(v5.shape(), (4, False))

    def test_lt(self):
        v = Const(0, 4) < Const(0, 6)
        self.assertEqual(repr(v), "(< (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_le(self):
        v = Const(0, 4) <= Const(0, 6)
        self.assertEqual(repr(v), "(<= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_gt(self):
        v = Const(0, 4) > Const(0, 6)
        self.assertEqual(repr(v), "(> (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_ge(self):
        v = Const(0, 4) >= Const(0, 6)
        self.assertEqual(repr(v), "(>= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_eq(self):
        v = Const(0, 4) == Const(0, 6)
        self.assertEqual(repr(v), "(== (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_ne(self):
        v = Const(0, 4) != Const(0, 6)
        self.assertEqual(repr(v), "(!= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_mux(self):
        s  = Const(0)
        v1 = Mux(s, Const(0, (4, False)), Const(0, (6, False)))
        self.assertEqual(repr(v1), "(m (const 0'd0) (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), (6, False))
        v2 = Mux(s, Const(0, (4, True)), Const(0, (6, True)))
        self.assertEqual(v2.shape(), (6, True))
        v3 = Mux(s, Const(0, (4, True)), Const(0, (4, False)))
        self.assertEqual(v3.shape(), (5, True))
        v4 = Mux(s, Const(0, (4, False)), Const(0, (4, True)))
        self.assertEqual(v4.shape(), (5, True))

    def test_bool(self):
        v = Const(0).bool()
        self.assertEqual(repr(v), "(b (const 0'd0))")
        self.assertEqual(v.shape(), (1, False))

    def test_hash(self):
        with self.assertRaises(TypeError):
            hash(Const(0) + Const(0))


class SliceTestCase(unittest.TestCase):
    def test_shape(self):
        s1 = Const(10)[2]
        self.assertEqual(s1.shape(), (1, False))
        s2 = Const(-10)[0:2]
        self.assertEqual(s2.shape(), (2, False))

    def test_repr(self):
        s1 = Const(10)[2]
        self.assertEqual(repr(s1), "(slice (const 4'd10) 2:3)")


class CatTestCase(unittest.TestCase):
    def test_shape(self):
        c1 = Cat(Const(10))
        self.assertEqual(c1.shape(), (4, False))
        c2 = Cat(Const(10), Const(1))
        self.assertEqual(c2.shape(), (5, False))
        c3 = Cat(Const(10), Const(1), Const(0))
        self.assertEqual(c3.shape(), (5, False))

    def test_repr(self):
        c1 = Cat(Const(10), Const(1))
        self.assertEqual(repr(c1), "(cat (const 4'd10) (const 1'd1))")


class ReplTestCase(unittest.TestCase):
    def test_shape(self):
        r1 = Repl(Const(10), 3)
        self.assertEqual(r1.shape(), (12, False))

    def test_count_wrong(self):
        with self.assertRaises(TypeError):
            Repl(Const(10), -1)
        with self.assertRaises(TypeError):
            Repl(Const(10), "str")

    def test_repr(self):
        r1 = Repl(Const(10), 3)
        self.assertEqual(repr(r1), "(repl (const 4'd10) 3)")


class SignalTestCase(unittest.TestCase):
    def test_shape(self):
        s1 = Signal()
        self.assertEqual(s1.shape(), (1, False))
        s2 = Signal(2)
        self.assertEqual(s2.shape(), (2, False))
        s3 = Signal((2, False))
        self.assertEqual(s3.shape(), (2, False))
        s4 = Signal((2, True))
        self.assertEqual(s4.shape(), (2, True))
        s5 = Signal(max=16)
        self.assertEqual(s5.shape(), (4, False))
        s6 = Signal(min=4, max=16)
        self.assertEqual(s6.shape(), (4, False))
        s7 = Signal(min=-4, max=16)
        self.assertEqual(s7.shape(), (5, True))
        s8 = Signal(min=-20, max=16)
        self.assertEqual(s8.shape(), (6, True))

        with self.assertRaises(ValueError):
            Signal(min=10, max=4)
        with self.assertRaises(ValueError):
            Signal(2, min=10)
        with self.assertRaises(TypeError):
            Signal(-10)

    def test_name(self):
        s1 = Signal()
        self.assertEqual(s1.name, "s1")
        s2 = Signal(name="sig")
        self.assertEqual(s2.name, "sig")

    def test_reset(self):
        s1 = Signal(4, reset=0b111, reset_less=True)
        self.assertEqual(s1.reset, 0b111)
        self.assertEqual(s1.reset_less, True)

    def test_attrs(self):
        s1 = Signal()
        self.assertEqual(s1.attrs, {})
        s2 = Signal(attrs={"no_retiming": True})
        self.assertEqual(s2.attrs, {"no_retiming": True})

    def test_repr(self):
        s1 = Signal()
        self.assertEqual(repr(s1), "(sig s1)")

    def test_like(self):
        s1 = Signal.like(Signal(4))
        self.assertEqual(s1.shape(), (4, False))
        s2 = Signal.like(Signal(min=-15))
        self.assertEqual(s2.shape(), (5, True))
        s3 = Signal.like(Signal(4, reset=0b111, reset_less=True))
        self.assertEqual(s3.reset, 0b111)
        self.assertEqual(s3.reset_less, True)
        s4 = Signal.like(Signal(attrs={"no_retiming": True}))
        self.assertEqual(s4.attrs, {"no_retiming": True})
        s5 = Signal.like(10)
        self.assertEqual(s5.shape(), (4, False))


class ClockSignalTestCase(unittest.TestCase):
    def test_domain(self):
        s1 = ClockSignal()
        self.assertEqual(s1.domain, "sync")
        s2 = ClockSignal("pix")
        self.assertEqual(s2.domain, "pix")

        with self.assertRaises(TypeError):
            ClockSignal(1)

    def test_repr(self):
        s1 = ClockSignal()
        self.assertEqual(repr(s1), "(clk sync)")


class ResetSignalTestCase(unittest.TestCase):
    def test_domain(self):
        s1 = ResetSignal()
        self.assertEqual(s1.domain, "sync")
        s2 = ResetSignal("pix")
        self.assertEqual(s2.domain, "pix")

        with self.assertRaises(TypeError):
            ResetSignal(1)

    def test_repr(self):
        s1 = ResetSignal()
        self.assertEqual(repr(s1), "(rst sync)")
