from amaranth.hdl._time import *

from .utils import *


class PeriodTestCase(FHDLTestCase):
    def test_constructor(self):
        self.assertEqual(Period().femtoseconds, 0)

        self.assertEqual(Period(fs=5).femtoseconds, 5)
        self.assertEqual(Period(ps=5).femtoseconds, 5_000)
        self.assertEqual(Period(ns=5).femtoseconds, 5_000_000)
        self.assertEqual(Period(us=5).femtoseconds, 5_000_000_000)
        self.assertEqual(Period(ms=5).femtoseconds, 5_000_000_000_000)
        self.assertEqual(Period( s=5).femtoseconds, 5_000_000_000_000_000)

        self.assertEqual(Period(GHz=5).femtoseconds, 200_000)
        self.assertEqual(Period(MHz=5).femtoseconds, 200_000_000)
        self.assertEqual(Period(kHz=5).femtoseconds, 200_000_000_000)
        self.assertEqual(Period( Hz=5).femtoseconds, 200_000_000_000_000)

    def test_constructor_exceptions(self):
        with self.assertRaisesRegex(TypeError,
                r"^Period accepts at most one argument$"):
            Period(s=5, ms = 3)

        with self.assertRaisesRegex(TypeError,
                r"^foo is not a valid unit$"):
            Period(foo=5)

        with self.assertRaisesRegex(TypeError,
                r"^s value must be a real number$"):
            Period(s="five")

        with self.assertRaisesRegex(ZeroDivisionError,
                r"^Frequency can't be zero$"):
            Period(Hz=0)

        with self.assertRaisesRegex(ValueError,
                r"^Frequency can't be negative$"):
            Period(Hz=-1)

    def test_accessors(self):
        self.assertEqual(Period(s=5).seconds,      5.0)
        self.assertEqual(Period(s=5).milliseconds, 5_000.0)
        self.assertEqual(Period(s=5).microseconds, 5_000_000.0)
        self.assertEqual(Period(s=5).nanoseconds,  5_000_000_000.0)
        self.assertEqual(Period(s=5).picoseconds,  5_000_000_000_000.0)
        self.assertEqual(Period(s=5).femtoseconds, 5_000_000_000_000_000)

        self.assertEqual(Period(GHz=5).gigahertz, 5.0)
        self.assertEqual(Period(GHz=5).megahertz, 5_000.0)
        self.assertEqual(Period(GHz=5).kilohertz, 5_000_000.0)
        self.assertEqual(Period(GHz=5).hertz,     5_000_000_000.0)

    def test_accessor_exceptions(self):
        with self.assertRaisesRegex(ZeroDivisionError,
                r"^Can't calculate the frequency of a zero period$"):
            Period(s=0).hertz

        with self.assertRaisesRegex(ValueError,
                r"^Can't calculate the frequency of a negative period$"):
            Period(s=-1).hertz

    def test_operators(self):
        for a, b in [(3, 5), (3, 3), (5, 3)]:
            self.assertEqual(Period(s=a) <  Period(s=b), a <  b)
            self.assertEqual(Period(s=a) <= Period(s=b), a <= b)
            self.assertEqual(Period(s=a) == Period(s=b), a == b)
            self.assertEqual(Period(s=a) != Period(s=b), a != b)
            self.assertEqual(Period(s=a) >  Period(s=b), a >  b)
            self.assertEqual(Period(s=a) >= Period(s=b), a >= b)

        self.assertEqual(hash(Period(fs=5)), hash(5))

        self.assertFalse(Period())
        self.assertTrue(Period(s=5))

        self.assertEqual(-Period(s=5), Period(s=-5))
        self.assertEqual(+Period(s=5), Period(s=5))
        self.assertEqual(abs(Period(s=-5)), Period(s=5))

        self.assertEqual(Period(s=3) + Period(ms=5), Period(ms=3005))
        self.assertEqual(Period(s=3) - Period(ms=5), Period(ms=2995))
        self.assertEqual(Period(s=3) * 5, Period(s=15))
        self.assertEqual(3 * Period(s=5), Period(s=15))
        self.assertEqual(Period(s=15) / 3, Period(s=5))
        self.assertEqual(Period(s=15) / Period(s=3), 5.0)
        self.assertEqual(Period(s=8) // Period(s=3), 2)
        self.assertEqual(Period(s=8) % Period(s=3), Period(s=2))

    def test_invalid_operands(self):
        with self.assertRaises(TypeError):
            Period(s=5) > 3
        with self.assertRaises(TypeError):
            Period(s=5) >= 3
        with self.assertRaises(TypeError):
            Period(s=5) < 3
        with self.assertRaises(TypeError):
            Period(s=5) <= 3
        self.assertFalse(Period(s=5) == 3)
        self.assertTrue(Period(s=5) != 3)

        with self.assertRaises(TypeError):
            Period(s=5) + 3
        with self.assertRaises(TypeError):
            Period(s=5) - 3
        with self.assertRaises(TypeError):
            Period(s=5) * Period(s=3)
        with self.assertRaises(TypeError):
            Period(s=5) / "three"
        with self.assertRaises(TypeError):
            Period(s=5) // 3
        with self.assertRaises(TypeError):
            Period(s=5) % 3

    def test_str(self):
        self.assertEqual(str(Period( s=5)), "5s")
        self.assertEqual(str(Period(ms=5)), "5ms")
        self.assertEqual(str(Period(us=5)), "5us")
        self.assertEqual(str(Period(ns=5)), "5ns")
        self.assertEqual(str(Period(ps=5)), "5ps")
        self.assertEqual(str(Period(fs=5)), "5fs")

    def test_repr(self):
        self.assertRepr(Period( s=5), "Period(s=5)")
        self.assertRepr(Period(ms=5), "Period(ms=5)")

    def test_format(self):
        with self.assertRaisesRegex(ValueError,
                r"^Invalid format specifier 'foo' for object of type 'Period'"):
            f"{Period(s=5):foo}"

        self.assertEqual(f"{Period(ms=1234):}", "1.234s")
        self.assertEqual(f"{Period(ms=1234):ms}", "1234ms")
        self.assertEqual(f"{Period(ms=1234):.1}", "1.2s")
        self.assertEqual(f"{Period(ms=1234): }", "1.234 s")
        self.assertEqual(f"{Period(ms=1234):10}", "    1.234s")

        self.assertEqual(f"{Period(MHz=1250):.0Hz}", "1250000000Hz")
        self.assertEqual(f"{Period(MHz=1250):.0kHz}", "1250000kHz")
        self.assertEqual(f"{Period(MHz=1250):.0MHz}", "1250MHz")
        self.assertEqual(f"{Period(MHz=1250):.0GHz}", "1GHz")
