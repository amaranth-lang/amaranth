from enum import Enum

from amaranth.hdl.ast import *
from amaranth.hdl.rec import *

from .utils import *


class UnsignedEnum(Enum):
    FOO = 1
    BAR = 2
    BAZ = 3


class LayoutTestCase(FHDLTestCase):
    def assertFieldEqual(self, field, expected):
        (shape, dir) = field
        shape = Shape.cast(shape)
        self.assertEqual((shape, dir), expected)

    def test_fields(self):
        layout = Layout.cast([
            ("cyc",  1),
            ("data", signed(32)),
            ("stb",  1, DIR_FANOUT),
            ("ack",  1, DIR_FANIN),
            ("info", [
                ("a", 1),
                ("b", 1),
            ])
        ])

        self.assertFieldEqual(layout["cyc"], ((1, False), DIR_NONE))
        self.assertFieldEqual(layout["data"], ((32, True), DIR_NONE))
        self.assertFieldEqual(layout["stb"], ((1, False), DIR_FANOUT))
        self.assertFieldEqual(layout["ack"], ((1, False), DIR_FANIN))
        sublayout = layout["info"][0]
        self.assertEqual(layout["info"][1], DIR_NONE)
        self.assertFieldEqual(sublayout["a"], ((1, False), DIR_NONE))
        self.assertFieldEqual(sublayout["b"], ((1, False), DIR_NONE))

    def test_enum_field(self):
        layout = Layout.cast([
            ("enum", UnsignedEnum),
            ("enum_dir", UnsignedEnum, DIR_FANOUT),
        ])
        self.assertFieldEqual(layout["enum"], ((2, False), DIR_NONE))
        self.assertFieldEqual(layout["enum_dir"], ((2, False), DIR_FANOUT))

    def test_range_field(self):
        layout = Layout.cast([
            ("range", range(0, 7)),
        ])
        self.assertFieldEqual(layout["range"], ((3, False), DIR_NONE))

    def test_slice_tuple(self):
        layout = Layout.cast([
            ("a", 1),
            ("b", 2),
            ("c", 3)
        ])
        expect = Layout.cast([
            ("a", 1),
            ("c", 3)
        ])
        self.assertEqual(layout["a", "c"], expect)

    def test_repr(self):
        self.assertEqual(repr(Layout([("a", unsigned(1)), ("b", signed(2))])),
                         "Layout([('a', unsigned(1)), ('b', signed(2))])")
        self.assertEqual(repr(Layout([("a", unsigned(1)), ("b", [("c", signed(3))])])),
                         "Layout([('a', unsigned(1)), "
                            "('b', Layout([('c', signed(3))]))])")

    def test_wrong_field(self):
        with self.assertRaisesRegex(TypeError,
                (r"^Field \(1,\) has invalid layout: should be either \(name, shape\) or "
                    r"\(name, shape, direction\)$")):
            Layout.cast([(1,)])

    def test_wrong_name(self):
        with self.assertRaisesRegex(TypeError,
                r"^Field \(1, 1\) has invalid name: should be a string$"):
            Layout.cast([(1, 1)])

    def test_wrong_name_duplicate(self):
        with self.assertRaisesRegex(NameError,
                r"^Field \('a', 2\) has a name that is already present in the layout$"):
            Layout.cast([("a", 1), ("a", 2)])

    def test_wrong_direction(self):
        with self.assertRaisesRegex(TypeError,
                (r"^Field \('a', 1, 0\) has invalid direction: should be a Direction "
                    r"instance like DIR_FANIN$")):
            Layout.cast([("a", 1, 0)])

    def test_wrong_shape(self):
        with self.assertRaisesRegex(TypeError,
                (r"^Field \('a', 'x'\) has invalid shape: should be castable to Shape or "
                    r"a list of fields of a nested record$")):
            Layout.cast([("a", "x")])


class RecordTestCase(FHDLTestCase):
    def test_basic(self):
        r = Record([
            ("stb",  1),
            ("data", 32),
            ("info", [
                ("a", 1),
                ("b", 1),
            ])
        ])

        self.assertEqual(repr(r), "(rec r stb data (rec r__info a b))")
        self.assertEqual(len(r),  35)
        self.assertIsInstance(r.stb, Signal)
        self.assertEqual(r.stb.name, "r__stb")
        self.assertEqual(r["stb"].name, "r__stb")

        self.assertTrue(hasattr(r, "stb"))
        self.assertFalse(hasattr(r, "xxx"))

    def test_unnamed(self):
        r = [Record([
            ("stb", 1)
        ])][0]

        self.assertEqual(repr(r), "(rec <unnamed> stb)")
        self.assertEqual(r.stb.name, "stb")

    def test_iter(self):
        r = Record([
            ("data", 4),
            ("stb",  1),
        ])

        self.assertEqual(repr(r[0]),   "(slice (cat (sig r__data) (sig r__stb)) 0:1)")
        self.assertEqual(repr(r[0:3]), "(slice (cat (sig r__data) (sig r__stb)) 0:3)")

    def test_wrong_field(self):
        r = Record([
            ("stb", 1),
            ("ack", 1),
        ])
        with self.assertRaisesRegex(AttributeError,
                r"^Record 'r' does not have a field 'en'\. Did you mean one of: stb, ack\?$"):
            r["en"]
        with self.assertRaisesRegex(AttributeError,
                r"^Record 'r' does not have a field 'en'\. Did you mean one of: stb, ack\?$"):
            r.en

    def test_wrong_field_unnamed(self):
        r = [Record([
            ("stb", 1),
            ("ack", 1),
        ])][0]
        with self.assertRaisesRegex(AttributeError,
                r"^Unnamed record does not have a field 'en'\. Did you mean one of: stb, ack\?$"):
            r.en

    def test_construct_with_fields(self):
        ns = Signal(1)
        nr = Record([
            ("burst", 1)
        ])
        r = Record([
            ("stb", 1),
            ("info", [
                ("burst", 1)
            ])
        ], fields={
            "stb":  ns,
            "info": nr
        })
        self.assertIs(r.stb, ns)
        self.assertIs(r.info, nr)

    def test_shape(self):
        r1 = Record([("a", 1), ("b", 2)])
        self.assertEqual(r1.shape(), unsigned(3))

    def test_like(self):
        r1 = Record([("a", 1), ("b", 2)])
        r2 = Record.like(r1)
        self.assertEqual(r1.layout, r2.layout)
        self.assertEqual(r2.name, "r2")
        r3 = Record.like(r1, name="foo")
        self.assertEqual(r3.name, "foo")
        r4 = Record.like(r1, name_suffix="foo")
        self.assertEqual(r4.name, "r1foo")

    def test_like_modifications(self):
        r1 = Record([("a", 1), ("b", [("s", 1)])])
        self.assertEqual(r1.a.name, "r1__a")
        self.assertEqual(r1.b.name, "r1__b")
        self.assertEqual(r1.b.s.name, "r1__b__s")
        r1.a.reset = 1
        r1.b.s.reset = 1
        r2 = Record.like(r1)
        self.assertEqual(r2.a.reset, 1)
        self.assertEqual(r2.b.s.reset, 1)
        self.assertEqual(r2.a.name, "r2__a")
        self.assertEqual(r2.b.name, "r2__b")
        self.assertEqual(r2.b.s.name, "r2__b__s")

    def test_slice_tuple(self):
        r1 = Record([("a", 1), ("b", 2), ("c", 3)])
        r2 = r1["a", "c"]
        self.assertEqual(r2.layout, Layout([("a", 1), ("c", 3)]))
        self.assertIs(r2.a, r1.a)
        self.assertIs(r2.c, r1.c)

    def test_enum_decoder(self):
        r1 = Record([("a", UnsignedEnum)])
        self.assertEqual(r1.a.decoder(UnsignedEnum.FOO), "FOO/1")

    def test_operators(self):
        r1 = Record([("a", 1)])
        s1 = Signal()

        # __bool__
        with self.assertRaisesRegex(TypeError,
                r"^Attempted to convert Amaranth value to Python boolean$"):
            not r1

        # __invert__, __neg__
        self.assertEqual(repr(~r1), "(~ (cat (sig r1__a)))")
        self.assertEqual(repr(-r1), "(- (cat (sig r1__a)))")

        # __add__, __radd__, __sub__, __rsub__
        self.assertEqual(repr(r1 + 1),  "(+ (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 + s1), "(+ (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 + r1),  "(+ (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 + r1), "(+ (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 - 1),  "(- (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 - s1), "(- (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 - r1),  "(- (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 - r1), "(- (sig s1) (cat (sig r1__a)))")

        # __mul__, __rmul__
        self.assertEqual(repr(r1 * 1),  "(* (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 * s1), "(* (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 * r1),  "(* (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 * r1), "(* (sig s1) (cat (sig r1__a)))")

        # __mod__, __rmod__, __floordiv__, __rfloordiv__
        self.assertEqual(repr(r1 % 1),   "(% (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 % s1),  "(% (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 % r1),   "(% (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 % r1),  "(% (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 // 1),  "(// (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 // s1), "(// (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 // r1),  "(// (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 // r1), "(// (sig s1) (cat (sig r1__a)))")

        # __lshift__, __rlshift__, __rshift__, __rrshift__
        self.assertEqual(repr(r1 >> 1),  "(>> (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 >> s1), "(>> (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 >> r1),  "(>> (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 >> r1), "(>> (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 << 1),  "(<< (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 << s1), "(<< (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 << r1),  "(<< (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 << r1), "(<< (sig s1) (cat (sig r1__a)))")

        # __and__, __rand__, __xor__, __rxor__, __or__, __ror__
        self.assertEqual(repr(r1 & 1),  "(& (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 & s1), "(& (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 & r1),  "(& (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 & r1), "(& (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 ^ 1),  "(^ (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 ^ s1), "(^ (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 ^ r1),  "(^ (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 ^ r1), "(^ (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 | 1),  "(| (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 | s1), "(| (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(1 | r1),  "(| (const 1'd1) (cat (sig r1__a)))")
        self.assertEqual(repr(s1 | r1), "(| (sig s1) (cat (sig r1__a)))")

        # __eq__, __ne__, __lt__, __le__, __gt__, __ge__
        self.assertEqual(repr(r1 == 1),  "(== (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 == s1), "(== (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(s1 == r1), "(== (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 != 1),  "(!= (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 != s1), "(!= (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(s1 != r1), "(!= (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 < 1),   "(< (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 < s1),  "(< (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(s1 < r1),  "(< (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 <= 1),  "(<= (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 <= s1), "(<= (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(s1 <= r1), "(<= (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 > 1),   "(> (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 > s1),  "(> (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(s1 > r1),  "(> (sig s1) (cat (sig r1__a)))")
        self.assertEqual(repr(r1 >= 1),  "(>= (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1 >= s1), "(>= (cat (sig r1__a)) (sig s1))")
        self.assertEqual(repr(s1 >= r1), "(>= (sig s1) (cat (sig r1__a)))")

        # __abs__, __len__
        self.assertEqual(repr(abs(r1)), "(cat (sig r1__a))")
        self.assertEqual(len(r1), 1)

        # as_unsigned, as_signed, bool, any, all, xor, implies
        self.assertEqual(repr(r1.as_unsigned()), "(u (cat (sig r1__a)))")
        self.assertEqual(repr(r1.as_signed()),   "(s (cat (sig r1__a)))")
        self.assertEqual(repr(r1.bool()),        "(b (cat (sig r1__a)))")
        self.assertEqual(repr(r1.any()),         "(r| (cat (sig r1__a)))")
        self.assertEqual(repr(r1.all()),         "(r& (cat (sig r1__a)))")
        self.assertEqual(repr(r1.xor()),         "(r^ (cat (sig r1__a)))")
        self.assertEqual(repr(r1.implies(1)),    "(| (~ (cat (sig r1__a))) (const 1'd1))")
        self.assertEqual(repr(r1.implies(s1)),   "(| (~ (cat (sig r1__a))) (sig s1))")

        # bit_select, word_select, matches,
        self.assertEqual(repr(r1.bit_select(0, 1)),  "(slice (cat (sig r1__a)) 0:1)")
        self.assertEqual(repr(r1.word_select(0, 1)), "(slice (cat (sig r1__a)) 0:1)")
        self.assertEqual(repr(r1.matches("1")),
                "(== (& (cat (sig r1__a)) (const 1'd1)) (const 1'd1))")

        # shift_left, shift_right, rotate_left, rotate_right, eq
        self.assertEqual(repr(r1.shift_left(1)),  "(cat (const 1'd0) (cat (sig r1__a)))")
        self.assertEqual(repr(r1.shift_right(1)), "(slice (cat (sig r1__a)) 1:1)")
        self.assertEqual(repr(r1.rotate_left(1)), "(cat (slice (cat (sig r1__a)) 0:1) (slice (cat (sig r1__a)) 0:0))")
        self.assertEqual(repr(r1.rotate_right(1)), "(cat (slice (cat (sig r1__a)) 0:1) (slice (cat (sig r1__a)) 0:0))")
        self.assertEqual(repr(r1.eq(1)), "(eq (cat (sig r1__a)) (const 1'd1))")
        self.assertEqual(repr(r1.eq(s1)), "(eq (cat (sig r1__a)) (sig s1))")


class ConnectTestCase(FHDLTestCase):
    def setUp_flat(self):
        self.core_layout = [
            ("addr",   32, DIR_FANOUT),
            ("data_r", 32, DIR_FANIN),
            ("data_w", 32, DIR_FANIN),
        ]
        self.periph_layout = [
            ("addr",   32, DIR_FANOUT),
            ("data_r", 32, DIR_FANIN),
            ("data_w", 32, DIR_FANIN),
        ]

    def setUp_nested(self):
        self.core_layout = [
            ("addr",   32, DIR_FANOUT),
            ("data", [
                ("r",  32, DIR_FANIN),
                ("w",  32, DIR_FANIN),
            ]),
        ]
        self.periph_layout = [
            ("addr",   32, DIR_FANOUT),
            ("data", [
                ("r",  32, DIR_FANIN),
                ("w",  32, DIR_FANIN),
            ]),
        ]

    def test_flat(self):
        self.setUp_flat()

        core    = Record(self.core_layout)
        periph1 = Record(self.periph_layout)
        periph2 = Record(self.periph_layout)

        stmts = core.connect(periph1, periph2)
        self.assertRepr(stmts, """(
            (eq (sig periph1__addr) (sig core__addr))
            (eq (sig periph2__addr) (sig core__addr))
            (eq (sig core__data_r) (| (sig periph1__data_r) (sig periph2__data_r)))
            (eq (sig core__data_w) (| (sig periph1__data_w) (sig periph2__data_w)))
        )""")

    def test_flat_include(self):
        self.setUp_flat()

        core    = Record(self.core_layout)
        periph1 = Record(self.periph_layout)
        periph2 = Record(self.periph_layout)

        stmts = core.connect(periph1, periph2, include={"addr": True})
        self.assertRepr(stmts, """(
            (eq (sig periph1__addr) (sig core__addr))
            (eq (sig periph2__addr) (sig core__addr))
        )""")

    def test_flat_exclude(self):
        self.setUp_flat()

        core    = Record(self.core_layout)
        periph1 = Record(self.periph_layout)
        periph2 = Record(self.periph_layout)

        stmts = core.connect(periph1, periph2, exclude={"addr": True})
        self.assertRepr(stmts, """(
            (eq (sig core__data_r) (| (sig periph1__data_r) (sig periph2__data_r)))
            (eq (sig core__data_w) (| (sig periph1__data_w) (sig periph2__data_w)))
        )""")

    def test_nested(self):
        self.setUp_nested()

        core    = Record(self.core_layout)
        periph1 = Record(self.periph_layout)
        periph2 = Record(self.periph_layout)

        stmts = core.connect(periph1, periph2)
        self.maxDiff = None
        self.assertRepr(stmts, """(
            (eq (sig periph1__addr) (sig core__addr))
            (eq (sig periph2__addr) (sig core__addr))
            (eq (sig core__data__r) (| (sig periph1__data__r) (sig periph2__data__r)))
            (eq (sig core__data__w) (| (sig periph1__data__w) (sig periph2__data__w)))
        )""")

    def test_wrong_include_exclude(self):
        self.setUp_flat()

        core   = Record(self.core_layout)
        periph = Record(self.periph_layout)

        with self.assertRaisesRegex(AttributeError,
                r"^Cannot include field 'foo' because it is not present in record 'core'$"):
            core.connect(periph, include={"foo": True})

        with self.assertRaisesRegex(AttributeError,
                r"^Cannot exclude field 'foo' because it is not present in record 'core'$"):
            core.connect(periph, exclude={"foo": True})

    def test_wrong_direction(self):
        recs = [Record([("x", 1)]) for _ in range(2)]

        with self.assertRaisesRegex(TypeError,
                (r"^Cannot connect field 'x' of unnamed record because it does not have "
                    r"a direction$")):
            recs[0].connect(recs[1])

    def test_wrong_missing_field(self):
        core   = Record([("addr", 32, DIR_FANOUT)])
        periph = Record([])

        with self.assertRaisesRegex(AttributeError,
                (r"^Cannot connect field 'addr' of record 'core' to subordinate record 'periph' "
                    r"because the subordinate record does not have this field$")):
            core.connect(periph)
