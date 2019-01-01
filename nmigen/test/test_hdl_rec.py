from ..hdl.ast import *
from ..hdl.rec import *
from .tools import *


class LayoutTestCase(FHDLTestCase):
    def test_fields(self):
        layout = Layout.wrap([
            ("cyc",  1),
            ("data", (32, True)),
            ("stb",  1, DIR_FANOUT),
            ("ack",  1, DIR_FANIN),
            ("info", [
                ("a", 1),
                ("b", 1),
            ])
        ])

        self.assertEqual(layout["cyc"], (1, DIR_NONE))
        self.assertEqual(layout["data"], ((32, True), DIR_NONE))
        self.assertEqual(layout["stb"], (1, DIR_FANOUT))
        self.assertEqual(layout["ack"], (1, DIR_FANIN))
        sublayout = layout["info"][0]
        self.assertEqual(layout["info"][1], DIR_NONE)
        self.assertEqual(sublayout["a"], (1, DIR_NONE))
        self.assertEqual(sublayout["b"], (1, DIR_NONE))

    def test_wrong_field(self):
        with self.assertRaises(TypeError,
                msg="Field (1,) has invalid layout: should be either (name, shape) or "
                    "(name, shape, direction)"):
            Layout.wrap([(1,)])

    def test_wrong_name(self):
        with self.assertRaises(TypeError,
                msg="Field (1, 1) has invalid name: should be a string"):
            Layout.wrap([(1, 1)])

    def test_wrong_name_duplicate(self):
        with self.assertRaises(NameError,
                msg="Field ('a', 2) has a name that is already present in the layout"):
            Layout.wrap([("a", 1), ("a", 2)])

    def test_wrong_direction(self):
        with self.assertRaises(TypeError,
                msg="Field ('a', 1, 0) has invalid direction: should be a Direction "
                    "instance like DIR_FANIN"):
            Layout.wrap([("a", 1, 0)])

    def test_wrong_shape(self):
        with self.assertRaises(TypeError,
                msg="Field ('a', 'x') has invalid shape: should be an int, tuple, or "
                    "list of fields of a nested record"):
            Layout.wrap([("a", "x")])


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

        self.assertEqual(repr(r), "(rec r stb data (rec r_info a b))")
        self.assertEqual(len(r),  35)
        self.assertIsInstance(r.stb, Signal)
        self.assertEqual(r.stb.name, "r_stb")
        self.assertEqual(r["stb"].name, "r_stb")

    def test_unnamed(self):
        r = [Record([
            ("stb", 1)
        ])][0]

        self.assertEqual(repr(r), "(rec <unnamed> stb)")
        self.assertEqual(r.stb.name, "stb")

    def test_wrong_field(self):
        r = Record([
            ("stb", 1),
            ("ack", 1),
        ])
        with self.assertRaises(NameError,
                msg="Record 'r' does not have a field 'en'. Did you mean one of: stb, ack?"):
            r.en

    def test_wrong_field_unnamed(self):
        r = [Record([
            ("stb", 1),
            ("ack", 1),
        ])][0]
        with self.assertRaises(NameError,
                msg="Unnamed record does not have a field 'en'. Did you mean one of: stb, ack?"):
            r.en
