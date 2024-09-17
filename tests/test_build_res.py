# amaranth: UnusedElaboratable=no

from amaranth.hdl import *
from amaranth.lib.wiring import *
from amaranth.lib.io import *
from amaranth.build.dsl import *
from amaranth.build.res import *
from amaranth._utils import _ignore_deprecated

from .utils import *


class ResourceManagerTestCase(FHDLTestCase):
    def setUp(self):
        self.resources = [
            Resource("clk100", 0, DiffPairs("H1", "H2", dir="i"), Clock(Period(MHz=100))),
            Resource("clk50", 0, Pins("K1"), Clock(Period(MHz=50))),
            Resource("user_led", 0, Pins("A0", dir="o")),
            Resource("i2c", 0,
                Subsignal("scl", Pins("N10", dir="o")),
                Subsignal("sda", Pins("N11"))
            )
        ]
        self.connectors = [
            Connector("pmod", 0, "B0 B1 B2 B3 - -"),
        ]
        self.cm = ResourceManager(self.resources, self.connectors)

    def test_basic(self):
        self.cm = ResourceManager(self.resources, self.connectors)
        self.assertEqual(self.cm.resources, {
            ("clk100",   0): self.resources[0],
            ("clk50",    0): self.resources[1],
            ("user_led", 0): self.resources[2],
            ("i2c",      0): self.resources[3]
        })
        self.assertEqual(self.cm.connectors, {
            ("pmod", 0): self.connectors[0],
        })

    def test_add_resources(self):
        new_resources = [
            Resource("user_led", 1, Pins("A1", dir="o"))
        ]
        self.cm.add_resources(new_resources)
        self.assertEqual(self.cm.resources, {
            ("clk100",   0): self.resources[0],
            ("clk50",    0): self.resources[1],
            ("user_led", 0): self.resources[2],
            ("i2c",      0): self.resources[3],
            ("user_led", 1): new_resources[0]
        })

    def test_lookup(self):
        r = self.cm.lookup("user_led", 0)
        self.assertIs(r, self.cm.resources["user_led", 0])

    def test_request_basic(self):
        r = self.cm.lookup("user_led", 0)
        with _ignore_deprecated():
            user_led = self.cm.request("user_led", 0)

        self.assertIsInstance(flipped(user_led), Pin)
        self.assertEqual(user_led.o.name, "user_led_0__o")
        self.assertEqual(user_led.width, 1)
        self.assertEqual(user_led.dir, "o")

        (pin, port, buffer), = self.cm.iter_pins()
        buffer._MustUse__silence = True

        self.assertIs(pin, user_led)
        self.assertEqual(port.io.name, "user_led_0__io")
        self.assertEqual(port.io.metadata[0].name, "A0")
        self.assertEqual(port.io.metadata[0].attrs, {})
        self.assertEqual(port.direction, Direction.Output)
        self.assertEqual(port.invert, (False,))

    def test_request_with_dir(self):
        with _ignore_deprecated():
            i2c = self.cm.request("i2c", 0, dir={"sda": "o"})
        self.assertIsInstance(flipped(i2c.sda), Pin)
        self.assertEqual(i2c.sda.dir, "o")
        ((_, _, scl_buffer), (_, _, sda_buffer)) = self.cm.iter_pins()
        scl_buffer._MustUse__silence = True
        sda_buffer._MustUse__silence = True

    def test_request_subsignal_dash(self):
        with _ignore_deprecated():
            i2c = self.cm.request("i2c", 0, dir="-")
        self.assertIsInstance(i2c.sda, SingleEndedPort)
        self.assertIsInstance(i2c.scl, SingleEndedPort)

    def test_request_tristate(self):
        with _ignore_deprecated():
            i2c = self.cm.request("i2c", 0)
        self.assertEqual(i2c.sda.dir, "io")

        ((scl_pin, scl_port, scl_buffer), (sda_pin, sda_port, sda_buffer)) = self.cm.iter_pins()
        scl_buffer._MustUse__silence = True
        sda_buffer._MustUse__silence = True

        self.assertIs(scl_pin, i2c.scl)
        self.assertIs(sda_pin, i2c.sda)
        self.assertEqual(scl_port.io.name, "i2c_0__scl__io")
        self.assertEqual(scl_port.io.metadata[0].name, "N10")
        self.assertEqual(sda_port.io.name, "i2c_0__sda__io")
        self.assertEqual(sda_port.io.metadata[0].name, "N11")

    def test_request_diffpairs(self):
        with _ignore_deprecated():
            clk100 = self.cm.request("clk100", 0)
        self.assertIsInstance(flipped(clk100), Pin)
        self.assertEqual(clk100.dir, "i")
        self.assertEqual(clk100.width, 1)

        (clk100_pin, clk100_port, buffer), = self.cm.iter_pins()
        buffer._MustUse__silence = True

        self.assertIs(clk100_pin, clk100)
        self.assertEqual(clk100_port.p.name, "clk100_0__p")
        self.assertEqual(clk100_port.p.width, clk100.width)
        self.assertEqual(clk100_port.n.name, "clk100_0__n")
        self.assertEqual(clk100_port.n.width, clk100.width)
        self.assertEqual(clk100_port.p.metadata[0].name, "H1")
        self.assertEqual(clk100_port.n.metadata[0].name, "H2")

    def test_request_inverted(self):
        new_resources = [
            Resource("cs", 0, PinsN("X0")),
            Resource("clk", 0, DiffPairsN("Y0", "Y1")),
        ]
        self.cm.add_resources(new_resources)

        with _ignore_deprecated():
            cs = self.cm.request("cs")
            clk = self.cm.request("clk")

        (
            (cs_pin, cs_port, cs_buffer),
            (clk_pin, clk_port, clk_buffer),
        ) = self.cm.iter_pins()
        cs_buffer._MustUse__silence = True
        clk_buffer._MustUse__silence = True

        self.assertIs(cs_pin, cs)
        self.assertEqual(cs_port.invert, (True,))
        self.assertIs(clk_pin, clk)
        self.assertEqual(clk_port.invert, (True,))

    def test_request_raw(self):
        clk50 = self.cm.request("clk50", 0, dir="-")
        self.assertIsInstance(clk50, SingleEndedPort)
        self.assertIsInstance(clk50.io, IOPort)

    def test_request_raw_diffpairs(self):
        clk100 = self.cm.request("clk100", 0, dir="-")
        self.assertIsInstance(clk100, DifferentialPort)
        self.assertIsInstance(clk100.p, IOPort)
        self.assertIsInstance(clk100.n, IOPort)

    def test_request_via_connector(self):
        self.cm.add_resources([
            Resource("spi", 0,
                Subsignal("cs",   Pins("1", conn=("pmod", 0))),
                Subsignal("clk",  Pins("2", conn=("pmod", 0))),
                Subsignal("cipo", Pins("3", conn=("pmod", 0))),
                Subsignal("copi", Pins("4", conn=("pmod", 0))),
            )
        ])
        with _ignore_deprecated():
            spi0 = self.cm.request("spi", 0)
        (
            (cs_pin, cs_port, cs_buffer),
            (clk_pin, clk_port, clk_buffer),
            (cipo_pin, cipo_port, cipo_buffer),
            (copi_pin, copi_port, copi_buffer),
        ) = self.cm.iter_pins()
        cs_buffer._MustUse__silence = True
        clk_buffer._MustUse__silence = True
        cipo_buffer._MustUse__silence = True
        copi_buffer._MustUse__silence = True
        self.assertIs(cs_pin, spi0.cs)
        self.assertIs(clk_pin, spi0.clk)
        self.assertIs(cipo_pin, spi0.cipo)
        self.assertIs(copi_pin, spi0.copi)
        self.assertEqual(cs_port.io.metadata[0].name, "B0")
        self.assertEqual(clk_port.io.metadata[0].name, "B1")
        self.assertEqual(cipo_port.io.metadata[0].name, "B2")
        self.assertEqual(copi_port.io.metadata[0].name, "B3")

    def test_request_via_nested_connector(self):
        new_connectors = [
            Connector("pmod_extension", 0, "1 2 3 4 - -", conn=("pmod", 0)),
        ]
        self.cm.add_connectors(new_connectors)
        self.cm.add_resources([
            Resource("spi", 0,
                Subsignal("cs",   Pins("1", conn=("pmod_extension", 0))),
                Subsignal("clk",  Pins("2", conn=("pmod_extension", 0))),
                Subsignal("cipo", Pins("3", conn=("pmod_extension", 0))),
                Subsignal("copi", Pins("4", conn=("pmod_extension", 0))),
            )
        ])
        with _ignore_deprecated():
            spi0 = self.cm.request("spi", 0)
        (
            (cs_pin, cs_port, cs_buffer),
            (clk_pin, clk_port, clk_buffer),
            (cipo_pin, cipo_port, cipo_buffer),
            (copi_pin, copi_port, copi_buffer),
        ) = self.cm.iter_pins()
        cs_buffer._MustUse__silence = True
        clk_buffer._MustUse__silence = True
        cipo_buffer._MustUse__silence = True
        copi_buffer._MustUse__silence = True
        self.assertIs(cs_pin, spi0.cs)
        self.assertIs(clk_pin, spi0.clk)
        self.assertIs(cipo_pin, spi0.cipo)
        self.assertIs(copi_pin, spi0.copi)
        self.assertEqual(cs_port.io.metadata[0].name, "B0")
        self.assertEqual(clk_port.io.metadata[0].name, "B1")
        self.assertEqual(cipo_port.io.metadata[0].name, "B2")
        self.assertEqual(copi_port.io.metadata[0].name, "B3")

    def test_request_clock(self):
        with _ignore_deprecated():
            clk100 = self.cm.request("clk100", 0)
            clk50 = self.cm.request("clk50", 0, dir="i")
        (
            (clk100_pin, clk100_port, clk100_buffer),
            (clk50_pin, clk50_port, clk50_buffer),
        ) = self.cm.iter_pins()
        clk100_buffer._MustUse__silence = True
        clk50_buffer._MustUse__silence = True
        self.assertEqual(list(self.cm.iter_port_clock_constraints()), [
            (clk100_port.p, 100e6),
            (clk50_port.io, 50e6)
        ])

    def test_add_clock(self):
        with _ignore_deprecated():
            i2c = self.cm.request("i2c")
        self.cm.add_clock_constraint(i2c.scl.o, 100e3)
        self.assertEqual(list(self.cm.iter_signal_clock_constraints()), [
            (i2c.scl.o, 100e3)
        ])
        ((_, _, scl_buffer), (_, _, sda_buffer)) = self.cm.iter_pins()
        scl_buffer._MustUse__silence = True
        sda_buffer._MustUse__silence = True

    def test_wrong_resources(self):
        with self.assertRaisesRegex(TypeError, r"^Object 'wrong' is not a Resource$"):
            self.cm.add_resources(['wrong'])

    def test_wrong_resources_duplicate(self):
        with self.assertRaisesRegex(NameError,
                (r"^Trying to add \(resource user_led 0 \(pins o A1\)\), but "
                    r"\(resource user_led 0 \(pins o A0\)\) has the same name and number$")):
            self.cm.add_resources([Resource("user_led", 0, Pins("A1", dir="o"))])

    def test_wrong_connectors(self):
        with self.assertRaisesRegex(TypeError, r"^Object 'wrong' is not a Connector$"):
            self.cm.add_connectors(['wrong'])

    def test_wrong_connectors_duplicate(self):
        with self.assertRaisesRegex(NameError,
                (r"^Trying to add \(connector pmod 0 1=>1 2=>2\), but "
                    r"\(connector pmod 0 1=>B0 2=>B1 3=>B2 4=>B3\) has the same name and number$")):
            self.cm.add_connectors([Connector("pmod", 0, "1 2")])

    def test_wrong_lookup(self):
        with self.assertRaisesRegex(ResourceError,
                r"^Resource user_led#1 does not exist$"):
            r = self.cm.lookup("user_led", 1)

    def test_wrong_clock_signal(self):
        with self.assertRaisesRegex(TypeError,
                r"^Object None is not a Signal or IOPort$"):
            self.cm.add_clock_constraint(None, 10e6)

    def test_wrong_clock_frequency(self):
        with self.assertRaisesRegex(TypeError,
                r"^Frequency must be a number, not None$"):
            self.cm.add_clock_constraint(Signal(), None)

    def test_wrong_request_duplicate(self):
        with _ignore_deprecated():
            self.cm.request("user_led", 0)
        (pin, port, buffer), = self.cm.iter_pins()
        buffer._MustUse__silence = True
        with self.assertRaisesRegex(ResourceError,
                r"^Resource user_led#0 has already been requested$"):
            with _ignore_deprecated():
                self.cm.request("user_led", 0)

    def test_wrong_request_duplicate_physical(self):
        self.cm.add_resources([
            Resource("clk20", 0, Pins("H1", dir="i")),
        ])
        with _ignore_deprecated():
            self.cm.request("clk100", 0)
        (pin, port, buffer), = self.cm.iter_pins()
        buffer._MustUse__silence = True
        with self.assertRaisesRegex(ResourceError,
                (r"^Resource component clk20_0 uses physical pin H1, but it is already "
                    r"used by resource component clk100_0 that was requested earlier$")):
            with _ignore_deprecated():
                self.cm.request("clk20", 0)

    def test_wrong_request_with_dir(self):
        with self.assertRaisesRegex(TypeError,
                (r"^Direction must be one of \"i\", \"o\", \"oe\", \"io\", or \"-\", "
                    r"not 'wrong'$")):
            user_led = self.cm.request("user_led", 0, dir="wrong")

    def test_wrong_request_with_dir_io(self):
        with self.assertRaisesRegex(ValueError,
                (r"^Direction of \(pins o A0\) cannot be changed from \"o\" to \"i\"; direction "
                    r"can be changed from \"io\" to \"i\", \"o\", or \"oe\", or from anything "
                    r"to \"-\"$")):
            user_led = self.cm.request("user_led", 0, dir="i")

    def test_wrong_request_with_dir_dict(self):
        with self.assertRaisesRegex(TypeError,
                (r"^Directions must be a dict, not 'i', because \(resource i2c 0 \(subsignal scl "
                    r"\(pins o N10\)\) \(subsignal sda \(pins io N11\)\)\) "
                    r"has subsignals$")):
            i2c = self.cm.request("i2c", 0, dir="i")

    def test_wrong_request_with_wrong_xdr(self):
        with self.assertRaisesRegex(ValueError,
                r"^Data rate of \(pins o A0\) must be a non-negative integer, not -1$"):
            user_led = self.cm.request("user_led", 0, xdr=-1)

    def test_wrong_request_with_xdr_dict(self):
        with self.assertRaisesRegex(TypeError,
                r"^Data rate must be a dict, not 2, because \(resource i2c 0 \(subsignal scl "
                    r"\(pins o N10\)\) \(subsignal sda \(pins io N11\)\)\) "
                    r"has subsignals$"):
            i2c = self.cm.request("i2c", 0, xdr=2)

    def test_wrong_clock_constraint_twice(self):
        with _ignore_deprecated():
            clk100 = self.cm.request("clk100", dir="-")
        with self.assertRaisesRegex(ValueError,
                (r"^Cannot add clock constraint on \(io-port clk100_0__p\), which is already "
                    r"constrained to 100000000\.0 Hz$")):
            self.cm.add_clock_constraint(clk100.p, 1e6)
