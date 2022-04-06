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

    def test_size_wrong_shrink(self):
        il = FlexibleLayout(8, {"a": Field(unsigned(2), 3)})
        with self.assertRaisesRegex(ValueError,
                r"^Flexible layout size 4 does not cover the field 'a', which ends at bit 5$"):
            il.size = 4

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


class LayoutTestCase(TestCase):
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

    def test_of_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object <.+> is not a data view$"):
            Layout.of(object())

    def test_eq_wrong_recur(self):
        sc = MockShapeCastable(None)
        sc.shape = sc
        self.assertNotEqual(StructLayout({}), sc)


class ViewTestCase(FHDLTestCase):
    def test_construct(self):
        s = Signal(3)
        v = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}), s)
        self.assertIs(Value.cast(v), s)
        self.assertRepr(v["a"], "(slice (sig s) 0:1)")
        self.assertRepr(v["b"], "(slice (sig s) 1:3)")

    def test_construct_signal(self):
        v = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}))
        cv = Value.cast(v)
        self.assertIsInstance(cv, Signal)
        self.assertEqual(cv.shape(), unsigned(3))
        self.assertEqual(cv.name, "v")

    def test_construct_signal_name(self):
        v = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}), name="named")
        self.assertEqual(Value.cast(v).name, "named")

    def test_construct_signal_reset(self):
        v1 = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}),
                  reset={"a": 0b1, "b": 0b10})
        self.assertEqual(Value.cast(v1).reset, 0b101)
        v2 = View(StructLayout({"a": unsigned(1),
                                "b": StructLayout({"x": unsigned(1), "y": unsigned(1)})}),
                  reset={"a": 0b1, "b": {"x": 0b0, "y": 0b1}})
        self.assertEqual(Value.cast(v2).reset, 0b101)
        v3 = View(ArrayLayout(unsigned(2), 2),
                  reset=[0b01, 0b10])
        self.assertEqual(Value.cast(v3).reset, 0b1001)

    def test_construct_signal_reset_less(self):
        v = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}), reset_less=True)
        self.assertEqual(Value.cast(v).reset_less, True)

    def test_construct_signal_attrs(self):
        v = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}), attrs={"debug": 1})
        self.assertEqual(Value.cast(v).attrs, {"debug": 1})

    def test_construct_signal_decoder(self):
        decoder = lambda x: f"{x}"
        v = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}), decoder=decoder)
        self.assertEqual(Value.cast(v).decoder, decoder)

    def test_layout_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^View layout must be a Layout instance, not <.+?>$"):
            View(object(), Signal(1))

    def test_target_wrong_type(self):
        with self.assertRaisesRegex(TypeError,
                r"^View target must be a value-castable object, not <.+?>$"):
            View(StructLayout({}), object())

    def test_target_wrong_size(self):
        with self.assertRaisesRegex(ValueError,
                r"^View target is 2 bit\(s\) wide, which is not compatible with the 1 bit\(s\) "
                r"wide view layout$"):
            View(StructLayout({"a": unsigned(1)}), Signal(2))

    def test_signal_reset_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Layout initializer must be a mapping or a sequence, not 1$"):
            View(StructLayout({}), reset=0b1)

    def test_target_signal_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^View target cannot be provided at the same time as any of the Signal "
                r"constructor arguments \(name, reset, reset_less, attrs, decoder\)$"):
            View(StructLayout({}), Signal(), reset=0b1)

    def test_getitem(self):
        v = View(UnionLayout({
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

    def test_index_wrong_missing(self):
        with self.assertRaisesRegex(KeyError,
                r"^'a'$"):
            View(StructLayout({}))["a"]

    def test_index_wrong_struct_dynamic(self):
        with self.assertRaisesRegex(TypeError,
                r"^Only views with array layout, not StructLayout\(\{\}\), may be indexed "
                r"with a value$"):
            View(StructLayout({}))[Signal(1)]

    def test_getattr(self):
        v = View(UnionLayout({
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
        v = View(UnionLayout({
            "_a": unsigned(2)
        }))
        self.assertRepr(v["_a"], "(slice (sig v) 0:2)")

    def test_attr_wrong_missing(self):
        with self.assertRaisesRegex(AttributeError,
                r"^View of \(sig \$signal\) does not have a field 'a'; "
                r"did you mean one of: 'b', 'c'\?$"):
            View(StructLayout({"b": unsigned(1), "c": signed(1)})).a

    def test_attr_wrong_reserved(self):
        with self.assertRaisesRegex(AttributeError,
                r"^View of \(sig \$signal\) field '_c' has a reserved name "
                r"and may only be accessed by indexing$"):
            View(StructLayout({"_c": signed(1)}))._c


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

        v = S()
        self.assertEqual(Layout.of(v), S)
        self.assertEqual(Value.cast(v).shape(), S)
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

        self.assertEqual(S, unsigned(9))

        v = S()
        self.assertIs(Layout.of(v), S)
        self.assertIsInstance(v, S)
        self.assertIs(Layout.of(v.b), R)
        self.assertIsInstance(v.b, R)
        self.assertIs(Layout.of(v.b.q), Q)
        self.assertIsInstance(v.b.q, View)
        self.assertRepr(v.b.p, "(slice (slice (sig v) 1:9) 0:4)")
        self.assertRepr(v.b.q.as_value(), "(slice (slice (sig v) 1:9) 4:8)")
        self.assertRepr(v.b.q.r, "(s (slice (slice (slice (sig v) 1:9) 4:8) 0:2))")
        self.assertRepr(v.b.q.s, "(s (slice (slice (slice (sig v) 1:9) 4:8) 2:4))")

    def test_construct_signal_kwargs(self):
        decoder = lambda x: f"{x}"
        v = View(StructLayout({"a": unsigned(1), "b": unsigned(2)}),
            name="named", reset={"b": 0b1}, reset_less=True, attrs={"debug": 1}, decoder=decoder)
        s = Value.cast(v)
        self.assertEqual(s.name, "named")
        self.assertEqual(s.reset, 0b010)
        self.assertEqual(s.reset_less, True)
        self.assertEqual(s.attrs, {"debug": 1})
        self.assertEqual(s.decoder, decoder)


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

        v = U()
        self.assertEqual(Layout.of(v), U)
        self.assertEqual(Value.cast(v).shape(), U)
        self.assertRepr(v.a, "(slice (sig v) 0:1)")
        self.assertRepr(v.b, "(s (slice (sig v) 0:3))")

    def test_construct_signal_kwargs(self):
        decoder = lambda x: f"{x}"
        v = View(UnionLayout({"a": unsigned(1), "b": unsigned(2)}),
            name="named", reset={"b": 0b1}, reset_less=True, attrs={"debug": 1}, decoder=decoder)
        s = Value.cast(v)
        self.assertEqual(s.name, "named")
        self.assertEqual(s.reset, 0b01)
        self.assertEqual(s.reset_less, True)
        self.assertEqual(s.attrs, {"debug": 1})
        self.assertEqual(s.decoder, decoder)


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

        flt_a = Float32()
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

        f_or_i = FloatOrInt32()
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

        adder_op_storage = Signal(adder_op_layout)
        self.assertEqual(len(adder_op_storage), 65)

        adder_op = View(adder_op_layout, adder_op_storage)
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

        sig1 = Signal(layout1)
        self.assertEqual(sig1.shape(), unsigned(3))

        view1 = View(layout1, sig1)
        self.assertIs(Value.cast(view1), sig1)

        view2 = View(layout1)
        self.assertIsInstance(Value.cast(view2), Signal)
        self.assertEqual(Value.cast(view2).shape(), unsigned(3))

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

        self.assertEqual(SomeVariant, unsigned(3))

        view3 = SomeVariant()
        self.assertIsInstance(Value.cast(view3), Signal)
        self.assertEqual(Value.cast(view3).shape(), unsigned(3))

        m2 = Module()
        m2.submodules += m1
        m2.d.comb += [
            view3.kind.eq(Kind.ONE_SIGNED),
            view3.value.eq(view1.value)
        ]

        @self.simulate(m2)
        def check_m2():
            self.assertEqual((yield view3.as_value()), 0b010)

        sig2 = Signal(SomeVariant)
        self.assertEqual(sig2.shape(), unsigned(3))

        layout2 = StructLayout({
            "ready": unsigned(1),
            "payload": SomeVariant
        })
        self.assertEqual(layout2.size, 4)

        self.assertEqual(layout1, Layout.cast(SomeVariant))

        self.assertIs(SomeVariant, Layout.of(view3))

    def test_rfc_example_3(self):
        class Stream8b10b(View):
            data: Signal
            ctrl: Signal

            def __init__(self, value=None, *, width: int):
                super().__init__(StructLayout({
                    "data": unsigned(8 * width),
                    "ctrl": unsigned(width)
                }), value)

        self.assertEqual(len(Stream8b10b(width=1).data), 8)
        self.assertEqual(len(Stream8b10b(width=4).data), 32)
