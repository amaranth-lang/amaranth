import enum as py_enum

from amaranth import *
from amaranth.lib.enum import Enum

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

    def test_const_no_shape(self):
        class EnumA(Enum):
            Z = 0
            A = 10
            B = 20
        self.assertRepr(EnumA.const(None), "(const 5'd0)")
        self.assertRepr(EnumA.const(10), "(const 5'd10)")
        self.assertRepr(EnumA.const(EnumA.A), "(const 5'd10)")

    def test_const_shape(self):
        class EnumA(Enum, shape=8):
            Z = 0
            A = 10
        self.assertRepr(EnumA.const(None), "(const 8'd0)")
        self.assertRepr(EnumA.const(10), "(const 8'd10)")
        self.assertRepr(EnumA.const(EnumA.A), "(const 8'd10)")

    def test_shape_implicit_wrong_in_concat(self):
        class EnumA(Enum):
            A = 0
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Argument #1 of Cat\(\) is an enumerated value <EnumA\.A: 0> without a defined "
                r"shape used in bit vector context; define the enumeration by inheriting from "
                r"the class in amaranth\.lib\.enum and specifying the 'shape=' keyword argument$"):
            Cat(EnumA.A)
