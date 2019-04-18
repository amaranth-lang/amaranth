from ..build.dsl import *
from .tools import *


class PinsTestCase(FHDLTestCase):
    def test_basic(self):
        p = Pins("A0 A1 A2")
        self.assertEqual(repr(p), "(pins A0 A1 A2 io)")
        self.assertEqual(len(p.names), 3)
        self.assertEqual(p.dir, "io")

    def test_wrong_names(self):
        with self.assertRaises(TypeError,
                msg="Names must be a whitespace-separated string, not ['A0', 'A1', 'A2']"):
            p = Pins(["A0", "A1", "A2"])

    def test_wrong_dir(self):
        with self.assertRaises(TypeError,
                msg="Direction must be one of \"i\", \"o\" or \"io\", not 'wrong'"):
            p = Pins("A0 A1", dir="wrong")


class DiffPairsTestCase(FHDLTestCase):
    def test_basic(self):
        dp = DiffPairs(p="A0 A1", n="B0 B1")
        self.assertEqual(repr(dp), "(diffpairs (pins A0 A1 io) (pins B0 B1 io))")
        self.assertEqual(dp.p.names, ["A0", "A1"])
        self.assertEqual(dp.n.names, ["B0", "B1"])
        self.assertEqual(dp.dir, "io")

    def test_dir(self):
        dp = DiffPairs("A0", "B0", dir="o")
        self.assertEqual(dp.dir, "o")
        self.assertEqual(dp.p.dir, "o")
        self.assertEqual(dp.n.dir, "o")

    def test_wrong_width(self):
        with self.assertRaises(TypeError,
                msg="Positive and negative pins must have the same width, but (pins A0 io) and "
                    "(pins B0 B1 io) do not"):
            dp = DiffPairs("A0", "B0 B1")


class SubsignalTestCase(FHDLTestCase):
    def test_basic_pins(self):
        s = Subsignal("a", Pins("A0"), extras=["IOSTANDARD=LVCMOS33"])
        self.assertEqual(repr(s), "(subsignal a (pins A0 io) IOSTANDARD=LVCMOS33)")

    def test_basic_diffpairs(self):
        s = Subsignal("a", DiffPairs("A0", "B0"))
        self.assertEqual(repr(s), "(subsignal a (diffpairs (pins A0 io) (pins B0 io)) )")

    def test_basic_subsignals(self):
        s = Subsignal("a",
                Subsignal("b", Pins("A0")),
                Subsignal("c", Pins("A1")))
        self.assertEqual(repr(s),
                "(subsignal a (subsignal b (pins A0 io) ) (subsignal c (pins A1 io) ) )")

    def test_extras(self):
        s = Subsignal("a",
                Subsignal("b", Pins("A0")),
                Subsignal("c", Pins("A0"), extras=["SLEW=FAST"]),
                extras=["IOSTANDARD=LVCMOS33"])
        self.assertEqual(s.extras, ["IOSTANDARD=LVCMOS33"])
        self.assertEqual(s.io[0].extras, ["IOSTANDARD=LVCMOS33"])
        self.assertEqual(s.io[1].extras, ["SLEW=FAST", "IOSTANDARD=LVCMOS33"])

    def test_empty_io(self):
        with self.assertRaises(TypeError, msg="Missing I/O constraints"):
            s = Subsignal("a")

    def test_wrong_io(self):
        with self.assertRaises(TypeError,
                msg="I/O constraint must be one of Pins, DiffPairs or Subsignal, not 'wrong'"):
            s = Subsignal("a", "wrong")

    def test_wrong_pins(self):
        with self.assertRaises(TypeError,
                msg="Pins and DiffPairs cannot be followed by more I/O constraints, but "
                    "(pins A0 io) is followed by (pins A1 io)"):
            s = Subsignal("a", Pins("A0"), Pins("A1"))

    def test_wrong_diffpairs(self):
        with self.assertRaises(TypeError,
                msg="Pins and DiffPairs cannot be followed by more I/O constraints, but "
                    "(diffpairs (pins A0 io) (pins B0 io)) is followed by (pins A1 io)"):
            s = Subsignal("a", DiffPairs("A0", "B0"), Pins("A1"))

    def test_wrong_subsignals(self):
        with self.assertRaises(TypeError,
                msg="A Subsignal can only be followed by more Subsignals, but "
                    "(subsignal b (pins A0 io) ) is followed by (pins B0 io)"):
            s = Subsignal("a", Subsignal("b", Pins("A0")), Pins("B0"))

    def test_wrong_extras(self):
        with self.assertRaises(TypeError,
                msg="Extra constraint must be a string, not (pins B0 io)"):
            s = Subsignal("a", Pins("A0"), extras=[Pins("B0")])


class ResourceTestCase(FHDLTestCase):
    def test_basic(self):
        r = Resource("serial", 0,
                Subsignal("tx", Pins("A0", dir="o")),
                Subsignal("rx", Pins("A1", dir="i")),
                extras=["IOSTANDARD=LVCMOS33"])
        self.assertEqual(repr(r), "(resource serial 0"
                                  " (subsignal tx (pins A0 o) IOSTANDARD=LVCMOS33)"
                                  " (subsignal rx (pins A1 i) IOSTANDARD=LVCMOS33)"
                                  " IOSTANDARD=LVCMOS33)")
