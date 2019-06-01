from .. import *
from ..hdl.rec import *
from ..lib.io import *
from ..build.dsl import *
from ..build.res import *
from .tools import *


class ConstraintManagerTestCase(FHDLTestCase):
    def setUp(self):
        self.resources = [
            Resource("clk100", 0, DiffPairs("H1", "H2", dir="i")),
            Resource("clk50", 0, Pins("K1")),
            Resource("user_led", 0, Pins("A0", dir="o")),
            Resource("i2c", 0,
                Subsignal("scl", Pins("N10", dir="o")),
                Subsignal("sda", Pins("N11"))
            )
        ]
        self.cm = ConstraintManager(self.resources, [])

    def test_basic(self):
        self.clocks = [
            ("clk100",      100),
            (("clk50", 0),  50),
        ]
        self.cm = ConstraintManager(self.resources, self.clocks)
        self.assertEqual(self.cm.resources, {
            ("clk100",   0): self.resources[0],
            ("clk50",    0): self.resources[1],
            ("user_led", 0): self.resources[2],
            ("i2c",      0): self.resources[3]
        })
        self.assertEqual(self.cm.clocks, {
            ("clk100", 0): 100,
            ("clk50",  0): 50,
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
        self.assertIs(user_led.o, ports[0])

        self.assertEqual(list(self.cm.iter_port_constraints()), [
            ("user_led_0__o", ["A0"], [])
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
        self.assertIs(i2c.scl.o, ports[0]),
        self.assertEqual(ports[1].name, "i2c_0__sda_io")
        self.assertEqual(ports[1].nbits, 1)

        self.assertEqual(self.cm._tristates, [(i2c.sda, ports[1])])
        self.assertEqual(list(self.cm.iter_port_constraints()), [
            ("i2c_0__scl__o", ["N10"], []),
            ("i2c_0__sda_io", ["N11"], [])
        ])

    def test_request_diffpairs(self):
        clk100 = self.cm.request("clk100", 0)
        self.assertIsInstance(clk100, Pin)
        self.assertEqual(clk100.dir, "i")
        self.assertEqual(clk100.width, 1)

        ports = list(self.cm.iter_ports())
        self.assertEqual(len(ports), 2)
        p, n = ports
        self.assertEqual(p.name, "clk100_0_p")
        self.assertEqual(p.nbits, clk100.width)
        self.assertEqual(n.name, "clk100_0_n")
        self.assertEqual(n.nbits, clk100.width)

        self.assertEqual(self.cm._diffpairs, [(clk100, p, n)])
        self.assertEqual(list(self.cm.iter_port_constraints()), [
            ("clk100_0_p", ["H1"], []),
            ("clk100_0_n", ["H2"], [])
        ])

    def test_add_clock(self):
        self.cm.add_clock("clk100", 0, 10e6)
        self.assertEqual(self.cm.clocks["clk100", 0], 10e6)
        self.cm.add_clock("clk50", 0, 5e6)

        clk100 = self.cm.request("clk100", 0)
        clk50 = self.cm.request("clk50", 0, dir="i")
        self.assertEqual(list(sorted(self.cm.iter_clock_constraints())), [
            ("clk100_0_p", 10e6),
            ("clk50_0__i", 5e6)
        ])

    def test_wrong_resources(self):
        with self.assertRaises(TypeError, msg="Object 'wrong' is not a Resource"):
            self.cm.add_resources(['wrong'])

    def test_wrong_resources_duplicate(self):
        with self.assertRaises(NameError,
                msg="Trying to add (resource user_led 0 (pins o A1) ), but "
                    "(resource user_led 0 (pins o A0) ) has the same name and number"):
            self.cm.add_resources([Resource("user_led", 0, Pins("A1", dir="o"))])

    def test_wrong_lookup(self):
        with self.assertRaises(NameError,
                msg="Resource user_led#1 does not exist"):
            r = self.cm.lookup("user_led", 1)

    def test_wrong_frequency_subsignals(self):
        with self.assertRaises(ConstraintError,
                msg="Cannot constrain frequency of resource i2c#0 because "
                    "it has subsignals"):
            self.cm.add_clock("i2c", 0, 10e6)

    def test_wrong_frequency_tristate(self):
        with self.assertRaises(ConstraintError,
                msg="Cannot constrain frequency of resource clk50#0 because "
                    "it has been requested as a tristate buffer"):
            self.cm.add_clock("clk50", 0, 20e6)
            clk50 = self.cm.request("clk50", 0)
            list(self.cm.iter_clock_constraints())

    def test_wrong_frequency_duplicate(self):
        with self.assertRaises(ConstraintError,
                msg="Resource clk100#0 is already constrained to a frequency of 10.000000 MHz"):
            self.cm.add_clock("clk100", 0, 10e6)
            self.cm.add_clock("clk100", 0, 5e6)

    def test_wrong_request_duplicate(self):
        with self.assertRaises(ConstraintError,
                msg="Resource user_led#0 has already been requested"):
            self.cm.request("user_led", 0)
            self.cm.request("user_led", 0)

    def test_wrong_request_with_dir(self):
        with self.assertRaises(TypeError,
                msg="Direction must be one of \"i\", \"o\" or \"io\", not 'wrong'"):
            user_led = self.cm.request("user_led", 0, dir="wrong")

    def test_wrong_request_with_dir_io(self):
        with self.assertRaises(ValueError,
                msg="Direction of (pins o A0) cannot be changed from \"o\" to \"i\"; direction "
                    "can be changed from \"io\" to \"i\" or from \"io\"to \"o\""):
            user_led = self.cm.request("user_led", 0, dir="i")

    def test_wrong_request_with_dir_dict(self):
        with self.assertRaises(TypeError,
                msg="Directions must be a dict, not 'i', because (resource i2c 0 (subsignal scl "
                    "(pins o N10) ) (subsignal sda (pins io N11) ) ) has subsignals"):
            i2c = self.cm.request("i2c", 0, dir="i")

    def test_wrong_request_with_wrong_xdr(self):
        with self.assertRaises(ValueError,
                msg="Data rate of (pins o A0) must be a positive integer, not 0"):
            user_led = self.cm.request("user_led", 0, xdr=0)

    def test_wrong_request_with_xdr_dict(self):
        with self.assertRaises(TypeError,
                msg="Data rate must be a dict, not 2, because (resource i2c 0 (subsignal scl "
                    "(pins o N10) ) (subsignal sda (pins io N11) ) ) has subsignals"):
            i2c = self.cm.request("i2c", 0, xdr=2)
