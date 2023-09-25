from enum import Enum
from unittest import TestCase

from amaranth.hdl import *
from amaranth.hdl.ast import ShapeCastable
from amaranth.lib.data import *
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


class FieldTestCase(TestCase):
    def test_construct(self):
        f = Field(unsigned(2), 1)
        self.assertEqual(f.shape, unsigned(2))
        self.assertEqual(f.offset, 1)
        self.assertEqual(f.width, 2)

    def test_repr(self):
        f = Field(unsigned(2), 1)
        self.assertEqual(repr(f), "Field(unsigned(2), 1)")

    def test_equal(self):
        f1 = Field(unsigned(2), 1)
        f2 = Field(unsigned(2), 0)
        self.assertNotEqual(f1, f2)
        f3 = Field(unsigned(2), 1)
        self.assertEqual(f1, f3)
        f4 = Field(2, 1)
        self.assertEqual(f1, f4)
        f5 = Field(MockShapeCastable(unsigned(2)), 1)
        self.assertEqual(f1, f5)
        self.assertNotEqual(f1, object())

    def test_preserve_shape(self):
        sc = MockShapeCastable(unsigned(2))
        f = Field(sc, 0)
        self.assertEqual(f.shape, sc)
        self.assertEqual(f.width, 2)

    def test_shape_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Field shape must be a shape-castable object, not <.+>$"):
            Field(object(), 0)

    def test_offset_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Field offset must be a non-negative integer, not <.+>$"):
            Field(unsigned(2), object())
        with self.assertRaisesRegex(TypeError,
                r"^Field offset must be a non-negative integer, not -1$"):
            Field(unsigned(2), -1)

    def test_immutable(self):
        with self.assertRaises(AttributeError):
            Field(1, 0).shape = unsigned(2)
        with self.assertRaises(AttributeError):
            Field(1, 0).offset = 1


class StructLayoutTestCase(TestCase):
    def test_construct(self):
        sl = StructLayout({
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(sl.members, {
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(sl.size, 3)
        self.assertEqual(list(iter(sl)), [
            ("a", Field(unsigned(1), 0)),
            ("b", Field(2, 1))
        ])
        self.assertEqual(sl["a"], Field(unsigned(1), 0))
        self.assertEqual(sl["b"], Field(2, 1))

    def test_size_empty(self):
        self.assertEqual(StructLayout({}).size, 0)

    def test_eq(self):
        self.assertEqual(StructLayout({"a": unsigned(1), "b": 2}),
                         StructLayout({"a": unsigned(1), "b": unsigned(2)}))
        self.assertNotEqual(StructLayout({"a": unsigned(1), "b": 2}),
                            StructLayout({"b": unsigned(2), "a": unsigned(1)}))
        self.assertNotEqual(StructLayout({"a": unsigned(1), "b": 2}),
                            StructLayout({"a": unsigned(1)}))

    def test_repr(self):
        sl = StructLayout({
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(repr(sl), "StructLayout({'a': unsigned(1), 'b': 2})")

    def test_members_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Struct layout members must be provided as a mapping, not <.+>$"):
            StructLayout(object())

    def test_member_key_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Struct layout member name must be a string, not 1\.0$"):
            StructLayout({1.0: unsigned(1)})

    def test_member_value_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Struct layout member shape must be a shape-castable object, not 1\.0$"):
            StructLayout({"a": 1.0})


class UnionLayoutTestCase(TestCase):
    def test_construct(self):
        ul = UnionLayout({
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(ul.members, {
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(ul.size, 2)
        self.assertEqual(list(iter(ul)), [
            ("a", Field(unsigned(1), 0)),
            ("b", Field(2, 0))
        ])
        self.assertEqual(ul["a"], Field(unsigned(1), 0))
        self.assertEqual(ul["b"], Field(2, 0))

    def test_size_empty(self):
        self.assertEqual(UnionLayout({}).size, 0)

    def test_eq(self):
        self.assertEqual(UnionLayout({"a": unsigned(1), "b": 2}),
                         UnionLayout({"a": unsigned(1), "b": unsigned(2)}))
        self.assertEqual(UnionLayout({"a": unsigned(1), "b": 2}),
                         UnionLayout({"b": unsigned(2), "a": unsigned(1)}))
        self.assertNotEqual(UnionLayout({"a": unsigned(1), "b": 2}),
                            UnionLayout({"a": unsigned(1)}))

    def test_repr(self):
        ul = UnionLayout({
            "a": unsigned(1),
            "b": 2
        })
        self.assertEqual(repr(ul), "UnionLayout({'a': unsigned(1), 'b': 2})")

    def test_members_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Union layout members must be provided as a mapping, not <.+>$"):
            UnionLayout(object())

    def test_member_key_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Union layout member name must be a string, not 1\.0$"):
            UnionLayout({1.0: unsigned(1)})

    def test_member_value_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Union layout member shape must be a shape-castable object, not 1\.0$"):
            UnionLayout({"a": 1.0})

    def test_const_two_members_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^Initializer for at most one field can be provided for a union layout "
                r"\(specified: a, b\)$"):
            UnionLayout({"a": 1, "b": 2}).const(dict(a=1, b=2))


class ArrayLayoutTestCase(TestCase):
    def test_construct(self):
        al = ArrayLayout(unsigned(2), 3)
        self.assertEqual(al.elem_shape, unsigned(2))
        self.assertEqual(al.length, 3)
        self.assertEqual(list(iter(al)), [
            (0, Field(unsigned(2), 0)),
            (1, Field(unsigned(2), 2)),
            (2, Field(unsigned(2), 4)),
        ])
        self.assertEqual(al[0], Field(unsigned(2), 0))
        self.assertEqual(al[1], Field(unsigned(2), 2))
        self.assertEqual(al[2], Field(unsigned(2), 4))
        self.assertEqual(al[-1], Field(unsigned(2), 4))
        self.assertEqual(al[-2], Field(unsigned(2), 2))
        self.assertEqual(al[-3], Field(unsigned(2), 0))
        self.assertEqual(al.size, 6)

    def test_shape_castable(self):
        al = ArrayLayout(2, 3)
        self.assertEqual(al.size, 6)

    def test_eq(self):
        self.assertEqual(ArrayLayout(unsigned(2), 3),
                         ArrayLayout(unsigned(2), 3))
        self.assertNotEqual(ArrayLayout(unsigned(2), 3),
                            ArrayLayout(unsigned(2), 4))

    def test_repr(self):
        al = ArrayLayout(unsigned(2), 3)
        self.assertEqual(repr(al), "ArrayLayout(unsigned(2), 3)")

    def test_elem_shape_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Array layout element shape must be a shape-castable object, not <.+>$"):
            ArrayLayout(object(), 1)

    def test_length_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Array layout length must be a non-negative integer, not <.+>$"):
            ArrayLayout(unsigned(1), object())
        with self.assertRaisesRegex(TypeError,
                r"^Array layout length must be a non-negative integer, not -1$"):
            ArrayLayout(unsigned(1), -1)

    def test_key_wrong_bounds(self):
        al = ArrayLayout(unsigned(2), 3)
        with self.assertRaisesRegex(KeyError, r"^4$"):
            al[4]
        with self.assertRaisesRegex(KeyError, r"^-4$"):
            al[-4]

    def test_key_wrong_type(self):
        al = ArrayLayout(unsigned(2), 3)
        with self.assertRaisesRegex(TypeError,
                r"^Cannot index array layout with 'a'$"):
            al["a"]


class FlexibleLayoutTestCase(TestCase):
    def test_construct(self):
        il = FlexibleLayout(8, {
            "a": Field(unsigned(1), 1),
            "b": Field(unsigned(3), 0),
            0: Field(unsigned(2), 5)
        })
        self.assertEqual(il.size, 8)
        self.assertEqual(il.fields, {
            "a": Field(unsigned(1), 1),
            "b": Field(unsigned(3), 0),
            0: Field(unsigned(2), 5)
        })
        self.assertEqual(list(iter(il)), [
            ("a", Field(unsigned(1), 1)),
            ("b", Field(unsigned(3), 0)),
            (0, Field(unsigned(2), 5))
        ])
        self.assertEqual(il["a"], Field(unsigned(1), 1))
        self.assertEqual(il["b"], Field(unsigned(3), 0))
        self.assertEqual(il[0], Field(unsigned(2), 5))

    def test_is_not_mutated(self):
        il = FlexibleLayout(8, {"a": Field(unsigned(1), 0)})
        del il.fields["a"]
        self.assertIn("a", il.fields)

    def test_eq(self):
        self.assertEqual(FlexibleLayout(3, {"a": Field(unsigned(1), 0)}),
                         FlexibleLayout(3, {"a": Field(unsigned(1), 0)}))
        self.assertNotEqual(FlexibleLayout(3, {"a": Field(unsigned(1), 0)}),
                            FlexibleLayout(4, {"a": Field(unsigned(1), 0)}))
        self.assertNotEqual(FlexibleLayout(3, {"a": Field(unsigned(1), 0)}),
                            FlexibleLayout(3, {"a": Field(unsigned(1), 1)}))

    def test_eq_duck(self):
        self.assertEqual(FlexibleLayout(3, {"a": Field(unsigned(1), 0),
                                             "b": Field(unsigned(2), 1)}),
                         StructLayout({"a": unsigned(1),
                                       "b": unsigned(2)}))
        self.assertEqual(FlexibleLayout(2, {"a": Field(unsigned(1), 0),
                                             "b": Field(unsigned(2), 0)}),
                         UnionLayout({"a": unsigned(1),
                                      "b": unsigned(2)}))

    def test_repr(self):
        il = FlexibleLayout(8, {
            "a": Field(unsigned(1), 1),
            "b": Field(unsigned(3), 0),
            0: Field(unsigned(2), 5)
        })
        self.assertEqual(repr(il), "FlexibleLayout(8, {"
            "'a': Field(unsigned(1), 1), "
            "'b': Field(unsigned(3), 0), "
            "0: Field(unsigned(2), 5)})")

    def test_fields_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout fields must be provided as a mapping, not <.+>$"):
            FlexibleLayout(8, object())

    def test_field_key_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout field name must be a non-negative integer or a string, "
                r"not 1\.0$"):
            FlexibleLayout(8, {1.0: unsigned(1)})
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout field name must be a non-negative integer or a string, "
                r"not -1$"):
            FlexibleLayout(8, {-1: unsigned(1)})

    def test_field_value_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout field value must be a Field instance, not 1\.0$"):
            FlexibleLayout(8, {"a": 1.0})

    def test_size_wrong_negative(self):
        with self.assertRaisesRegex(TypeError,
                r"^Flexible layout size must be a non-negative integer, not -1$"):
            FlexibleLayout(-1, {})

    def test_size_wrong_small(self):
        with self.assertRaisesRegex(ValueError,
                r"^Flexible layout field 'a' ends at bit 8, exceeding the size of 4 bit\(s\)$"):
            FlexibleLayout(4, {"a": Field(unsigned(8), 0)})
        with self.assertRaisesRegex(ValueError,
                r"^Flexible layout field 'a' ends at bit 5, exceeding the size of 4 bit\(s\)$"):
            FlexibleLayout(4, {"a": Field(unsigned(2), 3)})

    def test_key_wrong_missing(self):
        il = FlexibleLayout(8, {"a": Field(unsigned(2), 3)})
        with self.assertRaisesRegex(KeyError,
                r"^0$"):
            il[0]

    def test_key_wrong_type(self):
        il = FlexibleLayout(8, {"a": Field(unsigned(2), 3)})
        with self.assertRaisesRegex(TypeError,
                r"^Cannot index flexible layout with <.+>$"):
            il[object()]


class LayoutTestCase(FHDLTestCase):
    def test_cast(self):
        sl = StructLayout({})
        self.assertIs(Layout.cast(sl), sl)

    def test_cast_wrong_not_layout(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object unsigned\(1\) cannot be converted to a data layout$"):
            Layout.cast(unsigned(1))

    def test_cast_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object <.+> cannot be converted to an Amaranth shape$"):
            Layout.cast(object())

    def test_cast_wrong_recur(self):
        sc = MockShapeCastable(None)
        sc.shape = sc
        with self.assertRaisesRegex(RecursionError,
                r"^Shape-castable object <.+> casts to itself$"):
            Layout.cast(sc)

    def test_eq_wrong_recur(self):
        sc = MockShapeCastable(None)
        sc.shape = sc
        self.assertNotEqual(StructLayout({}), sc)

    def test_call(self):
        sl = StructLayout({"f": unsigned(1)})
        s = Signal(1)
        v = sl(s)
        self.assertIs(v.shape(), sl)
        self.assertIs(v.as_value(), s)

    def test_const(self):
        sl = StructLayout({
            "a": unsigned(1),
            "b": unsigned(2)
        })
        self.assertRepr(sl.const(None), "(const 3'd0)")
        self.assertRepr(sl.const({"a": 0b1, "b": 0b10}), "(const 3'd5)")

        fl = FlexibleLayout(2, {
            "a": Field(unsigned(1), 0),
            "b": Field(unsigned(2), 0)
        })
        self.assertRepr(fl.const({"a": 0b11}), "(const 2'd1)")
        self.assertRepr(fl.const({"b": 0b10}), "(const 2'd2)")
        self.assertRepr(fl.const({"a": 0b1, "b": 0b10}), "(const 2'd2)")

        sls = StructLayout({
            "a": signed(4),
            "b": signed(4)
        })
        self.assertRepr(sls.const({"b": 0, "a": -1}), "(const 8'd15)")

    def test_const_wrong(self):
        sl = StructLayout({"f": unsigned(1)})
        with self.assertRaisesRegex(TypeError,
                r"^Layout constant initializer must be a mapping or a sequence, not "
                r"<.+?object.+?>$"):
            sl.const(object())

    def test_const_field_shape_castable(self):
        class CastableFromHex(ShapeCastable):
            def as_shape(self):
                return unsigned(8)

            def __call__(self, value):
                return value

            def const(self, init):
                return int(init, 16)

        sl = StructLayout({"f": CastableFromHex()})
        self.assertRepr(sl.const({"f": "aa"}), "(const 8'd170)")

        with self.assertRaisesRegex(ValueError,
                r"^Constant returned by <.+?CastableFromHex.+?>\.const\(\) must have the shape "
                r"that it casts to, unsigned\(8\), and not unsigned\(1\)$"):
            sl.const({"f": "01"})

    def test_const_field_const(self):
        sl = StructLayout({"f": unsigned(1)})
        self.assertRepr(sl.const({"f": Const(1)}), "(const 1'd1)")

    def test_signal_reset(self):
        sl = StructLayout({
            "a": unsigned(1),
            "b": unsigned(2)
        })
        self.assertEqual(Signal(sl).as_value().reset, 0)
        self.assertEqual(Signal(sl, reset={"a": 0b1, "b": 0b10}).as_value().reset, 5)


class ViewTestCase(FHDLTestCase):
    def test_construct(self):
        s = Signal(3)
        v = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}), s)
        self.assertIs(Value.cast(v), s)
        self.assertRepr(v["a"], "(slice (sig s) 0:1)")
        self.assertRepr(v["b"], "(slice (sig s) 1:3)")

    def test_construct_signal(self):
        v = Signal(StructLayout({"a": unsigned(1), "b": unsigned(2)}))
        cv = Value.cast(v)
        self.assertIsInstance(cv, Signal)
        self.assertEqual(cv.shape(), unsigned(3))
        self.assertEqual(cv.name, "v")

    def test_construct_signal_reset(self):
        v1 = Signal(StructLayout({"a": unsigned(1), "b": unsigned(2)}),
                   reset={"a": 0b1, "b": 0b10})
        self.assertEqual(Value.cast(v1).reset, 0b101)
        v2 = Signal(StructLayout({"a": unsigned(1),
                                "b": StructLayout({"x": unsigned(1), "y": unsigned(1)})}),
                   reset={"a": 0b1, "b": {"x": 0b0, "y": 0b1}})
        self.assertEqual(Value.cast(v2).reset, 0b101)
        v3 = Signal(ArrayLayout(unsigned(2), 2),
                   reset=[0b01, 0b10])
        self.assertEqual(Value.cast(v3).reset, 0b1001)

    def test_layout_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^View layout must be a layout, not <.+?>$"):
            View(object(), Signal(1))

    def test_layout_conflict_with_attr(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^View layout includes a field 'as_value' that will be shadowed by the view "
                r"attribute 'amaranth\.lib\.data\.View\.as_value'$"):
            View(StructLayout({"as_value": unsigned(1)}), Signal(1))

    def test_layout_conflict_with_attr_derived(self):
        class DerivedView(View):
            def foo(self):
                pass
        with self.assertWarnsRegex(SyntaxWarning,
                r"^View layout includes a field 'foo' that will be shadowed by the view "
                r"attribute 'tests\.test_lib_data\.ViewTestCase\."
                r"test_layout_conflict_with_attr_derived\.<locals>.DerivedView\.foo'$"):
            DerivedView(StructLayout({"foo": unsigned(1)}), Signal(1))

    def test_target_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"^View target must be a value-castable object, not <.+?>$"):
            View(StructLayout({}), object())

    def test_target_wrong_size(self):
        with self.assertRaisesRegex(ValueError,
                r"^View target is 2 bit\(s\) wide, which is not compatible with the 1 bit\(s\) "
                r"wide view layout$"):
            View(StructLayout({"a": unsigned(1)}), Signal(2))

    def test_getitem(self):
        v = Signal(UnionLayout({
            "a": unsigned(2),
            "s": StructLayout({
                "b": unsigned(1),
                "c": unsigned(3)
            }),
            "p": 1,
            "q": signed(1),
            "r": ArrayLayout(unsigned(2), 2),
            "t": ArrayLayout(StructLayout({
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

        v = Signal(StructLayout({
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

        v = Signal(StructLayout({
            "f": WrongCastable()
        }))
        with self.assertRaisesRegex(TypeError,
                r"^<.+?\.WrongCastable.+?>\.__call__\(\) must return a value or a value-castable "
                r"object, not None$"):
            v.f

    def test_index_wrong_missing(self):
        with self.assertRaisesRegex(KeyError,
                r"^'a'$"):
            Signal(StructLayout({}))["a"]

    def test_index_wrong_struct_dynamic(self):
        with self.assertRaisesRegex(TypeError,
                r"^Only views with array layout, not StructLayout\(\{\}\), may be indexed "
                r"with a value$"):
            Signal(StructLayout({}))[Signal(1)]

    def test_getattr(self):
        v = Signal(UnionLayout({
            "a": unsigned(2),
            "s": StructLayout({
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
        v = Signal(UnionLayout({
            "_a": unsigned(2)
        }))
        self.assertRepr(v["_a"], "(slice (sig v) 0:2)")

    def test_attr_wrong_missing(self):
        with self.assertRaisesRegex(AttributeError,
                r"^View of \(sig \$signal\) does not have a field 'a'; "
                r"did you mean one of: 'b', 'c'\?$"):
            Signal(StructLayout({"b": unsigned(1), "c": signed(1)})).a

    def test_attr_wrong_reserved(self):
        with self.assertRaisesRegex(AttributeError,
                r"^View of \(sig \$signal\) field '_c' has a reserved name "
                r"and may only be accessed by indexing$"):
            Signal(StructLayout({"_c": signed(1)}))._c

    def test_signal_like(self):
        s1 = Signal(StructLayout({"a": unsigned(1)}))
        s2 = Signal.like(s1)
        self.assertEqual(s2.shape(), StructLayout({"a": unsigned(1)}))

    def test_bug_837_array_layout_getitem_str(self):
        with self.assertRaisesRegex(TypeError,
                r"^Views with array layout may only be indexed with an integer or a value, "
                r"not 'reset'$"):
            Signal(ArrayLayout(unsigned(1), 1), reset=[0])["reset"]

    def test_bug_837_array_layout_getattr(self):
        with self.assertRaisesRegex(AttributeError,
                r"^View of \(sig \$signal\) with an array layout does not have fields$"):
            Signal(ArrayLayout(unsigned(1), 1), reset=[0]).reset


class StructTestCase(FHDLTestCase):
    def test_construct(self):
        class S(Struct):
            a: unsigned(1)
            b: signed(3)

        self.assertEqual(Shape.cast(S), unsigned(4))
        self.assertEqual(Layout.cast(S), StructLayout({
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
        Q = StructLayout({"r": signed(2), "s": signed(2)})

        class R(Struct):
            p: 4
            q: Q

        class S(Struct):
            a: unsigned(1)
            b: R

        self.assertEqual(Shape.cast(S), unsigned(9))

        v = Signal(S)
        self.assertIs(v.shape(), S)
        self.assertIsInstance(v, S)
        self.assertIs(v.b.shape(), R)
        self.assertIsInstance(v.b, R)
        self.assertIs(v.b.q.shape(), Q)
        self.assertIsInstance(v.b.q, View)
        self.assertRepr(v.b.p, "(slice (slice (sig v) 1:9) 0:4)")
        self.assertRepr(v.b.q.as_value(), "(slice (slice (sig v) 1:9) 4:8)")
        self.assertRepr(v.b.q.r, "(s (slice (slice (slice (sig v) 1:9) 4:8) 0:2))")
        self.assertRepr(v.b.q.s, "(s (slice (slice (slice (sig v) 1:9) 4:8) 2:4))")

    def test_construct_reset(self):
        class S(Struct):
            p: 4
            q: 2 = 1

        with self.assertRaises(AttributeError):
            S.q

        v1 = Signal(S)
        self.assertEqual(v1.as_value().reset, 0b010000)
        v2 = Signal(S, reset=dict(p=0b0011))
        self.assertEqual(v2.as_value().reset, 0b010011)
        v3 = Signal(S, reset=dict(p=0b0011, q=0b00))
        self.assertEqual(v3.as_value().reset, 0b000011)

    def test_shape_undefined_wrong(self):
        class S(Struct):
            pass

        with self.assertRaisesRegex(TypeError,
                r"^Aggregate class '.+?\.S' does not have a defined shape$"):
            Shape.cast(S)

    def test_base_class_1(self):
        class Sb(Struct):
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
        class Sb(Struct):
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
        class Sb(Struct):
            a: 1

        with self.assertRaisesRegex(TypeError,
                r"^Aggregate class 'Sd' must either inherit or specify a layout, not both$"):
            class Sd(Sb):
                b: 1

    def test_typing_annotation_coexistence(self):
        class S(Struct):
            a: unsigned(1)
            b: int
            c: str = "x"

        self.assertEqual(Layout.cast(S), StructLayout({"a": unsigned(1)}))
        self.assertEqual(S.__annotations__, {"b": int, "c": str})
        self.assertEqual(S.c, "x")

    def test_signal_like(self):
        class S(Struct):
            a: 1
        s1 = Signal(S)
        s2 = Signal.like(s1)
        self.assertEqual(s2.shape(), S)


class UnionTestCase(FHDLTestCase):
    def test_construct(self):
        class U(Union):
            a: unsigned(1)
            b: signed(3)

        self.assertEqual(Shape.cast(U), unsigned(3))
        self.assertEqual(Layout.cast(U), UnionLayout({
            "a": unsigned(1),
            "b": signed(3)
        }))

        v = Signal(U)
        self.assertEqual(v.shape(), U)
        self.assertEqual(Value.cast(v).shape(), Shape.cast(U))
        self.assertRepr(v.a, "(slice (sig v) 0:1)")
        self.assertRepr(v.b, "(s (slice (sig v) 0:3))")

    def test_define_reset_two_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^Reset value for at most one field can be provided for a union class "
                r"\(specified: a, b\)$"):
            class U(Union):
                a: unsigned(1) = 1
                b: unsigned(2) = 1

    def test_construct_reset_two_wrong(self):
        class U(Union):
            a: unsigned(1)
            b: unsigned(2)

        with self.assertRaisesRegex(TypeError,
                r"^Reset value must be a constant initializer of <class '.+?\.U'>$") as cm:
            Signal(U, reset=dict(a=1, b=2))
            self.assertRegex(cm.exception.__cause__.message,
                             r"^Initializer for at most one field can be provided for a union "
                             r"class \(specified: a, b\)$")

    def test_construct_reset_override(self):
        class U(Union):
            a: unsigned(1) = 1
            b: unsigned(2)

        self.assertEqual(Signal(U).as_value().reset, 0b01)
        self.assertEqual(Signal(U, reset=dict(b=0b10)).as_value().reset, 0b10)


# Examples from https://github.com/amaranth-lang/amaranth/issues/693
class RFCExamplesTestCase(TestCase):
    @staticmethod
    def simulate(m):
        def wrapper(fn):
            sim = Simulator(m)
            sim.add_process(fn)
            sim.run()
        return wrapper

    def test_rfc_example_1(self):
        class Float32(Struct):
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

        class FloatOrInt32(Union):
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

        adder_op_layout = StructLayout({
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

        layout1 = StructLayout({
            "kind": Kind,
            "value": UnionLayout({
                "one_signed": signed(2),
                "two_unsigned": ArrayLayout(unsigned(1), 2)
            })
        })
        self.assertEqual(layout1.size, 3)

        view1 = Signal(layout1)
        self.assertIsInstance(view1, View)
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

        class SomeVariant(Struct):
            class Value(Union):
                one_signed: signed(2)
                two_unsigned: ArrayLayout(unsigned(1), 2)

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

        layout2 = StructLayout({
            "ready": unsigned(1),
            "payload": SomeVariant
        })
        self.assertEqual(layout2.size, 4)

        self.assertEqual(layout1, Layout.cast(SomeVariant))

        self.assertIs(SomeVariant, view2.shape())
