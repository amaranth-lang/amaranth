from amaranth import *
from amaranth.lib.enum import Enum

from .utils import *


class EnumTestCase(FHDLTestCase):
    def test_non_int_members(self):
        # Mustn't raise to be a drop-in replacement for Enum.
        class EnumA(Enum):
            A = "str"

    def test_non_int_members_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Value of enumeration member <EnumA\.A: 'str'> must be "
                r"a constant-castable expression$"):
            class EnumA(Enum, shape=unsigned(1)):
                A = "str"

    def test_shape_no_members(self):
        class EnumA(Enum):
            pass
        with self.assertRaisesRegex(TypeError,
                r"^Enumeration '.+?\.EnumA' does not have a defined shape$"):
            Shape.cast(EnumA)

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

    def test_shape_explicit_wrong_signed_mismatch(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value of enumeration member <EnumA\.A: -1> is signed, but enumeration "
                r"shape is unsigned\(1\)$"):
            class EnumA(Enum, shape=unsigned(1)):
                A = -1

    def test_shape_explicit_wrong_too_wide(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value of enumeration member <EnumA\.A: 2> will be truncated to enumeration "
                r"shape unsigned\(1\)$"):
            class EnumA(Enum, shape=unsigned(1)):
                A = 2
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value of enumeration member <EnumB\.A: 1> will be truncated to enumeration "
                r"shape signed\(1\)$"):
            class EnumB(Enum, shape=signed(1)):
                A = 1
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Value of enumeration member <EnumC\.A: -2> will be truncated to enumeration "
                r"shape signed\(1\)$"):
            class EnumC(Enum, shape=signed(1)):
                A = -2

    def test_value_shape_from_enum_member(self):
        class EnumA(Enum, shape=unsigned(10)):
            A = 1
        self.assertRepr(Value.cast(EnumA.A), "(const 10'd1)")

    def test_shape_implicit_wrong_in_concat(self):
        class EnumA(Enum):
            A = 0
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Argument #1 of Cat\(\) is an enumerated value <EnumA\.A: 0> without a defined "
                r"shape used in bit vector context; define the enumeration by inheriting from "
                r"the class in amaranth\.lib\.enum and specifying the 'shape=' keyword argument$"):
            Cat(EnumA.A)
