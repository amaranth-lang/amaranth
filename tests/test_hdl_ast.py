import warnings
from enum import Enum

from amaranth.hdl.ast import *

from .utils import *


class UnsignedEnum(Enum):
    FOO = 1
    BAR = 2
    BAZ = 3


class SignedEnum(Enum):
    FOO = -1
    BAR =  0
    BAZ = +1


class StringEnum(Enum):
    FOO = "a"
    BAR = "b"


class ShapeTestCase(FHDLTestCase):
    def test_make(self):
        s1 = Shape()
        self.assertEqual(s1.width, 1)
        self.assertEqual(s1.signed, False)
        s2 = Shape(signed=True)
        self.assertEqual(s2.width, 1)
        self.assertEqual(s2.signed, True)
        s3 = Shape(3, True)
        self.assertEqual(s3.width, 3)
        self.assertEqual(s3.signed, True)

    def test_make_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Width must be a non-negative integer, not -1$"):
            Shape(-1)

    def test_compare_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Shapes may be compared with other Shapes and \(int, bool\) tuples, not 'hi'$"):
            Shape(1, True) == 'hi'

    def test_compare_tuple_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Shapes may be compared with other Shapes and \(int, bool\) tuples, not \(2, 3\)$"):
            Shape(1, True) == (2, 3)

    def test_repr(self):
        self.assertEqual(repr(Shape()), "unsigned(1)")
        self.assertEqual(repr(Shape(2, True)), "signed(2)")

    def test_tuple(self):
        width, signed = Shape()
        self.assertEqual(width, 1)
        self.assertEqual(signed, False)

    def test_unsigned(self):
        s1 = unsigned(2)
        self.assertIsInstance(s1, Shape)
        self.assertEqual(s1.width, 2)
        self.assertEqual(s1.signed, False)

    def test_signed(self):
        s1 = signed(2)
        self.assertIsInstance(s1, Shape)
        self.assertEqual(s1.width, 2)
        self.assertEqual(s1.signed, True)

    def test_cast_shape(self):
        s1 = Shape.cast(unsigned(1))
        self.assertEqual(s1.width, 1)
        self.assertEqual(s1.signed, False)
        s2 = Shape.cast(signed(3))
        self.assertEqual(s2.width, 3)
        self.assertEqual(s2.signed, True)

    def test_cast_int(self):
        s1 = Shape.cast(2)
        self.assertEqual(s1.width, 2)
        self.assertEqual(s1.signed, False)

    def test_cast_int_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Width must be a non-negative integer, not -1$"):
            Shape.cast(-1)

    def test_cast_tuple(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore", category=DeprecationWarning)
            s1 = Shape.cast((1, True))
            self.assertEqual(s1.width, 1)
            self.assertEqual(s1.signed, True)

    def test_cast_tuple_wrong(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore", category=DeprecationWarning)
            with self.assertRaisesRegex(TypeError,
                    r"^Width must be a non-negative integer, not -1$"):
                Shape.cast((-1, True))

    def test_cast_range(self):
        s1 = Shape.cast(range(0, 8))
        self.assertEqual(s1.width, 3)
        self.assertEqual(s1.signed, False)
        s2 = Shape.cast(range(0, 9))
        self.assertEqual(s2.width, 4)
        self.assertEqual(s2.signed, False)
        s3 = Shape.cast(range(-7, 8))
        self.assertEqual(s3.width, 4)
        self.assertEqual(s3.signed, True)
        s4 = Shape.cast(range(0, 1))
        self.assertEqual(s4.width, 1)
        self.assertEqual(s4.signed, False)
        s5 = Shape.cast(range(-1, 0))
        self.assertEqual(s5.width, 1)
        self.assertEqual(s5.signed, True)
        s6 = Shape.cast(range(0, 0))
        self.assertEqual(s6.width, 0)
        self.assertEqual(s6.signed, False)
        s7 = Shape.cast(range(-1, -1))
        self.assertEqual(s7.width, 0)
        self.assertEqual(s7.signed, True)

    def test_cast_enum(self):
        s1 = Shape.cast(UnsignedEnum)
        self.assertEqual(s1.width, 2)
        self.assertEqual(s1.signed, False)
        s2 = Shape.cast(SignedEnum)
        self.assertEqual(s2.width, 2)
        self.assertEqual(s2.signed, True)

    def test_cast_enum_bad(self):
        with self.assertRaisesRegex(TypeError,
                r"^Only enumerations with integer values can be used as value shapes$"):
            Shape.cast(StringEnum)

    def test_cast_bad(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object 'foo' cannot be used as value shape$"):
            Shape.cast("foo")


class ValueTestCase(FHDLTestCase):
    def test_cast(self):
        self.assertIsInstance(Value.cast(0), Const)
        self.assertIsInstance(Value.cast(True), Const)
        c = Const(0)
        self.assertIs(Value.cast(c), c)
        with self.assertRaisesRegex(TypeError,
                r"^Object 'str' cannot be converted to an Amaranth value$"):
            Value.cast("str")

    def test_cast_enum(self):
        e1 = Value.cast(UnsignedEnum.FOO)
        self.assertIsInstance(e1, Const)
        self.assertEqual(e1.shape(), unsigned(2))
        e2 = Value.cast(SignedEnum.FOO)
        self.assertIsInstance(e2, Const)
        self.assertEqual(e2.shape(), signed(2))

    def test_cast_enum_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Only enumerations with integer values can be used as value shapes$"):
            Value.cast(StringEnum.FOO)

    def test_bool(self):
        with self.assertRaisesRegex(TypeError,
                r"^Attempted to convert Amaranth value to Python boolean$"):
            if Const(0):
                pass

    def test_len(self):
        self.assertEqual(len(Const(10)), 4)

    def test_getitem_int(self):
        s1 = Const(10)[0]
        self.assertIsInstance(s1, Slice)
        self.assertEqual(s1.start, 0)
        self.assertEqual(s1.stop, 1)
        s2 = Const(10)[-1]
        self.assertIsInstance(s2, Slice)
        self.assertEqual(s2.start, 3)
        self.assertEqual(s2.stop, 4)
        with self.assertRaisesRegex(IndexError,
                r"^Index 5 is out of bounds for a 4-bit value$"):
            Const(10)[5]

    def test_getitem_slice(self):
        s1 = Const(10)[1:3]
        self.assertIsInstance(s1, Slice)
        self.assertEqual(s1.start, 1)
        self.assertEqual(s1.stop, 3)
        s2 = Const(10)[1:-2]
        self.assertIsInstance(s2, Slice)
        self.assertEqual(s2.start, 1)
        self.assertEqual(s2.stop, 2)
        s3 = Const(31)[::2]
        self.assertIsInstance(s3, Cat)
        self.assertIsInstance(s3.parts[0], Slice)
        self.assertEqual(s3.parts[0].start, 0)
        self.assertEqual(s3.parts[0].stop, 1)
        self.assertIsInstance(s3.parts[1], Slice)
        self.assertEqual(s3.parts[1].start, 2)
        self.assertEqual(s3.parts[1].stop, 3)
        self.assertIsInstance(s3.parts[2], Slice)
        self.assertEqual(s3.parts[2].start, 4)
        self.assertEqual(s3.parts[2].stop, 5)

    def test_getitem_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Cannot index value with 'str'$"):
            Const(31)["str"]

    def test_shift_left(self):
        self.assertRepr(Const(256, unsigned(9)).shift_left(0),
                        "(cat (const 0'd0) (const 9'd256))")

        self.assertRepr(Const(256, unsigned(9)).shift_left(1),
                        "(cat (const 1'd0) (const 9'd256))")
        self.assertRepr(Const(256, unsigned(9)).shift_left(5),
                        "(cat (const 5'd0) (const 9'd256))")
        self.assertRepr(Const(256, signed(9)).shift_left(1),
                        "(s (cat (const 1'd0) (const 9'sd-256)))")
        self.assertRepr(Const(256, signed(9)).shift_left(5),
                        "(s (cat (const 5'd0) (const 9'sd-256)))")

        self.assertRepr(Const(256, unsigned(9)).shift_left(-1),
                        "(slice (const 9'd256) 1:9)")
        self.assertRepr(Const(256, unsigned(9)).shift_left(-5),
                        "(slice (const 9'd256) 5:9)")
        self.assertRepr(Const(256, signed(9)).shift_left(-1),
                        "(s (slice (const 9'sd-256) 1:9))")
        self.assertRepr(Const(256, signed(9)).shift_left(-5),
                        "(s (slice (const 9'sd-256) 5:9))")
        self.assertRepr(Const(256, signed(9)).shift_left(-15),
                        "(s (slice (const 9'sd-256) 9:9))")

    def test_shift_left_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Shift amount must be an integer, not 'str'$"):
            Const(31).shift_left("str")

    def test_shift_right(self):
        self.assertRepr(Const(256, unsigned(9)).shift_right(0),
                        "(slice (const 9'd256) 0:9)")

        self.assertRepr(Const(256, unsigned(9)).shift_right(-1),
                        "(cat (const 1'd0) (const 9'd256))")
        self.assertRepr(Const(256, unsigned(9)).shift_right(-5),
                        "(cat (const 5'd0) (const 9'd256))")
        self.assertRepr(Const(256, signed(9)).shift_right(-1),
                        "(s (cat (const 1'd0) (const 9'sd-256)))")
        self.assertRepr(Const(256, signed(9)).shift_right(-5),
                        "(s (cat (const 5'd0) (const 9'sd-256)))")

        self.assertRepr(Const(256, unsigned(9)).shift_right(1),
                        "(slice (const 9'd256) 1:9)")
        self.assertRepr(Const(256, unsigned(9)).shift_right(5),
                        "(slice (const 9'd256) 5:9)")
        self.assertRepr(Const(256, signed(9)).shift_right(1),
                        "(s (slice (const 9'sd-256) 1:9))")
        self.assertRepr(Const(256, signed(9)).shift_right(5),
                        "(s (slice (const 9'sd-256) 5:9))")
        self.assertRepr(Const(256, signed(9)).shift_right(15),
                        "(s (slice (const 9'sd-256) 9:9))")

    def test_shift_right_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Shift amount must be an integer, not 'str'$"):
            Const(31).shift_left("str")

    def test_rotate_left(self):
        self.assertRepr(Const(256).rotate_left(1),
                        "(cat (slice (const 9'd256) 8:9) (slice (const 9'd256) 0:8))")
        self.assertRepr(Const(256).rotate_left(7),
                        "(cat (slice (const 9'd256) 2:9) (slice (const 9'd256) 0:2))")
        self.assertRepr(Const(256).rotate_left(-1),
                        "(cat (slice (const 9'd256) 1:9) (slice (const 9'd256) 0:1))")
        self.assertRepr(Const(256).rotate_left(-7),
                        "(cat (slice (const 9'd256) 7:9) (slice (const 9'd256) 0:7))")

    def test_rotate_left_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Rotate amount must be an integer, not 'str'$"):
            Const(31).rotate_left("str")

    def test_rotate_right(self):
        self.assertRepr(Const(256).rotate_right(1),
                        "(cat (slice (const 9'd256) 1:9) (slice (const 9'd256) 0:1))")
        self.assertRepr(Const(256).rotate_right(7),
                        "(cat (slice (const 9'd256) 7:9) (slice (const 9'd256) 0:7))")
        self.assertRepr(Const(256).rotate_right(-1),
                        "(cat (slice (const 9'd256) 8:9) (slice (const 9'd256) 0:8))")
        self.assertRepr(Const(256).rotate_right(-7),
                        "(cat (slice (const 9'd256) 2:9) (slice (const 9'd256) 0:2))")

    def test_rotate_right_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Rotate amount must be an integer, not 'str'$"):
            Const(31).rotate_right("str")


class ConstTestCase(FHDLTestCase):
    def test_shape(self):
        self.assertEqual(Const(0).shape(),   unsigned(1))
        self.assertIsInstance(Const(0).shape(), Shape)
        self.assertEqual(Const(1).shape(),   unsigned(1))
        self.assertEqual(Const(10).shape(),  unsigned(4))
        self.assertEqual(Const(-10).shape(), signed(5))

        self.assertEqual(Const(1, 4).shape(),          unsigned(4))
        self.assertEqual(Const(-1, 4).shape(),         signed(4))
        self.assertEqual(Const(1, signed(4)).shape(),  signed(4))
        self.assertEqual(Const(0, unsigned(0)).shape(), unsigned(0))

    def test_shape_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Width must be a non-negative integer, not -1$"):
            Const(1, -1)

    def test_normalization(self):
        self.assertEqual(Const(0b10110, signed(5)).value, -10)

    def test_value(self):
        self.assertEqual(Const(10).value, 10)

    def test_repr(self):
        self.assertEqual(repr(Const(10)),  "(const 4'd10)")
        self.assertEqual(repr(Const(-10)), "(const 5'sd-10)")

    def test_hash(self):
        with self.assertRaises(TypeError):
            hash(Const(0))


class OperatorTestCase(FHDLTestCase):
    def test_bool(self):
        v = Const(0, 4).bool()
        self.assertEqual(repr(v), "(b (const 4'd0))")
        self.assertEqual(v.shape(), unsigned(1))

    def test_invert(self):
        v = ~Const(0, 4)
        self.assertEqual(repr(v), "(~ (const 4'd0))")
        self.assertEqual(v.shape(), unsigned(4))

    def test_as_unsigned(self):
        v = Const(-1, signed(4)).as_unsigned()
        self.assertEqual(repr(v), "(u (const 4'sd-1))")
        self.assertEqual(v.shape(), unsigned(4))

    def test_as_signed(self):
        v = Const(1, unsigned(4)).as_signed()
        self.assertEqual(repr(v), "(s (const 4'd1))")
        self.assertEqual(v.shape(), signed(4))

    def test_neg(self):
        v1 = -Const(0, unsigned(4))
        self.assertEqual(repr(v1), "(- (const 4'd0))")
        self.assertEqual(v1.shape(), signed(5))
        v2 = -Const(0, signed(4))
        self.assertEqual(repr(v2), "(- (const 4'sd0))")
        self.assertEqual(v2.shape(), signed(5))

    def test_add(self):
        v1 = Const(0, unsigned(4)) + Const(0, unsigned(6))
        self.assertEqual(repr(v1), "(+ (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(7))
        v2 = Const(0, signed(4)) + Const(0, signed(6))
        self.assertEqual(v2.shape(), signed(7))
        v3 = Const(0, signed(4)) + Const(0, unsigned(4))
        self.assertEqual(v3.shape(), signed(6))
        v4 = Const(0, unsigned(4)) + Const(0, signed(4))
        self.assertEqual(v4.shape(), signed(6))
        v5 = 10 + Const(0, 4)
        self.assertEqual(v5.shape(), unsigned(5))

    def test_sub(self):
        v1 = Const(0, unsigned(4)) - Const(0, unsigned(6))
        self.assertEqual(repr(v1), "(- (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(7))
        v2 = Const(0, signed(4)) - Const(0, signed(6))
        self.assertEqual(v2.shape(), signed(7))
        v3 = Const(0, signed(4)) - Const(0, unsigned(4))
        self.assertEqual(v3.shape(), signed(6))
        v4 = Const(0, unsigned(4)) - Const(0, signed(4))
        self.assertEqual(v4.shape(), signed(6))
        v5 = 10 - Const(0, 4)
        self.assertEqual(v5.shape(), unsigned(5))

    def test_mul(self):
        v1 = Const(0, unsigned(4)) * Const(0, unsigned(6))
        self.assertEqual(repr(v1), "(* (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(10))
        v2 = Const(0, signed(4)) * Const(0, signed(6))
        self.assertEqual(v2.shape(), signed(10))
        v3 = Const(0, signed(4)) * Const(0, unsigned(4))
        self.assertEqual(v3.shape(), signed(8))
        v5 = 10 * Const(0, 4)
        self.assertEqual(v5.shape(), unsigned(8))

    def test_mod(self):
        v1 = Const(0, unsigned(4)) % Const(0, unsigned(6))
        self.assertEqual(repr(v1), "(% (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(6))
        v3 = Const(0, signed(4)) % Const(0, unsigned(4))
        self.assertEqual(v3.shape(), unsigned(4))
        v4 = Const(0, signed(4)) % Const(0, signed(6))
        self.assertEqual(v4.shape(), signed(6))
        v5 = 10 % Const(0, 4)
        self.assertEqual(v5.shape(), unsigned(4))

    def test_floordiv(self):
        v1 = Const(0, unsigned(4)) // Const(0, unsigned(6))
        self.assertEqual(repr(v1), "(// (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(4))
        v3 = Const(0, signed(4)) // Const(0, unsigned(4))
        self.assertEqual(v3.shape(), signed(4))
        v4 = Const(0, signed(4)) // Const(0, signed(6))
        self.assertEqual(v4.shape(), signed(5))
        v5 = 10 // Const(0, 4)
        self.assertEqual(v5.shape(), unsigned(4))

    def test_and(self):
        v1 = Const(0, unsigned(4)) & Const(0, unsigned(6))
        self.assertEqual(repr(v1), "(& (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(6))
        v2 = Const(0, signed(4)) & Const(0, signed(6))
        self.assertEqual(v2.shape(), signed(6))
        v3 = Const(0, signed(4)) & Const(0, unsigned(4))
        self.assertEqual(v3.shape(), signed(5))
        v4 = Const(0, unsigned(4)) & Const(0, signed(4))
        self.assertEqual(v4.shape(), signed(5))
        v5 = 10 & Const(0, 4)
        self.assertEqual(v5.shape(), unsigned(4))

    def test_or(self):
        v1 = Const(0, unsigned(4)) | Const(0, unsigned(6))
        self.assertEqual(repr(v1), "(| (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(6))
        v2 = Const(0, signed(4)) | Const(0, signed(6))
        self.assertEqual(v2.shape(), signed(6))
        v3 = Const(0, signed(4)) | Const(0, unsigned(4))
        self.assertEqual(v3.shape(), signed(5))
        v4 = Const(0, unsigned(4)) | Const(0, signed(4))
        self.assertEqual(v4.shape(), signed(5))
        v5 = 10 | Const(0, 4)
        self.assertEqual(v5.shape(), unsigned(4))

    def test_xor(self):
        v1 = Const(0, unsigned(4)) ^ Const(0, unsigned(6))
        self.assertEqual(repr(v1), "(^ (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(6))
        v2 = Const(0, signed(4)) ^ Const(0, signed(6))
        self.assertEqual(v2.shape(), signed(6))
        v3 = Const(0, signed(4)) ^ Const(0, unsigned(4))
        self.assertEqual(v3.shape(), signed(5))
        v4 = Const(0, unsigned(4)) ^ Const(0, signed(4))
        self.assertEqual(v4.shape(), signed(5))
        v5 = 10 ^ Const(0, 4)
        self.assertEqual(v5.shape(), unsigned(4))

    def test_shl(self):
        v1 = Const(1, 4) << Const(4)
        self.assertEqual(repr(v1), "(<< (const 4'd1) (const 3'd4))")
        self.assertEqual(v1.shape(), unsigned(11))

    def test_shl_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Shift amount must be unsigned$"):
            1 << Const(0, signed(6))
        with self.assertRaisesRegex(TypeError,
                r"^Shift amount must be unsigned$"):
            Const(1, unsigned(4)) << -1

    def test_shr(self):
        v1 = Const(1, 4) >> Const(4)
        self.assertEqual(repr(v1), "(>> (const 4'd1) (const 3'd4))")
        self.assertEqual(v1.shape(), unsigned(4))

    def test_shr_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Shift amount must be unsigned$"):
            1 << Const(0, signed(6))
        with self.assertRaisesRegex(TypeError,
                r"^Shift amount must be unsigned$"):
            Const(1, unsigned(4)) << -1

    def test_lt(self):
        v = Const(0, 4) < Const(0, 6)
        self.assertEqual(repr(v), "(< (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), unsigned(1))

    def test_le(self):
        v = Const(0, 4) <= Const(0, 6)
        self.assertEqual(repr(v), "(<= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), unsigned(1))

    def test_gt(self):
        v = Const(0, 4) > Const(0, 6)
        self.assertEqual(repr(v), "(> (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), unsigned(1))

    def test_ge(self):
        v = Const(0, 4) >= Const(0, 6)
        self.assertEqual(repr(v), "(>= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), unsigned(1))

    def test_eq(self):
        v = Const(0, 4) == Const(0, 6)
        self.assertEqual(repr(v), "(== (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), unsigned(1))

    def test_ne(self):
        v = Const(0, 4) != Const(0, 6)
        self.assertEqual(repr(v), "(!= (const 4'd0) (const 6'd0))")
        self.assertEqual(v.shape(), unsigned(1))

    def test_mux(self):
        s  = Const(0)
        v1 = Mux(s, Const(0, unsigned(4)), Const(0, unsigned(6)))
        self.assertEqual(repr(v1), "(m (const 1'd0) (const 4'd0) (const 6'd0))")
        self.assertEqual(v1.shape(), unsigned(6))
        v2 = Mux(s, Const(0, signed(4)), Const(0, signed(6)))
        self.assertEqual(v2.shape(), signed(6))
        v3 = Mux(s, Const(0, signed(4)), Const(0, unsigned(4)))
        self.assertEqual(v3.shape(), signed(5))
        v4 = Mux(s, Const(0, unsigned(4)), Const(0, signed(4)))
        self.assertEqual(v4.shape(), signed(5))

    def test_mux_wide(self):
        s = Const(0b100)
        v = Mux(s, Const(0, unsigned(4)), Const(0, unsigned(6)))
        self.assertEqual(repr(v), "(m (const 3'd4) (const 4'd0) (const 6'd0))")

    def test_mux_bool(self):
        v = Mux(True, Const(0), Const(0))
        self.assertEqual(repr(v), "(m (const 1'd1) (const 1'd0) (const 1'd0))")

    def test_any(self):
        v = Const(0b101).any()
        self.assertEqual(repr(v), "(r| (const 3'd5))")

    def test_all(self):
        v = Const(0b101).all()
        self.assertEqual(repr(v), "(r& (const 3'd5))")

    def test_xor_value(self):
        v = Const(0b101).xor()
        self.assertEqual(repr(v), "(r^ (const 3'd5))")

    def test_matches(self):
        s = Signal(4)
        self.assertRepr(s.matches(), "(const 1'd0)")
        self.assertRepr(s.matches(1), """
        (== (sig s) (const 1'd1))
        """)
        self.assertRepr(s.matches(0, 1), """
        (r| (cat (== (sig s) (const 1'd0)) (== (sig s) (const 1'd1))))
        """)
        self.assertRepr(s.matches("10--"), """
        (== (& (sig s) (const 4'd12)) (const 4'd8))
        """)
        self.assertRepr(s.matches("1 0--"), """
        (== (& (sig s) (const 4'd12)) (const 4'd8))
        """)

    def test_matches_enum(self):
        s = Signal(SignedEnum)
        self.assertRepr(s.matches(SignedEnum.FOO), """
        (== (sig s) (const 1'sd-1))
        """)

    def test_matches_width_wrong(self):
        s = Signal(4)
        with self.assertRaisesRegex(SyntaxError,
                r"^Match pattern '--' must have the same width as match value \(which is 4\)$"):
            s.matches("--")
        with self.assertWarnsRegex(SyntaxWarning,
                (r"^Match pattern '10110' is wider than match value \(which has width 4\); "
                    r"comparison will never be true$")):
            s.matches(0b10110)

    def test_matches_bits_wrong(self):
        s = Signal(4)
        with self.assertRaisesRegex(SyntaxError,
                (r"^Match pattern 'abc' must consist of 0, 1, and - \(don't care\) bits, "
                    r"and may include whitespace$")):
            s.matches("abc")

    def test_matches_pattern_wrong(self):
        s = Signal(4)
        with self.assertRaisesRegex(SyntaxError,
                r"^Match pattern must be an integer, a string, or an enumeration, not 1\.0$"):
            s.matches(1.0)

    def test_hash(self):
        with self.assertRaises(TypeError):
            hash(Const(0) + Const(0))


class SliceTestCase(FHDLTestCase):
    def test_shape(self):
        s1 = Const(10)[2]
        self.assertEqual(s1.shape(), unsigned(1))
        self.assertIsInstance(s1.shape(), Shape)
        s2 = Const(-10)[0:2]
        self.assertEqual(s2.shape(), unsigned(2))

    def test_start_end_negative(self):
        c  = Const(0, 8)
        s1 = Slice(c, 0, -1)
        self.assertEqual((s1.start, s1.stop), (0, 7))
        s1 = Slice(c, -4, -1)
        self.assertEqual((s1.start, s1.stop), (4, 7))

    def test_start_end_bool(self):
        c  = Const(0, 8)
        s  = Slice(c, False, True)
        self.assertIs(type(s.start), int)
        self.assertIs(type(s.stop),  int)

    def test_start_end_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Slice start must be an integer, not 'x'$"):
            Slice(0, "x", 1)
        with self.assertRaisesRegex(TypeError,
                r"^Slice stop must be an integer, not 'x'$"):
            Slice(0, 1, "x")

    def test_start_end_out_of_range(self):
        c = Const(0, 8)
        with self.assertRaisesRegex(IndexError,
                r"^Cannot start slice 10 bits into 8-bit value$"):
            Slice(c, 10, 12)
        with self.assertRaisesRegex(IndexError,
                r"^Cannot stop slice 12 bits into 8-bit value$"):
            Slice(c, 0, 12)
        with self.assertRaisesRegex(IndexError,
                r"^Slice start 4 must be less than slice stop 2$"):
            Slice(c, 4, 2)

    def test_repr(self):
        s1 = Const(10)[2]
        self.assertEqual(repr(s1), "(slice (const 4'd10) 2:3)")


class BitSelectTestCase(FHDLTestCase):
    def setUp(self):
        self.c = Const(0, 8)
        self.s = Signal(range(self.c.width))

    def test_shape(self):
        s1 = self.c.bit_select(self.s, 2)
        self.assertIsInstance(s1, Part)
        self.assertEqual(s1.shape(), unsigned(2))
        self.assertIsInstance(s1.shape(), Shape)
        s2 = self.c.bit_select(self.s, 0)
        self.assertIsInstance(s2, Part)
        self.assertEqual(s2.shape(), unsigned(0))

    def test_stride(self):
        s1 = self.c.bit_select(self.s, 2)
        self.assertIsInstance(s1, Part)
        self.assertEqual(s1.stride, 1)

    def test_const(self):
        s1 = self.c.bit_select(1, 2)
        self.assertIsInstance(s1, Slice)
        self.assertRepr(s1, """(slice (const 8'd0) 1:3)""")

    def test_width_wrong(self):
        with self.assertRaises(TypeError):
            self.c.bit_select(self.s, -1)

    def test_repr(self):
        s = self.c.bit_select(self.s, 2)
        self.assertEqual(repr(s), "(part (const 8'd0) (sig s) 2 1)")


class WordSelectTestCase(FHDLTestCase):
    def setUp(self):
        self.c = Const(0, 8)
        self.s = Signal(range(self.c.width))

    def test_shape(self):
        s1 = self.c.word_select(self.s, 2)
        self.assertIsInstance(s1, Part)
        self.assertEqual(s1.shape(), unsigned(2))
        self.assertIsInstance(s1.shape(), Shape)

    def test_stride(self):
        s1 = self.c.word_select(self.s, 2)
        self.assertIsInstance(s1, Part)
        self.assertEqual(s1.stride, 2)

    def test_const(self):
        s1 = self.c.word_select(1, 2)
        self.assertIsInstance(s1, Slice)
        self.assertRepr(s1, """(slice (const 8'd0) 2:4)""")

    def test_width_wrong(self):
        with self.assertRaises(TypeError):
            self.c.word_select(self.s, 0)
        with self.assertRaises(TypeError):
            self.c.word_select(self.s, -1)

    def test_repr(self):
        s = self.c.word_select(self.s, 2)
        self.assertEqual(repr(s), "(part (const 8'd0) (sig s) 2 2)")


class CatTestCase(FHDLTestCase):
    def test_shape(self):
        c0 = Cat()
        self.assertEqual(c0.shape(), unsigned(0))
        self.assertIsInstance(c0.shape(), Shape)
        c1 = Cat(Const(10))
        self.assertEqual(c1.shape(), unsigned(4))
        c2 = Cat(Const(10), Const(1))
        self.assertEqual(c2.shape(), unsigned(5))
        c3 = Cat(Const(10), Const(1), Const(0))
        self.assertEqual(c3.shape(), unsigned(6))

    def test_repr(self):
        c1 = Cat(Const(10), Const(1))
        self.assertEqual(repr(c1), "(cat (const 4'd10) (const 1'd1))")

    def test_cast(self):
        c = Cat(1, 0)
        self.assertEqual(repr(c), "(cat (const 1'd1) (const 1'd0))")
    
    def test_str_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object 'foo' cannot be converted to an Amaranth value$"):
            Cat("foo")

    def test_int_01(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(action="error", category=SyntaxWarning)
            Cat(0, 1, 1, 0)

    def test_int_wrong(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Argument #1 of Cat\(\) is a bare integer 2 used in bit vector context; "
                r"consider specifying explicit width using C\(2, 2\) instead$"):
            Cat(2)


class ReplTestCase(FHDLTestCase):
    def test_shape(self):
        s1 = Repl(Const(10), 3)
        self.assertEqual(s1.shape(), unsigned(12))
        self.assertIsInstance(s1.shape(), Shape)
        s2 = Repl(Const(10), 0)
        self.assertEqual(s2.shape(), unsigned(0))

    def test_count_wrong(self):
        with self.assertRaises(TypeError):
            Repl(Const(10), -1)
        with self.assertRaises(TypeError):
            Repl(Const(10), "str")

    def test_repr(self):
        s = Repl(Const(10), 3)
        self.assertEqual(repr(s), "(repl (const 4'd10) 3)")

    def test_cast(self):
        r = Repl(0, 3)
        self.assertEqual(repr(r), "(repl (const 1'd0) 3)")

    def test_int_01(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(action="error", category=SyntaxWarning)
            Repl(0, 3)
            Repl(1, 3)

    def test_int_wrong(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value argument of Repl\(\) is a bare integer 2 used in bit vector context; "
                r"consider specifying explicit width using C\(2, 2\) instead$"):
            Repl(2, 3)


class ArrayTestCase(FHDLTestCase):
    def test_acts_like_array(self):
        a = Array([1,2,3])
        self.assertSequenceEqual(a, [1,2,3])
        self.assertEqual(a[1], 2)
        a[1] = 4
        self.assertSequenceEqual(a, [1,4,3])
        del a[1]
        self.assertSequenceEqual(a, [1,3])
        a.insert(1, 2)
        self.assertSequenceEqual(a, [1,2,3])

    def test_becomes_immutable(self):
        a = Array([1,2,3])
        s1 = Signal(range(len(a)))
        s2 = Signal(range(len(a)))
        v1 = a[s1]
        v2 = a[s2]
        with self.assertRaisesRegex(ValueError,
                r"^Array can no longer be mutated after it was indexed with a value at "):
            a[1] = 2
        with self.assertRaisesRegex(ValueError,
                r"^Array can no longer be mutated after it was indexed with a value at "):
            del a[1]
        with self.assertRaisesRegex(ValueError,
                r"^Array can no longer be mutated after it was indexed with a value at "):
            a.insert(1, 2)

    def test_repr(self):
        a = Array([1,2,3])
        self.assertEqual(repr(a), "(array mutable [1, 2, 3])")
        s = Signal(range(len(a)))
        v = a[s]
        self.assertEqual(repr(a), "(array [1, 2, 3])")


class ArrayProxyTestCase(FHDLTestCase):
    def test_index_shape(self):
        m = Array(Array(x * y for y in range(1, 4)) for x in range(1, 4))
        a = Signal(range(3))
        b = Signal(range(3))
        v = m[a][b]
        self.assertEqual(v.shape(), unsigned(4))

    def test_attr_shape(self):
        from collections import namedtuple
        pair = namedtuple("pair", ("p", "n"))
        a = Array(pair(i, -i) for i in range(10))
        s = Signal(range(len(a)))
        v = a[s]
        self.assertEqual(v.p.shape(), unsigned(4))
        self.assertEqual(v.n.shape(), signed(5))

    def test_attr_shape_signed(self):
        # [unsigned(1), unsigned(1)] → unsigned(1)
        a1 = Array([1, 1])
        v1 = a1[Const(0)]
        self.assertEqual(v1.shape(), unsigned(1))
        # [signed(1), signed(1)] → signed(1)
        a2 = Array([-1, -1])
        v2 = a2[Const(0)]
        self.assertEqual(v2.shape(), signed(1))
        # [unsigned(1), signed(2)] → signed(2)
        a3 = Array([1, -2])
        v3 = a3[Const(0)]
        self.assertEqual(v3.shape(), signed(2))
        # [unsigned(1), signed(1)] → signed(2); 1st operand padded with sign bit!
        a4 = Array([1, -1])
        v4 = a4[Const(0)]
        self.assertEqual(v4.shape(), signed(2))
        # [unsigned(2), signed(1)] → signed(3); 1st operand padded with sign bit!
        a5 = Array([1, -1])
        v5 = a5[Const(0)]
        self.assertEqual(v5.shape(), signed(2))

    def test_repr(self):
        a = Array([1, 2, 3])
        s = Signal(range(3))
        v = a[s]
        self.assertEqual(repr(v), "(proxy (array [1, 2, 3]) (sig s))")


class SignalTestCase(FHDLTestCase):
    def test_shape(self):
        s1 = Signal()
        self.assertEqual(s1.shape(), unsigned(1))
        self.assertIsInstance(s1.shape(), Shape)
        s2 = Signal(2)
        self.assertEqual(s2.shape(), unsigned(2))
        s3 = Signal(unsigned(2))
        self.assertEqual(s3.shape(), unsigned(2))
        s4 = Signal(signed(2))
        self.assertEqual(s4.shape(), signed(2))
        s5 = Signal(0)
        self.assertEqual(s5.shape(), unsigned(0))
        s6 = Signal(range(16))
        self.assertEqual(s6.shape(), unsigned(4))
        s7 = Signal(range(4, 16))
        self.assertEqual(s7.shape(), unsigned(4))
        s8 = Signal(range(-4, 16))
        self.assertEqual(s8.shape(), signed(5))
        s9 = Signal(range(-20, 16))
        self.assertEqual(s9.shape(), signed(6))
        s10 = Signal(range(0))
        self.assertEqual(s10.shape(), unsigned(0))
        s11 = Signal(range(1))
        self.assertEqual(s11.shape(), unsigned(1))

    def test_shape_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Width must be a non-negative integer, not -10$"):
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

    def test_reset_enum(self):
        s1 = Signal(2, reset=UnsignedEnum.BAR)
        self.assertEqual(s1.reset, 2)
        with self.assertRaisesRegex(TypeError,
                r"^Reset value has to be an int or an integral Enum$"
        ):
            Signal(1, reset=StringEnum.FOO)

    def test_reset_narrow(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Reset value 8 requires 4 bits to represent, but the signal only has 3 bits$"):
            Signal(3, reset=8)
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Reset value 4 requires 4 bits to represent, but the signal only has 3 bits$"):
            Signal(signed(3), reset=4)
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Reset value -5 requires 4 bits to represent, but the signal only has 3 bits$"):
            Signal(signed(3), reset=-5)

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
        self.assertEqual(s1.shape(), unsigned(4))
        s2 = Signal.like(Signal(range(-15, 1)))
        self.assertEqual(s2.shape(), signed(5))
        s3 = Signal.like(Signal(4, reset=0b111, reset_less=True))
        self.assertEqual(s3.reset, 0b111)
        self.assertEqual(s3.reset_less, True)
        s4 = Signal.like(Signal(attrs={"no_retiming": True}))
        self.assertEqual(s4.attrs, {"no_retiming": True})
        s5 = Signal.like(Signal(decoder=str))
        self.assertEqual(s5.decoder, str)
        s6 = Signal.like(10)
        self.assertEqual(s6.shape(), unsigned(4))
        s7 = [Signal.like(Signal(4))][0]
        self.assertEqual(s7.name, "$like")
        s8 = Signal.like(s1, name_suffix="_ff")
        self.assertEqual(s8.name, "s1_ff")

    def test_decoder(self):
        class Color(Enum):
            RED  = 1
            BLUE = 2
        s = Signal(decoder=Color)
        self.assertEqual(s.decoder(1), "RED/1")
        self.assertEqual(s.decoder(3), "3")

    def test_enum(self):
        s1 = Signal(UnsignedEnum)
        self.assertEqual(s1.shape(), unsigned(2))
        s2 = Signal(SignedEnum)
        self.assertEqual(s2.shape(), signed(2))
        self.assertEqual(s2.decoder(SignedEnum.FOO), "FOO/-1")


class ClockSignalTestCase(FHDLTestCase):
    def test_domain(self):
        s1 = ClockSignal()
        self.assertEqual(s1.domain, "sync")
        s2 = ClockSignal("pix")
        self.assertEqual(s2.domain, "pix")

        with self.assertRaisesRegex(TypeError,
                r"^Clock domain name must be a string, not 1$"):
            ClockSignal(1)

    def test_shape(self):
        s1 = ClockSignal()
        self.assertEqual(s1.shape(), unsigned(1))
        self.assertIsInstance(s1.shape(), Shape)

    def test_repr(self):
        s1 = ClockSignal()
        self.assertEqual(repr(s1), "(clk sync)")

    def test_wrong_name_comb(self):
        with self.assertRaisesRegex(ValueError,
                r"^Domain 'comb' does not have a clock$"):
            ClockSignal("comb")


class ResetSignalTestCase(FHDLTestCase):
    def test_domain(self):
        s1 = ResetSignal()
        self.assertEqual(s1.domain, "sync")
        s2 = ResetSignal("pix")
        self.assertEqual(s2.domain, "pix")

        with self.assertRaisesRegex(TypeError,
                r"^Clock domain name must be a string, not 1$"):
            ResetSignal(1)

    def test_shape(self):
        s1 = ResetSignal()
        self.assertEqual(s1.shape(), unsigned(1))
        self.assertIsInstance(s1.shape(), Shape)

    def test_repr(self):
        s1 = ResetSignal()
        self.assertEqual(repr(s1), "(rst sync)")

    def test_wrong_name_comb(self):
        with self.assertRaisesRegex(ValueError,
                r"^Domain 'comb' does not have a reset$"):
            ResetSignal("comb")


class MockUserValue(UserValue):
    def __init__(self, lowered):
        super().__init__()
        self.lower_count = 0
        self.lowered     = lowered

    def lower(self):
        self.lower_count += 1
        return self.lowered


class UserValueTestCase(FHDLTestCase):
    def test_shape(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore", category=DeprecationWarning)
            uv = MockUserValue(1)
            self.assertEqual(uv.shape(), unsigned(1))
            self.assertIsInstance(uv.shape(), Shape)
            uv.lowered = 2
            self.assertEqual(uv.shape(), unsigned(1))
            self.assertEqual(uv.lower_count, 1)

    def test_lower_to_user_value(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore", category=DeprecationWarning)
            uv = MockUserValue(MockUserValue(1))
            self.assertEqual(uv.shape(), unsigned(1))
            self.assertIsInstance(uv.shape(), Shape)
            uv.lowered = MockUserValue(2)
            self.assertEqual(uv.shape(), unsigned(1))
            self.assertEqual(uv.lower_count, 1)


class MockValueCastableChanges(ValueCastable):
    def __init__(self, width=0):
        self.width = width

    @ValueCastable.lowermethod
    def as_value(self):
        return Signal(self.width)


class MockValueCastableNotDecorated(ValueCastable):
    def __init__(self):
        pass

    def as_value(self):
        return Signal()


class MockValueCastableNoOverride(ValueCastable):
    def __init__(self):
        pass


class MockValueCastableCustomGetattr(ValueCastable):
    def __init__(self):
        pass

    @ValueCastable.lowermethod
    def as_value(self):
        return Const(0)

    def __getattr__(self, attr):
        assert False


class ValueCastableTestCase(FHDLTestCase):
    def test_not_decorated(self):
        with self.assertRaisesRegex(TypeError,
                r"^Class 'MockValueCastableNotDecorated' deriving from `ValueCastable` must decorate the `as_value` "
                r"method with the `ValueCastable.lowermethod` decorator$"):
            vc = MockValueCastableNotDecorated()

    def test_no_override(self):
        with self.assertRaisesRegex(TypeError,
                r"^Class 'MockValueCastableNoOverride' deriving from `ValueCastable` must override the `as_value` "
                r"method$"):
            vc = MockValueCastableNoOverride()

    def test_memoized(self):
        vc = MockValueCastableChanges(1)
        sig1 = vc.as_value()
        vc.width = 2
        sig2 = vc.as_value()
        self.assertIs(sig1, sig2)
        vc.width = 3
        sig3 = Value.cast(vc)
        self.assertIs(sig1, sig3)

    def test_custom_getattr(self):
        vc = MockValueCastableCustomGetattr()
        vc.as_value() # shouldn't call __getattr__


class SampleTestCase(FHDLTestCase):
    def test_const(self):
        s = Sample(1, 1, "sync")
        self.assertEqual(s.shape(), unsigned(1))

    def test_signal(self):
        s1 = Sample(Signal(2), 1, "sync")
        self.assertEqual(s1.shape(), unsigned(2))
        s2 = Sample(ClockSignal(), 1, "sync")
        s3 = Sample(ResetSignal(), 1, "sync")

    def test_wrong_value_operator(self):
        with self.assertRaisesRegex(TypeError,
                (r"^Sampled value must be a signal or a constant, not "
                r"\(\+ \(sig \$signal\) \(const 1'd1\)\)$")):
            Sample(Signal() + 1, 1, "sync")

    def test_wrong_clocks_neg(self):
        with self.assertRaisesRegex(ValueError,
                r"^Cannot sample a value 1 cycles in the future$"):
            Sample(Signal(), -1, "sync")

    def test_wrong_domain(self):
        with self.assertRaisesRegex(TypeError,
                r"^Domain name must be a string or None, not 0$"):
            Sample(Signal(), 1, 0)


class InitialTestCase(FHDLTestCase):
    def test_initial(self):
        i = Initial()
        self.assertEqual(i.shape(), unsigned(1))


class SwitchTestCase(FHDLTestCase):
    def test_default_case(self):
        s = Switch(Const(0), {None: []})
        self.assertEqual(s.cases, {(): []})

    def test_int_case(self):
        s = Switch(Const(0, 8), {10: []})
        self.assertEqual(s.cases, {("00001010",): []})

    def test_int_neg_case(self):
        s = Switch(Const(0, 8), {-10: []})
        self.assertEqual(s.cases, {("11110110",): []})

    def test_enum_case(self):
        s = Switch(Const(0, UnsignedEnum), {UnsignedEnum.FOO: []})
        self.assertEqual(s.cases, {("01",): []})

    def test_str_case(self):
        s = Switch(Const(0, 8), {"0000 11\t01": []})
        self.assertEqual(s.cases, {("00001101",): []})

    def test_two_cases(self):
        s = Switch(Const(0, 8), {("00001111", 123): []})
        self.assertEqual(s.cases, {("00001111", "01111011"): []})
