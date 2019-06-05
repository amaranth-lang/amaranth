from collections import OrderedDict

from ..build.dsl import *
from .tools import *


class PinsTestCase(FHDLTestCase):
    def test_basic(self):
        p = Pins("A0 A1 A2")
        self.assertEqual(repr(p), "(pins io A0 A1 A2)")
        self.assertEqual(len(p.names), 3)
        self.assertEqual(p.dir, "io")
        self.assertEqual(list(p), ["A0", "A1", "A2"])

    def test_conn(self):
        p = Pins("0 1 2", conn=("pmod", 0))
        self.assertEqual(list(p), ["pmod_0:0", "pmod_0:1", "pmod_0:2"])

    def test_map_names(self):
        p = Pins("0 1 2", conn=("pmod", 0))
        mapping = {
            "pmod_0:0": "A0",
            "pmod_0:1": "A1",
            "pmod_0:2": "A2",
        }
        self.assertEqual(p.map_names(mapping, p), ["A0", "A1", "A2"])

    def test_map_names_recur(self):
        p = Pins("0", conn=("pmod", 0))
        mapping = {
            "pmod_0:0": "ext_0:1",
            "ext_0:1":  "A1",
        }
        self.assertEqual(p.map_names(mapping, p), ["A1"])

    def test_wrong_names(self):
        with self.assertRaises(TypeError,
                msg="Names must be a whitespace-separated string, not ['A0', 'A1', 'A2']"):
            p = Pins(["A0", "A1", "A2"])

    def test_wrong_dir(self):
        with self.assertRaises(TypeError,
                msg="Direction must be one of \"i\", \"o\", \"oe\", or \"io\", not 'wrong'"):
            p = Pins("A0 A1", dir="wrong")

    def test_wrong_map_names(self):
        p = Pins("0 1 2", conn=("pmod", 0))
        mapping = {
            "pmod_0:0": "A0",
        }
        with self.assertRaises(NameError,
                msg="Resource (pins io pmod_0:0 pmod_0:1 pmod_0:2) refers to nonexistent "
                    "connector pin pmod_0:1"):
            p.map_names(mapping, p)


class DiffPairsTestCase(FHDLTestCase):
    def test_basic(self):
        dp = DiffPairs(p="A0 A1", n="B0 B1")
        self.assertEqual(repr(dp), "(diffpairs io (p A0 A1) (n B0 B1))")
        self.assertEqual(dp.p.names, ["A0", "A1"])
        self.assertEqual(dp.n.names, ["B0", "B1"])
        self.assertEqual(dp.dir, "io")
        self.assertEqual(list(dp), [("A0", "B0"), ("A1", "B1")])

    def test_conn(self):
        dp = DiffPairs(p="0 1 2", n="3 4 5", conn=("pmod", 0))
        self.assertEqual(list(dp), [
            ("pmod_0:0", "pmod_0:3"),
            ("pmod_0:1", "pmod_0:4"),
            ("pmod_0:2", "pmod_0:5"),
        ])

    def test_dir(self):
        dp = DiffPairs("A0", "B0", dir="o")
        self.assertEqual(dp.dir, "o")
        self.assertEqual(dp.p.dir, "o")
        self.assertEqual(dp.n.dir, "o")

    def test_wrong_width(self):
        with self.assertRaises(TypeError,
                msg="Positive and negative pins must have the same width, but (pins io A0) "
                    "and (pins io B0 B1) do not"):
            dp = DiffPairs("A0", "B0 B1")


class AttrsTestCase(FHDLTestCase):
    def test_basic(self):
        a = Attrs(IO_STANDARD="LVCMOS33", PULLUP="1")
        self.assertEqual(a["IO_STANDARD"], "LVCMOS33")
        self.assertEqual(repr(a), "(attrs IO_STANDARD=LVCMOS33 PULLUP=1)")

    def test_wrong_value(self):
        with self.assertRaises(TypeError,
                msg="Attribute value must be a string, not 1"):
            a = Attrs(FOO=1)


class ClockTestCase(FHDLTestCase):
    def test_basic(self):
        c = Clock(1_000_000)
        self.assertEqual(c.frequency, 1e6)
        self.assertEqual(c.period, 1e-6)
        self.assertEqual(repr(c), "(clock 1000000.0)")


class SubsignalTestCase(FHDLTestCase):
    def test_basic_pins(self):
        s = Subsignal("a", Pins("A0"), Attrs(IOSTANDARD="LVCMOS33"))
        self.assertEqual(repr(s),
            "(subsignal a (pins io A0) (attrs IOSTANDARD=LVCMOS33))")

    def test_basic_diffpairs(self):
        s = Subsignal("a", DiffPairs("A0", "B0"))
        self.assertEqual(repr(s),
            "(subsignal a (diffpairs io (p A0) (n B0)))")

    def test_basic_subsignals(self):
        s = Subsignal("a",
                Subsignal("b", Pins("A0")),
                Subsignal("c", Pins("A1")))
        self.assertEqual(repr(s),
            "(subsignal a (subsignal b (pins io A0)) "
                         "(subsignal c (pins io A1)))")

    def test_attrs(self):
        s = Subsignal("a",
                Subsignal("b", Pins("A0")),
                Subsignal("c", Pins("A0"), Attrs(SLEW="FAST")),
                Attrs(IOSTANDARD="LVCMOS33"))
        self.assertEqual(s.attrs, {"IOSTANDARD": "LVCMOS33"})
        self.assertEqual(s.ios[0].attrs, {})
        self.assertEqual(s.ios[1].attrs, {"SLEW": "FAST"})

    def test_attrs_many(self):
        s = Subsignal("a", Pins("A0"), Attrs(SLEW="FAST"), Attrs(PULLUP="1"))
        self.assertEqual(s.attrs, {"SLEW": "FAST", "PULLUP": "1"})

    def test_clock(self):
        s = Subsignal("a", Pins("A0"), Clock(1e6))
        self.assertEqual(s.clock.frequency, 1e6)

    def test_wrong_empty_io(self):
        with self.assertRaises(ValueError, msg="Missing I/O constraints"):
            s = Subsignal("a")

    def test_wrong_io(self):
        with self.assertRaises(TypeError,
                msg="Constraint must be one of Pins, DiffPairs, Subsignal, Attrs, or Clock, "
                    "not 'wrong'"):
            s = Subsignal("a", "wrong")

    def test_wrong_pins(self):
        with self.assertRaises(TypeError,
                msg="Pins and DiffPairs are incompatible with other location or subsignal "
                    "constraints, but (pins io A1) appears after (pins io A0)"):
            s = Subsignal("a", Pins("A0"), Pins("A1"))

    def test_wrong_diffpairs(self):
        with self.assertRaises(TypeError,
                msg="Pins and DiffPairs are incompatible with other location or subsignal "
                    "constraints, but (pins io A1) appears after (diffpairs io (p A0) (n B0))"):
            s = Subsignal("a", DiffPairs("A0", "B0"), Pins("A1"))

    def test_wrong_subsignals(self):
        with self.assertRaises(TypeError,
                msg="Pins and DiffPairs are incompatible with other location or subsignal "
                    "constraints, but (pins io B0) appears after (subsignal b (pins io A0))"):
            s = Subsignal("a", Subsignal("b", Pins("A0")), Pins("B0"))

    def test_wrong_clock(self):
        with self.assertRaises(TypeError,
                msg="Clock constraint can only be applied to Pins or DiffPairs, not "
                    "(subsignal b (pins io A0))"):
            s = Subsignal("a", Subsignal("b", Pins("A0")), Clock(1e6))

    def test_wrong_clock_many(self):
        with self.assertRaises(ValueError,
                msg="Clock constraint can be applied only once"):
            s = Subsignal("a", Pins("A0"), Clock(1e6), Clock(1e7))


class ResourceTestCase(FHDLTestCase):
    def test_basic(self):
        r = Resource("serial", 0,
                Subsignal("tx", Pins("A0", dir="o")),
                Subsignal("rx", Pins("A1", dir="i")),
                Attrs(IOSTANDARD="LVCMOS33"))
        self.assertEqual(repr(r), "(resource serial 0"
                                  " (subsignal tx (pins o A0))"
                                  " (subsignal rx (pins i A1))"
                                  " (attrs IOSTANDARD=LVCMOS33))")


class ConnectorTestCase(FHDLTestCase):
    def test_string(self):
        c = Connector("pmod", 0, "A0 A1 A2 A3 - - A4 A5 A6 A7 - -")
        self.assertEqual(c.name, "pmod")
        self.assertEqual(c.number, 0)
        self.assertEqual(c.mapping, OrderedDict([
            ("1", "A0"),
            ("2", "A1"),
            ("3", "A2"),
            ("4", "A3"),
            ("7", "A4"),
            ("8", "A5"),
            ("9", "A6"),
            ("10", "A7"),
        ]))
        self.assertEqual(list(c), [
            ("pmod_0:1", "A0"),
            ("pmod_0:2", "A1"),
            ("pmod_0:3", "A2"),
            ("pmod_0:4", "A3"),
            ("pmod_0:7", "A4"),
            ("pmod_0:8", "A5"),
            ("pmod_0:9", "A6"),
            ("pmod_0:10", "A7"),
        ])
        self.assertEqual(repr(c),
            "(connector pmod 0 1=>A0 2=>A1 3=>A2 4=>A3 7=>A4 8=>A5 9=>A6 10=>A7)")

    def test_dict(self):
        c = Connector("ext", 1, {"DP0": "A0", "DP1": "A1"})
        self.assertEqual(c.name, "ext")
        self.assertEqual(c.number, 1)
        self.assertEqual(c.mapping, OrderedDict([
            ("DP0", "A0"),
            ("DP1", "A1"),
        ]))

    def test_wrong_io(self):
        with self.assertRaises(TypeError,
                msg="Connector I/Os must be a dictionary or a string, not []"):
            Connector("pmod", 0, [])

    def test_wrong_dict_key_value(self):
        with self.assertRaises(TypeError,
                msg="Connector pin name must be a string, not 0"):
            Connector("pmod", 0, {0: "A"})
        with self.assertRaises(TypeError,
                msg="Platform pin name must be a string, not 0"):
            Connector("pmod", 0, {"A": 0})
