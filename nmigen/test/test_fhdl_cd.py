from ..fhdl.cd import *
from .tools import *


class ClockDomainCase(FHDLTestCase):
    def test_name(self):
        pix = ClockDomain()
        self.assertEqual(pix.name, "pix")
        cd_pix = ClockDomain()
        self.assertEqual(pix.name, "pix")
        dom = [ClockDomain("foo")][0]
        self.assertEqual(dom.name, "foo")
        with self.assertRaises(ValueError,
                msg="Clock domain name must be specified explicitly"):
            ClockDomain()

    def test_with_reset(self):
        pix = ClockDomain()
        self.assertIsNotNone(pix.clk)
        self.assertIsNotNone(pix.rst)
        self.assertFalse(pix.async_reset)

    def test_without_reset(self):
        pix = ClockDomain(reset_less=True)
        self.assertIsNotNone(pix.clk)
        self.assertIsNone(pix.rst)
        self.assertFalse(pix.async_reset)

    def test_async_reset(self):
        pix = ClockDomain(async_reset=True)
        self.assertIsNotNone(pix.clk)
        self.assertIsNotNone(pix.rst)
        self.assertTrue(pix.async_reset)
