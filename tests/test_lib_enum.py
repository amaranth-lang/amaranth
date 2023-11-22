import enum as py_enum
import operator
import sys

from amaranth import *
from amaranth.lib.enum import Enum, EnumMeta, Flag, IntEnum, EnumView, FlagView

from .utils import *


class EnumTestCase(FHDLTestCase):
    def test_members_non_int(self):
        # Mustn't raise to be a drop-in replacement for Enum.
        class EnumA(Enum):
            A = "str"

    def test_members_const_non_int(self):
        class EnumA(Enum):
            A = C(0)
            B = C(1)
        self.assertIs(EnumA.A.value, 0)
        self.assertIs(EnumA.B.value, 1)
        self.assertEqual(Shape.cast(EnumA), unsigned(1))

    def test_shape_no_members(self):
        class EnumA(Enum):
            pass
        class PyEnumA(py_enum.Enum):
            pass
        self.assertEqual(Shape.cast(EnumA), unsigned(0))
        self.assertEqual(Shape.cast(PyEnumA), unsigned(0))

    def test_shape_explicit(self):
        class EnumA(Enum, shape=signed(2)):
            pass
        self.assertEqual(Shape.cast(EnumA), signed(2))

    def test_shape_explicit_cast(self):
        class EnumA(Enum, shape=range(10)):
            pass
        self.assertEqual(Shape.cast(EnumA), unsigned(4))

    def test_shape_implicit(self):
        class EnumA(Enum):
            A = 0
            B = 1
        self.assertEqual(Shape.cast(EnumA), unsigned(1))
        class EnumB(Enum):
            A = 0
            B = 5
        self.assertEqual(Shape.cast(EnumB), unsigned(3))
        class EnumC(Enum):
            A = 0
            B = -1
        self.assertEqual(Shape.cast(EnumC), signed(2))
        class EnumD(Enum):
            A = 3
            B = -5
        self.assertEqual(Shape.cast(EnumD), signed(4))

    def test_shape_members_non_const_non_int_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Value 'str' of enumeration member 'A' must be a constant-castable expression$"):
            class EnumA(Enum, shape=unsigned(1)):
                A = "str"

    def test_shape_explicit_wrong_signed_mismatch(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value -1 of enumeration member 'A' is signed, but the enumeration "
                r"shape is unsigned\(1\)$"):
            class EnumA(Enum, shape=unsigned(1)):
                A = -1

    def test_shape_explicit_wrong_too_wide(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value 2 of enumeration member 'A' will be truncated to the enumeration "
                r"shape unsigned\(1\)$"):
            class EnumA(Enum, shape=unsigned(1)):
                A = 2
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value 1 of enumeration member 'A' will be truncated to the enumeration "
                r"shape signed\(1\)$"):
            class EnumB(Enum, shape=signed(1)):
                A = 1
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value -2 of enumeration member 'A' will be truncated to the "
                r"enumeration shape signed\(1\)$"):
            class EnumC(Enum, shape=signed(1)):
                A = -2

    def test_value_shape_from_enum_member(self):
        class EnumA(Enum, shape=unsigned(10)):
            A = 1
        self.assertRepr(Value.cast(EnumA.A), "(const 10'd1)")

    def test_no_shape(self):
        class EnumA(Enum):
            Z = 0
            A = 10
            B = 20
        self.assertNotIsInstance(EnumA, EnumMeta)
        self.assertIsInstance(EnumA, py_enum.EnumMeta)

    def test_const_shape(self):
        class EnumA(Enum, shape=8):
            Z = 0
            A = 10
        self.assertRepr(EnumA.const(None), "EnumView(EnumA, (const 8'd0))")
        self.assertRepr(EnumA.const(10), "EnumView(EnumA, (const 8'd10))")
        self.assertRepr(EnumA.const(EnumA.A), "EnumView(EnumA, (const 8'd10))")

    def test_shape_implicit_wrong_in_concat(self):
        class EnumA(Enum):
            A = 0
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Argument #1 of Cat\(\) is an enumerated value <EnumA\.A: 0> without a defined "
                r"shape used in bit vector context; define the enumeration by inheriting from "
                r"the class in amaranth\.lib\.enum and specifying the 'shape=' keyword argument$"):
            Cat(EnumA.A)

    def test_functional(self):
        Enum("FOO", ["BAR", "BAZ"])

    def test_int_enum(self):
        class EnumA(IntEnum, shape=signed(4)):
            A = 0
            B = -3
        a = Signal(EnumA)
        self.assertRepr(a, "(sig a)")

    def test_enum_view(self):
        class EnumA(Enum, shape=signed(4)):
            A = 0
            B = -3
        class EnumB(Enum, shape=signed(4)):
            C = 0
            D = 5
        a = Signal(EnumA)
        b = Signal(EnumB)
        c = Signal(EnumA)
        d = Signal(4)
        self.assertIsInstance(a, EnumView)
        self.assertIs(a.shape(), EnumA)
        self.assertRepr(a, "EnumView(EnumA, (sig a))")
        self.assertRepr(a.as_value(), "(sig a)")
        self.assertRepr(a.eq(c), "(eq (sig a) (sig c))")
        for op in [
            operator.__add__,
            operator.__sub__,
            operator.__mul__,
            operator.__floordiv__,
            operator.__mod__,
            operator.__lshift__,
            operator.__rshift__,
            operator.__and__,
            operator.__or__,
            operator.__xor__,
            operator.__lt__,
            operator.__le__,
            operator.__gt__,
            operator.__ge__,
        ]:
            with self.assertRaises(TypeError):
                op(a, a)
            with self.assertRaises(TypeError):
                op(a, d)
            with self.assertRaises(TypeError):
                op(d, a)
            with self.assertRaises(TypeError):
                op(a, 3)
            with self.assertRaises(TypeError):
                op(a, EnumA.A)
        for op in [
            operator.__eq__,
            operator.__ne__,
        ]:
            with self.assertRaises(TypeError):
                op(a, b)
            with self.assertRaises(TypeError):
                op(a, d)
            with self.assertRaises(TypeError):
                op(d, a)
            with self.assertRaises(TypeError):
                op(a, 3)
            with self.assertRaises(TypeError):
                op(a, EnumB.C)
        self.assertRepr(a == c, "(== (sig a) (sig c))")
        self.assertRepr(a != c, "(!= (sig a) (sig c))")
        self.assertRepr(a == EnumA.B, "(== (sig a) (const 4'sd-3))")
        self.assertRepr(EnumA.B == a, "(== (sig a) (const 4'sd-3))")
        self.assertRepr(a != EnumA.B, "(!= (sig a) (const 4'sd-3))")

    def test_flag_view(self):
        class FlagA(Flag, shape=unsigned(4)):
            A = 1
            B = 4
        class FlagB(Flag, shape=unsigned(4)):
            C = 1
            D = 2
        a = Signal(FlagA)
        b = Signal(FlagB)
        c = Signal(FlagA)
        d = Signal(4)
        self.assertIsInstance(a, FlagView)
        self.assertRepr(a, "FlagView(FlagA, (sig a))")
        for op in [
            operator.__add__,
            operator.__sub__,
            operator.__mul__,
            operator.__floordiv__,
            operator.__mod__,
            operator.__lshift__,
            operator.__rshift__,
            operator.__lt__,
            operator.__le__,
            operator.__gt__,
            operator.__ge__,
        ]:
            with self.assertRaises(TypeError):
                op(a, a)
            with self.assertRaises(TypeError):
                op(a, d)
            with self.assertRaises(TypeError):
                op(d, a)
            with self.assertRaises(TypeError):
                op(a, 3)
            with self.assertRaises(TypeError):
                op(a, FlagA.A)
        for op in [
            operator.__eq__,
            operator.__ne__,
            operator.__and__,
            operator.__or__,
            operator.__xor__,
        ]:
            with self.assertRaises(TypeError):
                op(a, b)
            with self.assertRaises(TypeError):
                op(a, d)
            with self.assertRaises(TypeError):
                op(d, a)
            with self.assertRaises(TypeError):
                op(a, 3)
            with self.assertRaises(TypeError):
                op(a, FlagB.C)
        self.assertRepr(a == c, "(== (sig a) (sig c))")
        self.assertRepr(a != c, "(!= (sig a) (sig c))")
        self.assertRepr(a == FlagA.B, "(== (sig a) (const 4'd4))")
        self.assertRepr(FlagA.B == a, "(== (sig a) (const 4'd4))")
        self.assertRepr(a != FlagA.B, "(!= (sig a) (const 4'd4))")
        self.assertRepr(a | c, "FlagView(FlagA, (| (sig a) (sig c)))")
        self.assertRepr(a & c, "FlagView(FlagA, (& (sig a) (sig c)))")
        self.assertRepr(a ^ c, "FlagView(FlagA, (^ (sig a) (sig c)))")
        self.assertRepr(~a, "FlagView(FlagA, (& (~ (sig a)) (const 3'd5)))")
        self.assertRepr(a | FlagA.B, "FlagView(FlagA, (| (sig a) (const 4'd4)))")
        if sys.version_info >= (3, 11):
            class FlagC(Flag, shape=unsigned(4), boundary=py_enum.KEEP):
                A = 1
                B = 4
            e = Signal(FlagC)
            self.assertRepr(~e, "FlagView(FlagC, (~ (sig e)))")

    def test_enum_view_wrong(self):
        class EnumA(Enum, shape=signed(4)):
            A = 0
            B = -3

        a = Signal(2)
        with self.assertRaisesRegex(TypeError,
                r'^EnumView target must have the same shape as the enum$'):
            EnumA(a)
        with self.assertRaisesRegex(TypeError,
                r'^EnumView target must be a value-castable object, not .*$'):
            EnumView(EnumA, "a")

        class EnumB(Enum):
            C = 0
            D = 1
        with self.assertRaisesRegex(TypeError,
                r'^EnumView type must be an enum with shape, not .*$'):
            EnumView(EnumB, 3)

    def test_enum_view_custom(self):
        class CustomView(EnumView):
            pass
        class EnumA(Enum, view_class=CustomView, shape=unsigned(2)):
            A = 0
            B = 1
        a = Signal(EnumA)
        assert isinstance(a, CustomView)
