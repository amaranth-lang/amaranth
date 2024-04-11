from enum import Enum
import operator
from unittest import TestCase

from amaranth.hdl import *
from amaranth.lib import data
from amaranth.sim import Simulator

from .utils import *


class MockShapeCastable(ShapeCastable):
    def __init__(self, shape):
        self.shape = shape

    def as_shape(self):
        return self.shape

    def __call__(self, value):
        return value

    def const(self, init):
        return Const(init, self.shape)

    def from_bits(self, bits):
        return bits


class FieldTestCase(TestCase):
    def test_construct(self):
        f = data.Field(unsigned(2), 1)
        self.assertEqual(f.shape, unsigned(2))
        self.assertEqual(f.offset, 1)
        self.assertEqual(f.width, 2)

    def test_repr(self):
        f = data.Field(unsigned(2), 1)
        self.assertEqual(repr(f), "Field(unsigned(2), 1)")

    def test_equal(self):
        f1 = data.Field(unsigned(2), 1)
        f2 = data.Field(unsigned(2), 0)
        self.assertNotEqual(f1, f2)
        f3 = data.Field(unsigned(2), 1)
        self.assertEqual(f1, f3)
        f4 = data.Field(2, 1)
        self.assertEqual(f1, f4)
        f5 = data.Field(MockShapeCastable(unsigned(2)), 1)
        self.assertEqual(f1, f5)
        self.assertNotEqual(f1, object())

    def test_preserve_shape(self):
        sc = MockShapeCastable(unsigned(2))
        f = data.Field(sc, 0)
        self.assertEqual(f.shape, sc)
        self.assertEqual(f.width, 2)

    def test_shape_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Field shape must be a shape-castable object, not <.+>$"):
            data.Field(object(), 0)

    def test_offset_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Field offset must be a non-negative integer, not <.+>$"):
            data.Field(unsigned(2), object())
        with self.assertRaisesRegex(TypeError,
                r"^Field offset must be a non-negative integer, not -1$"):
            data.Field(unsigned(2), -1)

    def test_immutable(self):
        with self.assertRaises(AttributeError):
            data.Field(1, 0).shape = unsigned(2)
        with self.assertRaises(AttributeError):
            data.Field(1, 0).offset = 1


class StructLayoutTestCase(FHDLTestCase):
    def test_construct(self):
        sl = data.StructLayout({
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(sl.members, {
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(sl.size, 3)
        self.assertEqual(list(iter(sl)), [
            ("a", data.Field(unsigned(1), 0)),
            ("b", data.Field(2, 1))
        ])
        self.assertEqual(sl["a"], data.Field(unsigned(1), 0))
        self.assertEqual(sl["b"], data.Field(2, 1))

    def test_size_empty(self):
        self.assertEqual(data.StructLayout({}).size, 0)

    def test_eq(self):
        self.assertEqual(data.StructLayout({"a": unsigned(1), "b": 2}),
                         data.StructLayout({"a": unsigned(1), "b": unsigned(2)}))
        self.assertNotEqual(data.StructLayout({"a": unsigned(1), "b": 2}),
                            data.StructLayout({"b": unsigned(2), "a": unsigned(1)}))
        self.assertNotEqual(data.StructLayout({"a": unsigned(1), "b": 2}),
                            data.StructLayout({"a": unsigned(1)}))

    def test_repr(self):
        sl = data.StructLayout({
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(repr(sl), "StructLayout({'a': unsigned(1), 'b': 2})")

    def test_members_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Struct layout members must be provided as a mapping, not <.+>$"):
            data.StructLayout(object())

    def test_member_key_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Struct layout member name must be a string, not 1\.0$"):
            data.StructLayout({1.0: unsigned(1)})

    def test_member_value_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Struct layout member shape must be a shape-castable object, not 1\.0$"):
            data.StructLayout({"a": 1.0})

    def test_format(self):
        sl = data.StructLayout({
            "a": unsigned(1),
            "b": signed(2),
        })
        sig = Signal(sl)
        self.assertRepr(sl.format(sig, ""), """
        (format-struct (sig sig)
            ('a' (format '{}' (slice (sig sig) 0:1)))
            ('b' (format '{}' (s (slice (sig sig) 1:3))))
        )
        """)


class UnionLayoutTestCase(FHDLTestCase):
    def test_construct(self):
        ul = data.UnionLayout({
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(ul.members, {
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(ul.size, 2)
        self.assertEqual(list(iter(ul)), [
            ("a", data.Field(unsigned(1), 0)),
            ("b", data.Field(2, 0))
        ])
        self.assertEqual(ul["a"], data.Field(unsigned(1), 0))
        self.assertEqual(ul["b"], data.Field(2, 0))

    def test_size_empty(self):
        self.assertEqual(data.UnionLayout({}).size, 0)

    def test_eq(self):
        self.assertEqual(data.UnionLayout({"a": unsigned(1), "b": 2}),
                         data.UnionLayout({"a": unsigned(1), "b": unsigned(2)}))
        self.assertEqual(data.UnionLayout({"a": unsigned(1), "b": 2}),
                         data.UnionLayout({"b": unsigned(2), "a": unsigned(1)}))
        self.assertNotEqual(data.UnionLayout({"a": unsigned(1), "b": 2}),
                            data.UnionLayout({"a": unsigned(1)}))

    def test_repr(self):
        ul = data.UnionLayout({
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(repr(ul), "UnionLayout({'a': unsigned(1), 'b': 2})")

    def test_members_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Union layout members must be provided as a mapping, not <.+>$"):
            data.UnionLayout(object())

    def test_member_key_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Union layout member name must be a string, not 1\.0$"):
            data.UnionLayout({1.0: unsigned(1)})

    def test_member_value_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Union layout member shape must be a shape-castable object, not 1\.0$"):
            data.UnionLayout({"a": 1.0})

    def test_const_two_members_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^Initializer for at most one field can be provided for a union layout "
                r"\(specified: a, b\)$"):
            data.UnionLayout({"a": 1, "b": 2}).const(dict(a=1, b=2))

    def test_format(self):
        ul = data.UnionLayout({
            "a": unsigned(1),
            "b": 2
        })
        sig = Signal(ul)
        self.assertRepr(ul.format(sig, ""), """
        (format-struct (sig sig)
            ('a' (format '{}' (slice (sig sig) 0:1)))
            ('b' (format '{}' (slice (sig sig) 0:2)))
        )
        """)


class ArrayLayoutTestCase(FHDLTestCase):
    def test_construct(self):
        al = data.ArrayLayout(unsigned(2), 3)
        self.assertEqual(al.elem_shape, unsigned(2))
        self.assertEqual(al.length, 3)
        self.assertEqual(list(iter(al)), [
            (0, data.Field(unsigned(2), 0)),
            (1, data.Field(unsigned(2), 2)),
            (2, data.Field(unsigned(2), 4)),
        ])
        self.assertEqual(al[0], data.Field(unsigned(2), 0))
        self.assertEqual(al[1], data.Field(unsigned(2), 2))
        self.assertEqual(al[2], data.Field(unsigned(2), 4))
        self.assertEqual(al[-1], data.Field(unsigned(2), 4))
        self.assertEqual(al[-2], data.Field(unsigned(2), 2))
        self.assertEqual(al[-3], data.Field(unsigned(2), 0))
        self.assertEqual(al.size, 6)

    def test_shape_castable(self):
        al = data.ArrayLayout(2, 3)
        self.assertEqual(al.size, 6)

    def test_eq(self):
        self.assertEqual(data.ArrayLayout(unsigned(2), 3),
                         data.ArrayLayout(unsigned(2), 3))
        self.assertNotEqual(data.ArrayLayout(unsigned(2), 3),
                            data.ArrayLayout(unsigned(2), 4))

    def test_repr(self):
        al = data.ArrayLayout(unsigned(2), 3)
        self.assertEqual(repr(al), "ArrayLayout(unsigned(2), 3)")

    def test_elem_shape_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Array layout element shape must be a shape-castable object, not <.+>$"):
            data.ArrayLayout(object(), 1)

    def test_length_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Array layout length must be a non-negative integer, not <.+>$"):
            data.ArrayLayout(unsigned(1), object())
        with self.assertRaisesRegex(TypeError,
                r"^Array layout length must be a non-negative integer, not -1$"):
            data.ArrayLayout(unsigned(1), -1)

    def test_key_wrong_bounds(self):
        al = data.ArrayLayout(unsigned(2), 3)
        with self.assertRaisesRegex(KeyError, r"^4$"):
            al[4]
        with self.assertRaisesRegex(KeyError, r"^-4$"):
            al[-4]

    def test_key_wrong_type(self):
        al = data.ArrayLayout(unsigned(2), 3)
        with self.assertRaisesRegex(TypeError,
                r"^Cannot index array layout with 'a'$"):
            al["a"]

    def test_format(self):
        al = data.ArrayLayout(unsigned(2), 3)
        sig = Signal(al)
        self.assertRepr(al.format(sig, ""), """
        (format-array (sig sig)
            (format '{}' (slice (sig sig) 0:2))
            (format '{}' (slice (sig sig) 2:4))
            (format '{}' (slice (sig sig) 4:6))
        )
        """)

    def test_format_signed(self):
        al = data.ArrayLayout(signed(2), 3)
        sig = Signal(al)
        self.assertRepr(al.format(sig, ""), """
        (format-array (sig sig)
            (format '{}' (s (slice (sig sig) 0:2)))
            (format '{}' (s (slice (sig sig) 2:4)))
            (format '{}' (s (slice (sig sig) 4:6)))
        )
        """)

    def test_format_nested(self):
        al = data.ArrayLayout(data.ArrayLayout(unsigned(2), 2), 3)
        sig = Signal(al)
        self.assertRepr(al.format(sig, ""), """
        (format-array (sig sig)
            (format-array (slice (sig sig) 0:4)
                (format '{}' (slice (slice (sig sig) 0:4) 0:2))
                (format '{}' (slice (slice (sig sig) 0:4) 2:4))
            )
            (format-array (slice (sig sig) 4:8)
                (format '{}' (slice (slice (sig sig) 4:8) 0:2))
                (format '{}' (slice (slice (sig sig) 4:8) 2:4))
            )
            (format-array (slice (sig sig) 8:12)
                (format '{}' (slice (slice (sig sig) 8:12) 0:2))
                (format '{}' (slice (slice (sig sig) 8:12) 2:4))
            )
        )
        """)


class FlexibleLayoutTestCase(TestCase):
    def test_construct(self):
        il = data.FlexibleLayout(8, {
            "a": data.Field(unsigned(1), 1),
            "b": data.Field(unsigned(3), 0),
            0: data.Field(unsigned(2), 5)
        })
        self.assertEqual(il.size, 8)
        self.assertEqual(il.fields, {
            "a": data.Field(unsigned(1), 1),
            "b": data.Field(unsigned(3), 0),
            0: data.Field(unsigned(2), 5)
        })
        self.assertEqual(list(iter(il)), [
            ("a", data.Field(unsigned(1), 1)),
            ("b", data.Field(unsigned(3), 0)),
            (0, data.Field(unsigned(2), 5))
        ])
        self.assertEqual(il["a"], data.Field(unsigned(1), 1))
        self.assertEqual(il["b"], data.Field(unsigned(3), 0))
        self.assertEqual(il[0], data.Field(unsigned(2), 5))

    def test_is_not_mutated(self):
        il = data.FlexibleLayout(8, {"a": data.Field(unsigned(1), 0)})
        del il.fields["a"]
        self.assertIn("a", il.fields)

    def test_eq(self):
        self.assertEqual(data.FlexibleLayout(3, {"a": data.Field(unsigned(1), 0)}),
                         data.FlexibleLayout(3, {"a": data.Field(unsigned(1), 0)}))
        self.assertNotEqual(data.FlexibleLayout(3, {"a": data.Field(unsigned(1), 0)}),
                            data.FlexibleLayout(4, {"a": data.Field(unsigned(1), 0)}))
        self.assertNotEqual(data.FlexibleLayout(3, {"a": data.Field(unsigned(1), 0)}),
                            data.FlexibleLayout(3, {"a": data.Field(unsigned(1), 1)}))

    def test_eq_duck(self):
        self.assertEqual(data.FlexibleLayout(3, {"a": data.Field(unsigned(1), 0),
                                             "b": data.Field(unsigned(2), 1)}),
                         data.StructLayout({"a": unsigned(1),
                                       "b": unsigned(2)}))
        self.assertEqual(data.FlexibleLayout(2, {"a": data.Field(unsigned(1), 0),
                                             "b": data.Field(unsigned(2), 0)}),
                         data.UnionLayout({"a": unsigned(1),
                                      "b": unsigned(2)}))

    def test_repr(self):
        il = data.FlexibleLayout(8, {
            "a": data.Field(unsigned(1), 1),
            "b": data.Field(unsigned(3), 0),
            0: data.Field(unsigned(2), 5)
        })
        self.assertEqual(repr(il), "FlexibleLayout(8, {"
            "'a': Field(unsigned(1), 1), "
            "'b': Field(unsigned(3), 0), "
            "0: Field(unsigned(2), 5)})")

    def test_fields_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout fields must be provided as a mapping, not <.+>$"):
            data.FlexibleLayout(8, object())

    def test_field_key_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout field name must be a non-negative integer or a string, "
                r"not 1\.0$"):
            data.FlexibleLayout(8, {1.0: unsigned(1)})
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout field name must be a non-negative integer or a string, "
                r"not -1$"):
            data.FlexibleLayout(8, {-1: unsigned(1)})

    def test_field_value_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout field value must be a Field instance, not 1\.0$"):
            data.FlexibleLayout(8, {"a": 1.0})

    def test_size_wrong_negative(self):
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout size must be a non-negative integer, not -1$"):
            data.FlexibleLayout(-1, {})

    def test_size_wrong_small(self):
        with self.assertRaisesRegex(ValueError,
                r"^Flexible layout field 'a' ends at bit 8, exceeding the size of 4 bit\(s\)$"):
            data.FlexibleLayout(4, {"a": data.Field(unsigned(8), 0)})
        with self.assertRaisesRegex(ValueError,
                r"^Flexible layout field 'a' ends at bit 5, exceeding the size of 4 bit\(s\)$"):
            data.FlexibleLayout(4, {"a": data.Field(unsigned(2), 3)})

    def test_key_wrong_missing(self):
        il = data.FlexibleLayout(8, {"a": data.Field(unsigned(2), 3)})
        with self.assertRaisesRegex(KeyError,
                r"^0$"):
            il[0]

    def test_key_wrong_type(self):
        il = data.FlexibleLayout(8, {"a": data.Field(unsigned(2), 3)})
        with self.assertRaisesRegex(TypeError,
                r"^Cannot index flexible layout with <.+>$"):
            il[object()]


class LayoutTestCase(FHDLTestCase):
    def test_cast(self):
        sl = data.StructLayout({})
        self.assertIs(data.Layout.cast(sl), sl)

    def test_cast_wrong_not_layout(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object unsigned\(1\) cannot be converted to a data layout$"):
            data.Layout.cast(unsigned(1))

    def test_cast_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object <.+> cannot be converted to an Amaranth shape$"):
            data.Layout.cast(object())

    def test_cast_wrong_recur(self):
        sc = MockShapeCastable(None)
        sc.shape = sc
        with self.assertRaisesRegex(RecursionError,
                r"^Shape-castable object <.+> casts to itself$"):
            data.Layout.cast(sc)

    def test_eq_wrong_recur(self):
        sc = MockShapeCastable(None)
        sc.shape = sc
        self.assertNotEqual(data.StructLayout({}), sc)

    def test_call(self):
        sl = data.StructLayout({"f": unsigned(1)})
        s = Signal(1)
        v = sl(s)
        self.assertIs(v.shape(), sl)
        self.assertIs(v.as_value(), s)

    def test_const(self):
        sl = data.StructLayout({
            "a": unsigned(1),
            "b": unsigned(2)
        })
        self.assertRepr(sl.const(None).as_value(), "(const 3'd0)")
        self.assertRepr(sl.const({"a": 0b1, "b": 0b10}).as_value(), "(const 3'd5)")
        self.assertRepr(sl.const(sl.const({"a": 0b1, "b": 0b10})).as_value(), "(const 3'd5)")

        fl = data.FlexibleLayout(2, {
            "a": data.Field(unsigned(1), 0),
            "b": data.Field(unsigned(2), 0)
        })
        self.assertRepr(fl.const({"a": 0b11}).as_value(), "(const 2'd1)")
        self.assertRepr(fl.const({"b": 0b10}).as_value(), "(const 2'd2)")
        self.assertRepr(fl.const({"a": 0b1, "b": 0b10}).as_value(), "(const 2'd2)")

        sls = data.StructLayout({
            "a": signed(4),
            "b": signed(4)
        })
        self.assertRepr(sls.const({"b": 0, "a": -1}).as_value(), "(const 8'd15)")

    def test_const_wrong(self):
        sl = data.StructLayout({"f": unsigned(1)})
        with self.assertRaisesRegex(TypeError,
                r"^Layout constant initializer must be a mapping or a sequence, not "
                r"<.+?object.+?>$"):
            sl.const(object())
        sl2 = data.StructLayout({"f": unsigned(2)})
        with self.assertRaisesRegex(ValueError,
                r"^Const layout StructLayout.* differs from shape layout StructLayout.*$"):
            sl2.const(sl.const({}))

    def test_const_field_shape_castable(self):
        class CastableFromHex(ShapeCastable):
            def as_shape(self):
                return unsigned(8)

            def __call__(self, value):
                return value

            def const(self, init):
                return int(init, 16)

            def from_bits(self, bits):
                return bits

        sl = data.StructLayout({"f": CastableFromHex()})
        self.assertRepr(sl.const({"f": "aa"}).as_value(), "(const 8'd170)")

        with self.assertRaisesRegex(ValueError,
                r"^Constant returned by <.+?CastableFromHex.+?>\.const\(\) must have the shape "
                r"that it casts to, unsigned\(8\), and not unsigned\(1\)$"):
            sl.const({"f": "01"})

    def test_const_field_const(self):
        sl = data.StructLayout({"f": unsigned(1)})
        self.assertRepr(sl.const({"f": Const(1)}).as_value(), "(const 1'd1)")

    def test_signal_init(self):
        sl = data.StructLayout({
            "a": unsigned(1),
            "b": unsigned(2)
        })
        self.assertEqual(Signal(sl).as_value().init, 0)
        self.assertEqual(Signal(sl, init={"a": 0b1, "b": 0b10}).as_value().init, 5)


class ViewTestCase(FHDLTestCase):
    def test_construct(self):
        s = Signal(3)
        v = data.View(data.StructLayout({"a": unsigned(1), "b": unsigned(2)}), s)
        self.assertIs(Value.cast(v), s)
        self.assertRepr(v["a"], "(slice (sig s) 0:1)")
        self.assertRepr(v["b"], "(slice (sig s) 1:3)")

    def test_construct_signal(self):
        v = Signal(data.StructLayout({"a": unsigned(1), "b": unsigned(2)}))
        cv = Value.cast(v)
        self.assertIsInstance(cv, Signal)
        self.assertEqual(cv.shape(), unsigned(3))
        self.assertEqual(cv.name, "v")
        self.assertRepr(cv._value_repr, """
        (Repr(FormatInt(), (sig v), ()),
            Repr(FormatInt(), (slice (sig v) 0:1), ('a',)),
            Repr(FormatInt(), (slice (sig v) 1:3), ('b',)))
        """)

    def test_construct_signal_init(self):
        v1 = Signal(data.StructLayout({"a": unsigned(1), "b": unsigned(2)}),
                   init={"a": 0b1, "b": 0b10})
        self.assertEqual(Value.cast(v1).init, 0b101)
        v2 = Signal(data.StructLayout({"a": unsigned(1),
                                "b": data.StructLayout({"x": unsigned(1), "y": unsigned(1)})}),
                   init={"a": 0b1, "b": {"x": 0b0, "y": 0b1}})
        self.assertEqual(Value.cast(v2).init, 0b101)
        v3 = Signal(data.ArrayLayout(unsigned(2), 2),
                   init=[0b01, 0b10])
        self.assertEqual(Value.cast(v3).init, 0b1001)

    def test_layout_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Layout of a view must be a Layout, not <.+?>$"):
            data.View(object(), Signal(1))

    def test_layout_conflict_with_attr(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Layout of a view includes a field 'as_value' that will be shadowed by "
                r"the attribute 'amaranth\.lib\.data\.View\.as_value'$"):
            data.View(data.StructLayout({"as_value": unsigned(1)}), Signal(1))

    def test_layout_conflict_with_attr_derived(self):
        class DerivedView(data.View):
            def foo(self):
                pass
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Layout of a view includes a field 'foo' that will be shadowed by "
                r"the attribute 'tests\.test_lib_data\.ViewTestCase\."
                r"test_layout_conflict_with_attr_derived\.<locals>.DerivedView\.foo'$"):
            DerivedView(data.StructLayout({"foo": unsigned(1)}), Signal(1))

    def test_target_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"^Target of a view must be a value-castable object, not <.+?>$"):
            data.View(data.StructLayout({}), object())

    def test_target_wrong_size(self):
        with self.assertRaisesRegex(ValueError,
                r"^Target of a view is 2 bit\(s\) wide, which is not compatible with its 1 bit\(s\) "
                r"wide layout$"):
            data.View(data.StructLayout({"a": unsigned(1)}), Signal(2))

    def test_getitem(self):
        v = Signal(data.UnionLayout({
            "a": unsigned(2),
            "s": data.StructLayout({
                "b": unsigned(1),
                "c": unsigned(3)
            }),
            "p": 1,
            "q": signed(1),
            "r": data.ArrayLayout(unsigned(2), 2),
            "t": data.ArrayLayout(data.StructLayout({
                "u": unsigned(1),
                "v": unsigned(1)
            }), 2),
        }))
        cv = Value.cast(v)
        i = Signal(1)
        self.assertEqual(cv.shape(), unsigned(4))
        self.assertRepr(v["a"], "(slice (sig v) 0:2)")
        self.assertEqual(v["a"].shape(), unsigned(2))
        self.assertRepr(v["s"]["b"], "(slice (slice (sig v) 0:4) 0:1)")
        self.assertRepr(v["s"]["c"], "(slice (slice (sig v) 0:4) 1:4)")
        self.assertRepr(v["p"], "(slice (sig v) 0:1)")
        self.assertEqual(v["p"].shape(), unsigned(1))
        self.assertRepr(v["q"], "(s (slice (sig v) 0:1))")
        self.assertEqual(v["q"].shape(), signed(1))
        self.assertRepr(v["r"][0], "(slice (slice (sig v) 0:4) 0:2)")
        self.assertRepr(v["r"][1], "(slice (slice (sig v) 0:4) 2:4)")
        self.assertRepr(v["r"][i], "(part (slice (sig v) 0:4) (sig i) 2 2)")
        self.assertRepr(v["t"][0]["u"], "(slice (slice (slice (sig v) 0:4) 0:2) 0:1)")
        self.assertRepr(v["t"][1]["v"], "(slice (slice (slice (sig v) 0:4) 2:4) 1:2)")

    def test_getitem_custom_call(self):
        class Reverser(ShapeCastable):
            def as_shape(self):
                return unsigned(2)

            def __call__(self, value):
                return value[::-1]

            def const(self, init):
                return Const(init, 2)

            def from_bits(self, bits):
                return bits

        v = Signal(data.StructLayout({
            "f": Reverser()
        }))
        self.assertRepr(v.f, "(cat (slice (slice (sig v) 0:2) 1:2) "
                             "     (slice (slice (sig v) 0:2) 0:1))")

    def test_getitem_custom_call_wrong(self):
        class WrongCastable(ShapeCastable):
            def as_shape(self):
                return unsigned(2)

            def __call__(self, value):
                pass

            def const(self, init):
                return Const(init, 2)

            def from_bits(self, bits):
                return bits

            def format(self, value, spec):
                return Format("")

        v = Signal(data.StructLayout({
            "f": WrongCastable()
        }))
        with self.assertRaisesRegex(TypeError,
                r"^<.+?\.WrongCastable.+?>\.__call__\(\) must return a value or a value-castable "
                r"object, not None$"):
            v.f

    def test_index_wrong_missing(self):
        with self.assertRaisesRegex(KeyError,
                r"^'a'$"):
            Signal(data.StructLayout({}))["a"]

    def test_index_wrong_struct_dynamic(self):
        with self.assertRaisesRegex(TypeError,
                r"^Only views with array layout, not StructLayout\(\{\}\), may be indexed "
                r"with a value$"):
            Signal(data.StructLayout({}))[Signal(1)]

    def test_getattr(self):
        v = Signal(data.UnionLayout({
            "a": unsigned(2),
            "s": data.StructLayout({
                "b": unsigned(1),
                "c": unsigned(3)
            }),
            "p": 1,
            "q": signed(1),
        }))
        cv = Value.cast(v)
        i = Signal(1)
        self.assertEqual(cv.shape(), unsigned(4))
        self.assertRepr(v.a, "(slice (sig v) 0:2)")
        self.assertEqual(v.a.shape(), unsigned(2))
        self.assertRepr(v.s.b, "(slice (slice (sig v) 0:4) 0:1)")
        self.assertRepr(v.s.c, "(slice (slice (sig v) 0:4) 1:4)")
        self.assertRepr(v.p, "(slice (sig v) 0:1)")
        self.assertEqual(v.p.shape(), unsigned(1))
        self.assertRepr(v.q, "(s (slice (sig v) 0:1))")
        self.assertEqual(v.q.shape(), signed(1))

    def test_getattr_reserved(self):
        v = Signal(data.UnionLayout({
            "_a": unsigned(2)
        }))
        self.assertRepr(v["_a"], "(slice (sig v) 0:2)")

    def test_attr_wrong_missing(self):
        with self.assertRaisesRegex(AttributeError,
                r"^View with layout .* does not have a field 'a'; did you mean one of: 'b', 'c'\?$"):
            Signal(data.StructLayout({"b": unsigned(1), "c": signed(1)})).a

    def test_attr_wrong_reserved(self):
        with self.assertRaisesRegex(AttributeError,
                r"^Field '_c' of view with layout .* has a reserved name and may only be accessed "
                r"by indexing$"):
            Signal(data.StructLayout({"_c": signed(1)}))._c

    def test_signal_like(self):
        s1 = Signal(data.StructLayout({"a": unsigned(1)}))
        s2 = Signal.like(s1)
        self.assertEqual(s2.shape(), data.StructLayout({"a": unsigned(1)}))
        s3 = Signal.like(s1, name_suffix="a")
        self.assertEqual(s3.as_value().name, "s1a")

        s4 = Signal(data.StructLayout({"a": unsigned(2), "b": unsigned(3)}), init={"a": 1}, reset_less=True, attrs={"x": "y"})
        s5 = Signal.like(s4)
        self.assertEqual(s5.as_value().init, 0b00001)
        self.assertEqual(s5.as_value().reset_less, True)
        self.assertEqual(s5.as_value().attrs, {"x": "y"})


    def test_bug_837_array_layout_getitem_str(self):
        with self.assertRaisesRegex(TypeError,
                r"^View with array layout may only be indexed with an integer or a value, "
                r"not 'init'$"):
            Signal(data.ArrayLayout(unsigned(1), 1), init=[0])["init"]

    def test_bug_837_array_layout_getattr(self):
        with self.assertRaisesRegex(AttributeError,
                r"^View with an array layout does not have fields$"):
            Signal(data.ArrayLayout(unsigned(1), 1), init=[0]).init

    def test_eq(self):
        s1 = Signal(data.StructLayout({"a": unsigned(2)}))
        s2 = Signal(data.StructLayout({"a": unsigned(2)}))
        s3 = Signal(data.StructLayout({"a": unsigned(1), "b": unsigned(1)}))
        self.assertRepr(s1 == s2, "(== (sig s1) (sig s2))")
        self.assertRepr(s1 != s2, "(!= (sig s1) (sig s2))")
        with self.assertRaisesRegex(TypeError,
                r"^View with layout .* can only be compared to another view or constant "
                r"with the same layout, not .*$"):
            s1 == s3
        with self.assertRaisesRegex(TypeError,
                r"^View with layout .* can only be compared to another view or constant "
                r"with the same layout, not .*$"):
            s1 != s3
        with self.assertRaisesRegex(TypeError,
                r"^View with layout .* can only be compared to another view or constant "
                r"with the same layout, not .*$"):
            s1 == Const(0, 2)
        with self.assertRaisesRegex(TypeError,
                r"^View with layout .* can only be compared to another view or constant "
                r"with the same layout, not .*$"):
            s1 != Const(0, 2)

    def test_operator(self):
        s1 = Signal(data.StructLayout({"a": unsigned(2)}))
        s2 = Signal(unsigned(2))
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
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot perform arithmetic operations on a View$"):
                op(s1, s2)
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot perform arithmetic operations on a View$"):
                op(s2, s1)
        for op in [
            operator.__and__,
            operator.__or__,
            operator.__xor__,
        ]:
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot perform bitwise operations on a View$"):
                op(s1, s2)
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot perform bitwise operations on a View$"):
                op(s2, s1)

    def test_repr(self):
        s1 = Signal(data.StructLayout({"a": unsigned(2)}))
        self.assertRepr(s1, "View(StructLayout({'a': unsigned(2)}), (sig s1))")


class ConstTestCase(FHDLTestCase):
    def test_construct(self):
        c = data.Const(data.StructLayout({"a": unsigned(1), "b": unsigned(2)}), 5)
        self.assertRepr(Value.cast(c), "(const 3'd5)")
        self.assertEqual(c.shape(), data.StructLayout({"a": unsigned(1), "b": unsigned(2)}))
        self.assertEqual(c.as_bits(), 5)
        self.assertEqual(c["a"], 1)
        self.assertEqual(c["b"], 2)

    def test_construct_const(self):
        c = Const({"a": 1, "b": 2}, data.StructLayout({"a": unsigned(1), "b": unsigned(2)}))
        self.assertRepr(Const.cast(c), "(const 3'd5)")
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, 2)

    def test_layout_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Layout of a constant must be a Layout, not <.+?>$"):
            data.Const(object(), 1)

    def test_layout_conflict_with_attr(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Layout of a constant includes a field 'as_value' that will be shadowed by "
                r"the attribute 'amaranth\.lib\.data\.Const\.as_value'$"):
            data.Const(data.StructLayout({"as_value": unsigned(1)}), 1)

    def test_layout_conflict_with_attr_derived(self):
        class DerivedConst(data.Const):
            def foo(self):
                pass
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Layout of a constant includes a field 'foo' that will be shadowed by "
                r"the attribute 'tests\.test_lib_data\.ConstTestCase\."
                r"test_layout_conflict_with_attr_derived\.<locals>.DerivedConst\.foo'$"):
            DerivedConst(data.StructLayout({"foo": unsigned(1)}), 1)

    def test_target_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"^Target of a constant must be an int, not <.+?>$"):
            data.Const(data.StructLayout({}), object())

    def test_target_wrong_value(self):
        with self.assertRaisesRegex(ValueError,
                r"^Target of a constant does not fit in 1 bit\(s\)$"):
            data.Const(data.StructLayout({"a": unsigned(1)}), 2)

    def test_getitem(self):
        l = data.StructLayout({
            "u": unsigned(1),
            "v": unsigned(1)
        })
        v = data.Const(data.StructLayout({
            "a": unsigned(2),
            "s": data.StructLayout({
                "b": unsigned(1),
                "c": unsigned(3)
            }),
            "p": 1,
            "q": signed(1),
            "r": data.ArrayLayout(unsigned(2), 2),
            "t": data.ArrayLayout(data.StructLayout({
                "u": unsigned(1),
                "v": unsigned(1)
            }), 2),
        }), 0xabcd)
        cv = Value.cast(v)
        i = Signal(1)
        self.assertEqual(cv.shape(), unsigned(16))
        self.assertEqual(v["a"], 1)
        self.assertEqual(v["s"]["b"], 1)
        self.assertEqual(v["s"]["c"], 1)
        self.assertEqual(v["p"], 1)
        self.assertEqual(v["q"], -1)
        self.assertEqual(v["r"][0], 3)
        self.assertEqual(v["r"][1], 2)
        self.assertRepr(v["r"][i], "(part (const 4'd11) (sig i) 2 2)")
        self.assertEqual(v["t"][0], data.Const(l, 2))
        self.assertEqual(v["t"][1], data.Const(l, 2))
        self.assertEqual(v["t"][0]["u"], 0)
        self.assertEqual(v["t"][1]["v"], 1)

    def test_getitem_custom_call(self):
        class Reverser(ShapeCastable):
            def as_shape(self):
                return unsigned(2)

            def __call__(self, value):
                raise NotImplementedError

            def const(self, init):
                raise NotImplementedError

            def from_bits(self, bits):
                return float(bits) / 2

        v = data.Const(data.StructLayout({
            "f": Reverser()
        }), 3)
        self.assertEqual(v.f, 1.5)

    def test_index_wrong_missing(self):
        with self.assertRaisesRegex(KeyError,
                r"^'a'$"):
            data.Const(data.StructLayout({}), 0)["a"]

    def test_index_wrong_struct_dynamic(self):
        with self.assertRaisesRegex(TypeError,
                r"^Only constants with array layout, not StructLayout\(\{\}\), may be indexed "
                r"with a value$"):
            data.Const(data.StructLayout({}), 0)[Signal(1)]

    def test_getattr(self):
        v = data.Const(data.UnionLayout({
            "a": unsigned(2),
            "s": data.StructLayout({
                "b": unsigned(1),
                "c": unsigned(3)
            }),
            "p": 1,
            "q": signed(1),
        }), 13)
        cv = Const.cast(v)
        i = Signal(1)
        self.assertEqual(cv.shape(), unsigned(4))
        self.assertEqual(v.a, 1)
        self.assertEqual(v.s.b, 1)
        self.assertEqual(v.s.c, 6)
        self.assertEqual(v.p, 1)
        self.assertEqual(v.q, -1)

    def test_getattr_reserved(self):
        v = data.Const(data.UnionLayout({
            "_a": unsigned(2)
        }), 2)
        self.assertEqual(v["_a"], 2)

    def test_attr_wrong_missing(self):
        with self.assertRaisesRegex(AttributeError,
                r"^Constant with layout .* does not have a field 'a'; did you mean one of: "
                r"'b', 'c'\?$"):
            data.Const(data.StructLayout({"b": unsigned(1), "c": signed(1)}), 0).a

    def test_attr_wrong_reserved(self):
        with self.assertRaisesRegex(AttributeError,
                r"^Field '_c' of constant with layout .* has a reserved name and may only be "
                r"accessed by indexing$"):
            data.Const(data.StructLayout({"_c": signed(1)}), 0)._c

    def test_bug_837_array_layout_getitem_str(self):
        with self.assertRaisesRegex(TypeError,
                r"^Constant with array layout may only be indexed with an integer or a value, "
                r"not 'init'$"):
            data.Const(data.ArrayLayout(unsigned(1), 1), 0)["init"]

    def test_bug_837_array_layout_getattr(self):
        with self.assertRaisesRegex(AttributeError,
                r"^Constant with an array layout does not have fields$"):
            data.Const(data.ArrayLayout(unsigned(1), 1), 0).init

    def test_eq(self):
        c1 = data.Const(data.StructLayout({"a": unsigned(2)}), 1)
        c2 = data.Const(data.StructLayout({"a": unsigned(2)}), 1)
        c3 = data.Const(data.StructLayout({"a": unsigned(2)}), 2)
        c4 = data.Const(data.StructLayout({"a": unsigned(1), "b": unsigned(1)}), 2)
        s1 = Signal(data.StructLayout({"a": unsigned(2)}))
        self.assertTrue(c1 == c2)
        self.assertFalse(c1 != c2)
        self.assertFalse(c1 == c3)
        self.assertTrue(c1 != c3)
        self.assertRepr(c1 == s1, "(== (const 2'd1) (sig s1))")
        self.assertRepr(c1 != s1, "(!= (const 2'd1) (sig s1))")
        self.assertRepr(s1 == c1, "(== (sig s1) (const 2'd1))")
        self.assertRepr(s1 != c1, "(!= (sig s1) (const 2'd1))")
        with self.assertRaisesRegex(TypeError,
                r"^Constant with layout .* can only be compared to another view or constant with "
                r"the same layout, not .*$"):
            c1 == c4
        with self.assertRaisesRegex(TypeError,
                r"^Constant with layout .* can only be compared to another view or constant with "
                r"the same layout, not .*$"):
            c1 != c4
        with self.assertRaisesRegex(TypeError,
                r"^View with layout .* can only be compared to another view or constant with "
                r"the same layout, not .*$"):
            s1 == c4
        with self.assertRaisesRegex(TypeError,
                r"^View with layout .* can only be compared to another view or constant with "
                r"the same layout, not .*$"):
            s1 != c4
        with self.assertRaisesRegex(TypeError,
                r"^Constant with layout .* can only be compared to another view or constant with "
                r"the same layout, not .*$"):
            c4 == s1
        with self.assertRaisesRegex(TypeError,
                r"^Constant with layout .* can only be compared to another view or constant with "
                r"the same layout, not .*$"):
            c4 != s1
        with self.assertRaisesRegex(TypeError,
                r"^Constant with layout .* can only be compared to another view or constant with "
                r"the same layout, not .*$"):
            c1 == Const(0, 2)
        with self.assertRaisesRegex(TypeError,
                r"^Constant with layout .* can only be compared to another view or constant with "
                r"the same layout, not .*$"):
            c1 != Const(0, 2)

    def test_operator(self):
        s1 = data.Const(data.StructLayout({"a": unsigned(2)}), 2)
        s2 = Signal(unsigned(2))
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
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot perform arithmetic operations on a lib.data.Const$"):
                op(s1, s2)
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot perform arithmetic operations on a lib.data.Const$"):
                op(s2, s1)
        for op in [
            operator.__and__,
            operator.__or__,
            operator.__xor__,
        ]:
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot perform bitwise operations on a lib.data.Const$"):
                op(s1, s2)
            with self.assertRaisesRegex(TypeError,
                    r"^Cannot perform bitwise operations on a lib.data.Const$"):
                op(s2, s1)

    def test_repr(self):
        s1 = data.Const(data.StructLayout({"a": unsigned(2)}), 2)
        self.assertRepr(s1, "Const(StructLayout({'a': unsigned(2)}), 2)")


class StructTestCase(FHDLTestCase):
    def test_construct(self):
        class S(data.Struct):
            a: unsigned(1)
            b: signed(3)

        self.assertEqual(Shape.cast(S), unsigned(4))
        self.assertEqual(data.Layout.cast(S), data.StructLayout({
            "a": unsigned(1),
            "b": signed(3)
        }))

        v = Signal(S)
        self.assertEqual(v.shape(), S)
        self.assertEqual(Value.cast(v).shape(), Shape.cast(S))
        self.assertEqual(Value.cast(v).name, "v")
        self.assertRepr(v.a, "(slice (sig v) 0:1)")
        self.assertRepr(v.b, "(s (slice (sig v) 1:4))")

    def test_construct_nested(self):
        Q = data.StructLayout({"r": signed(2), "s": signed(2)})

        class R(data.Struct):
            p: 4
            q: Q

        class S(data.Struct):
            a: unsigned(1)
            b: R

        self.assertEqual(Shape.cast(S), unsigned(9))

        v = Signal(S)
        self.assertIs(v.shape(), S)
        self.assertIsInstance(v, S)
        self.assertIs(v.b.shape(), R)
        self.assertIsInstance(v.b, R)
        self.assertIs(v.b.q.shape(), Q)
        self.assertIsInstance(v.b.q, data.View)
        self.assertRepr(v.b.p, "(slice (slice (sig v) 1:9) 0:4)")
        self.assertRepr(v.b.q.as_value(), "(slice (slice (sig v) 1:9) 4:8)")
        self.assertRepr(v.b.q.r, "(s (slice (slice (slice (sig v) 1:9) 4:8) 0:2))")
        self.assertRepr(v.b.q.s, "(s (slice (slice (slice (sig v) 1:9) 4:8) 2:4))")
        self.assertRepr(S.format(v, ""), """
        (format-struct (sig v)
            ('a' (format '{}' (slice (sig v) 0:1)))
            ('b' (format-struct (slice (sig v) 1:9)
                ('p' (format '{}' (slice (slice (sig v) 1:9) 0:4)))
                ('q' (format-struct (slice (slice (sig v) 1:9) 4:8)
                    ('r' (format '{}' (s (slice (slice (slice (sig v) 1:9) 4:8) 0:2))))
                    ('s' (format '{}' (s (slice (slice (slice (sig v) 1:9) 4:8) 2:4))))
                ))
            ))
        )
        """)

    def test_construct_init(self):
        class S(data.Struct):
            p: 4
            q: 2 = 1

        with self.assertRaises(AttributeError):
            S.q

        v1 = Signal(S)
        self.assertEqual(v1.as_value().init, 0b010000)
        v2 = Signal(S, init=dict(p=0b0011))
        self.assertEqual(v2.as_value().init, 0b010011)
        v3 = Signal(S, init=dict(p=0b0011, q=0b00))
        self.assertEqual(v3.as_value().init, 0b000011)
        v3 = Signal(S, init=S.const({"p": 0b0011, "q": 0b00}))
        self.assertEqual(v3.as_value().init, 0b000011)

    def test_const_wrong(self):
        class S(data.Struct):
            p: 4
            q: 2 = 1

        class S2(data.Struct):
            p: 2
            q: 4

        with self.assertRaisesRegex(ValueError,
                f"^Const layout StructLayout.* differs from shape layout StructLayout.*$"):
            S.const(S2.const({"p": 0b11, "q": 0b0000}))

    def test_shape_undefined_wrong(self):
        class S(data.Struct):
            pass

        with self.assertRaisesRegex(TypeError,
                r"^Aggregate class '.+?\.S' does not have a defined shape$"):
            Shape.cast(S)

    def test_base_class_1(self):
        class Sb(data.Struct):
            def add(self):
                return self.a + self.b

        class Sb1(Sb):
            a: 1
            b: 1

        class Sb2(Sb):
            a: 2
            b: 2

        self.assertEqual(Signal(Sb1).add().shape(), unsigned(2))
        self.assertEqual(Signal(Sb2).add().shape(), unsigned(3))

    def test_base_class_2(self):
        class Sb(data.Struct):
            a: 2
            b: 2

        class Sb1(Sb):
            def do(self):
                return Cat(self.a, self.b)

        class Sb2(Sb):
            def do(self):
                return self.a + self.b

        self.assertEqual(Signal(Sb1).do().shape(), unsigned(4))
        self.assertEqual(Signal(Sb2).do().shape(), unsigned(3))

    def test_layout_redefined_wrong(self):
        class Sb(data.Struct):
            a: 1

        with self.assertRaisesRegex(TypeError,
                r"^Aggregate class 'Sd' must either inherit or specify a layout, not both$"):
            class Sd(Sb):
                b: 1

    def test_typing_annotation_coexistence(self):
        class S(data.Struct):
            a: unsigned(1)
            b: int
            c: str = "x"

        self.assertEqual(data.Layout.cast(S), data.StructLayout({"a": unsigned(1)}))
        self.assertEqual(S.__annotations__, {"b": int, "c": str})
        self.assertEqual(S.c, "x")

    def test_signal_like(self):
        class S(data.Struct):
            a: 1
        s1 = Signal(S)
        s2 = Signal.like(s1)
        self.assertEqual(s2.shape(), S)

    def test_from_bits(self):
        class S(data.Struct):
            a: 1
        c = S.from_bits(1)
        self.assertIsInstance(c, data.Const)
        self.assertEqual(c.a, 1)


class UnionTestCase(FHDLTestCase):
    def test_construct(self):
        class U(data.Union):
            a: unsigned(1)
            b: signed(3)

        self.assertEqual(Shape.cast(U), unsigned(3))
        self.assertEqual(data.Layout.cast(U), data.UnionLayout({
            "a": unsigned(1),
            "b": signed(3)
        }))

        v = Signal(U)
        self.assertEqual(v.shape(), U)
        self.assertEqual(Value.cast(v).shape(), Shape.cast(U))
        self.assertRepr(v.a, "(slice (sig v) 0:1)")
        self.assertRepr(v.b, "(s (slice (sig v) 0:3))")

    def test_define_init_two_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^Initial value for at most one field can be provided for a union class "
                r"\(specified: a, b\)$"):
            class U(data.Union):
                a: unsigned(1) = 1
                b: unsigned(2) = 1

    def test_construct_init_two_wrong(self):
        class U(data.Union):
            a: unsigned(1)
            b: unsigned(2)

        with self.assertRaisesRegex(TypeError,
                r"^Initial value must be a constant initializer of <class '.+?\.U'>$") as cm:
            Signal(U, init=dict(a=1, b=2))
            self.assertRegex(cm.exception.__cause__.message,
                             r"^Initializer for at most one field can be provided for a union "
                             r"class \(specified: a, b\)$")

    def test_construct_init_override(self):
        class U(data.Union):
            a: unsigned(1) = 1
            b: unsigned(2)

        self.assertEqual(Signal(U).as_value().init, 0b01)
        self.assertEqual(Signal(U, init=dict(b=0b10)).as_value().init, 0b10)


# Examples from https://github.com/amaranth-lang/amaranth/issues/693
class RFCExamplesTestCase(TestCase):
    @staticmethod
    def simulate(m):
        def wrapper(fn):
            sim = Simulator(m)
            sim.add_testbench(fn)
            sim.run()
        return wrapper

    def test_rfc_example_1(self):
        class Float32(data.Struct):
            fraction: unsigned(23)
            exponent: unsigned(8)
            sign: unsigned(1)

        self.assertEqual(Float32.as_shape().size, 32)

        flt_a = Float32(Signal(32))
        flt_b = Float32(Const(0b00111110001000000000000000000000, 32))

        m1 = Module()
        with m1.If(flt_b.fraction > 0):
            m1.d.comb += [
                flt_a.sign.eq(1),
                flt_a.exponent.eq(127)
            ]

        @self.simulate(m1)
        def check_m1():
            self.assertEqual((yield flt_a.as_value()), 0xbf800000)

        class FloatOrInt32(data.Union):
            float: Float32
            int: signed(32)

        f_or_i = Signal(FloatOrInt32)
        is_gt_1 = Signal()
        m2 = Module()
        m2.d.comb += [
            f_or_i.int.eq(0x41C80000),
            is_gt_1.eq(f_or_i.float.exponent >= 127) # => 1
        ]

        @self.simulate(m2)
        def check_m2():
            self.assertEqual((yield is_gt_1), 1)

        class Op(Enum):
          ADD = 0
          SUB = 1

        adder_op_layout = data.StructLayout({
            "op": Op,
            "a": Float32,
            "b": Float32
        })

        adder_op = Signal(adder_op_layout)
        self.assertEqual(len(adder_op.as_value()), 65)

        m3 = Module()
        m3.d.comb += [
            adder_op.eq(Op.SUB),
            adder_op.a.eq(flt_a),
            adder_op.b.eq(flt_b)
        ]

        @self.simulate(m3)
        def check_m3():
            self.assertEqual((yield adder_op.as_value()), 0x7c40000000000001)

    def test_rfc_example_2(self):
        class Kind(Enum):
            ONE_SIGNED = 0
            TWO_UNSIGNED = 1

        layout1 = data.StructLayout({
            "kind": Kind,
            "value": data.UnionLayout({
                "one_signed": signed(2),
                "two_unsigned": data.ArrayLayout(unsigned(1), 2)
            })
        })
        self.assertEqual(layout1.size, 3)

        view1 = Signal(layout1)
        self.assertIsInstance(view1, data.View)
        self.assertEqual(view1.shape(), layout1)
        self.assertEqual(view1.as_value().shape(), unsigned(3))

        m1 = Module()
        m1.d.comb += [
            view1.kind.eq(Kind.TWO_UNSIGNED),
            view1.value.two_unsigned[0].eq(1),
        ]

        @self.simulate(m1)
        def check_m1():
            self.assertEqual((yield view1.as_value()), 0b011)

        class SomeVariant(data.Struct):
            class Value(data.Union):
                one_signed: signed(2)
                two_unsigned: data.ArrayLayout(unsigned(1), 2)

            kind: Kind
            value: Value

        self.assertEqual(Shape.cast(SomeVariant), unsigned(3))

        view2 = Signal(SomeVariant)
        self.assertIsInstance(Value.cast(view2), Signal)
        self.assertEqual(Value.cast(view2).shape(), unsigned(3))

        m2 = Module()
        m2.submodules += m1
        m2.d.comb += [
            view2.kind.eq(Kind.ONE_SIGNED),
            view2.value.eq(view1.value)
        ]

        @self.simulate(m2)
        def check_m2():
            self.assertEqual((yield view2.as_value()), 0b010)

        layout2 = data.StructLayout({
            "ready": unsigned(1),
            "payload": SomeVariant
        })
        self.assertEqual(layout2.size, 4)

        self.assertEqual(layout1, data.Layout.cast(SomeVariant))

        self.assertIs(SomeVariant, view2.shape())
