# amaranth: UnusedElaboratable=no

from amaranth import *
from amaranth.hdl.rec import *
from amaranth.lib.io import *
from amaranth.build.dsl import *
from amaranth.build.res import *

from .utils import *


class ResourceManagerTestCase(FHDLTestCase):
    def setUp(self):
        self.resources = [
            Resource("clk100", 0, DiffPairs("H1", "H2", dir="i"), Clock(100e6)),
            Resource("clk50", 0, Pins("K1"), Clock(50e6)),
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
        user_led = self.cm.request("user_led", 0)

        self.assertIsInstance(user_led, Pin)
        self.assertEqual(user_led.name, "user_led_0")
        self.assertEqual(user_led.width, 1)
        self.assertEqual(user_led.dir, "o")

        ports = list(self.cm.iter_ports())
        self.assertEqual(len(ports), 1)

        self.assertEqual(list(self.cm.iter_port_constraints()), [
            ("user_led_0__io", ["A0"], {})
        ])

    def test_request_with_dir(self):
        i2c = self.cm.request("i2c", 0, dir={"sda": "o"})
        self.assertIsInstance(i2c, Record)
        self.assertIsInstance(i2c.sda, Pin)
        self.assertEqual(i2c.sda.dir, "o")

    def test_request_tristate(self):
        i2c = self.cm.request("i2c", 0)
        self.assertEqual(i2c.sda.dir, "io")

        ports = list(self.cm.iter_ports())
        self.assertEqual(len(ports), 2)
        scl, sda = ports
        self.assertEqual(ports[1].name, "i2c_0__sda__io")
        self.assertEqual(ports[1].width, 1)

        scl_info, sda_info = self.cm.iter_single_ended_pins()
        self.assertIs(scl_info[0], i2c.scl)
        self.assertIs(scl_info[1].io, scl)
        self.assertEqual(scl_info[2], {})
        self.assertEqual(scl_info[3], False)
        self.assertIs(sda_info[0], i2c.sda)
        self.assertIs(sda_info[1].io, sda)

        self.assertEqual(list(self.cm.iter_port_constraints()), [
            ("i2c_0__scl__io", ["N10"], {}),
            ("i2c_0__sda__io", ["N11"], {})
        ])

    def test_request_diffpairs(self):
        clk100 = self.cm.request("clk100", 0)
        self.assertIsInstance(clk100, Pin)
        self.assertEqual(clk100.dir, "i")
        self.assertEqual(clk100.width, 1)

        ports = list(self.cm.iter_ports())
        self.assertEqual(len(ports), 2)
        p, n = ports
        self.assertEqual(p.name, "clk100_0__p")
        self.assertEqual(p.width, clk100.width)
        self.assertEqual(n.name, "clk100_0__n")
        self.assertEqual(n.width, clk100.width)

        clk100_info, = self.cm.iter_differential_pins()
        self.assertIs(clk100_info[0], clk100)
        self.assertIs(clk100_info[1].p, p)
        self.assertIs(clk100_info[1].n, n)
        self.assertEqual(clk100_info[2], {})
        self.assertEqual(clk100_info[3], False)

        self.assertEqual(list(self.cm.iter_port_constraints()), [
            ("clk100_0__p", ["H1"], {}),
            ("clk100_0__n", ["H2"], {}),
        ])

    def test_request_inverted(self):
        new_resources = [
            Resource("cs", 0, PinsN("X0")),
            Resource("clk", 0, DiffPairsN("Y0", "Y1")),
        ]
        self.cm.add_resources(new_resources)

        cs = self.cm.request("cs")
        clk = self.cm.request("clk")
        cs_io, clk_p, clk_n = self.cm.iter_ports()

        cs_info, = self.cm.iter_single_ended_pins()
        self.assertIs(cs_info[0], cs)
        self.assertIs(cs_info[1].io, cs_io)
        self.assertEqual(cs_info[2], {})
        self.assertEqual(cs_info[3], True)

        clk_info, = self.cm.iter_differential_pins()
        self.assertIs(clk_info[0], clk)
        self.assertIs(clk_info[1].p, clk_p)
        self.assertIs(clk_info[1].n, clk_n)
        self.assertEqual(clk_info[2], {})
        self.assertEqual(clk_info[3], True)

    def test_request_raw(self):
        clk50 = self.cm.request("clk50", 0, dir="-")
        self.assertIsInstance(clk50, Record)
        self.assertIsInstance(clk50.io, Signal)

        ports = list(self.cm.iter_ports())
        self.assertEqual(len(ports), 1)
        self.assertIs(ports[0], clk50.io)

    def test_request_raw_diffpairs(self):
        clk100 = self.cm.request("clk100", 0, dir="-")
        self.assertIsInstance(clk100, Record)
        self.assertIsInstance(clk100.p, Signal)
        self.assertIsInstance(clk100.n, Signal)

        ports = list(self.cm.iter_ports())
        self.assertEqual(len(ports), 2)
        self.assertIs(ports[0], clk100.p)
        self.assertIs(ports[1], clk100.n)

    def test_request_via_connector(self):
        self.cm.add_resources([
            Resource("spi", 0,
                Subsignal("ss",   Pins("1", conn=("pmod", 0))),
                Subsignal("clk",  Pins("2", conn=("pmod", 0))),
                Subsignal("miso", Pins("3", conn=("pmod", 0))),
                Subsignal("mosi", Pins("4", conn=("pmod", 0))),
            )
        ])
        spi0 = self.cm.request("spi", 0)
        self.assertEqual(list(self.cm.iter_port_constraints()), [
            ("spi_0__ss__io",   ["B0"], {}),
            ("spi_0__clk__io",  ["B1"], {}),
            ("spi_0__miso__io", ["B2"], {}),
            ("spi_0__mosi__io", ["B3"], {}),
        ])

    def test_request_via_nested_connector(self):
        new_connectors = [
            Connector("pmod_extension", 0, "1 2 3 4 - -", conn=("pmod", 0)),
        ]
        self.cm.add_connectors(new_connectors)
        self.cm.add_resources([
            Resource("spi", 0,
                Subsignal("ss",   Pins("1", conn=("pmod_extension", 0))),
                Subsignal("clk",  Pins("2", conn=("pmod_extension", 0))),
                Subsignal("miso", Pins("3", conn=("pmod_extension", 0))),
                Subsignal("mosi", Pins("4", conn=("pmod_extension", 0))),
            )
        ])
        spi0 = self.cm.request("spi", 0)
        self.assertEqual(list(self.cm.iter_port_constraints()), [
            ("spi_0__ss__io",   ["B0"], {}),
            ("spi_0__clk__io",  ["B1"], {}),
            ("spi_0__miso__io", ["B2"], {}),
            ("spi_0__mosi__io", ["B3"], {}),
        ])

    def test_request_clock(self):
        clk100 = self.cm.request("clk100", 0)
        clk50 = self.cm.request("clk50", 0, dir="i")
        clk100_port_p, clk100_port_n, clk50_port = self.cm.iter_ports()
        self.assertEqual(list(self.cm.iter_clock_constraints()), [
            (clk100.i, clk100_port_p, 100e6),
            (clk50.i, clk50_port, 50e6)
        ])

    def test_add_clock(self):
        i2c = self.cm.request("i2c")
        self.cm.add_clock_constraint(i2c.scl.o, 100e3)
        self.assertEqual(list(self.cm.iter_clock_constraints()), [
            (i2c.scl.o, None, 100e3)
        ])

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
                r"^Object None is not a Signal$"):
            self.cm.add_clock_constraint(None, 10e6)

    def test_wrong_clock_frequency(self):
        with self.assertRaisesRegex(TypeError,
                r"^Frequency must be a number, not None$"):
            self.cm.add_clock_constraint(Signal(), None)

    def test_wrong_request_duplicate(self):
        with self.assertRaisesRegex(ResourceError,
                r"^Resource user_led#0 has already been requested$"):
            self.cm.request("user_led", 0)
            self.cm.request("user_led", 0)

    def test_wrong_request_duplicate_physical(self):
        self.cm.add_resources([
            Resource("clk20", 0, Pins("H1", dir="i")),
        ])
        self.cm.request("clk100", 0)
        with self.assertRaisesRegex(ResourceError,
                (r"^Resource component clk20_0 uses physical pin H1, but it is already "
                    r"used by resource component clk100_0 that was requested earlier$")):
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
        clk100 = self.cm.request("clk100")
        with self.assertRaisesRegex(ValueError,
                (r"^Cannot add clock constraint on \(sig clk100_0__i\), which is already "
                    r"constrained to 100000000\.0 Hz$")):
            self.cm.add_clock_constraint(clk100.i, 1e6)
