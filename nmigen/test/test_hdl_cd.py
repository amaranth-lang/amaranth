from ..hdl.cd import *
from .tools import *


class ClockDomainTestCase(FHDLTestCase):
    def test_name(self):
        sync = ClockDomain()
        self.assertEqual(sync.name, "sync")
        self.assertEqual(sync.clk.name, "clk")
        self.assertEqual(sync.rst.name, "rst")
        pix = ClockDomain()
        self.assertEqual(pix.name, "pix")
        self.assertEqual(pix.clk.name, "pix_clk")
        self.assertEqual(pix.rst.name, "pix_rst")
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

    def test_rename(self):
        sync = ClockDomain()
        self.assertEqual(sync.name, "sync")
        self.assertEqual(sync.clk.name, "clk")
        self.assertEqual(sync.rst.name, "rst")
        sync.rename("pix")
        self.assertEqual(sync.name, "pix")
        self.assertEqual(sync.clk.name, "pix_clk")
        self.assertEqual(sync.rst.name, "pix_rst")

    def test_rename_reset_less(self):
        sync = ClockDomain(reset_less=True)
        self.assertEqual(sync.name, "sync")
        self.assertEqual(sync.clk.name, "clk")
        sync.rename("pix")
        self.assertEqual(sync.name, "pix")
        self.assertEqual(sync.clk.name, "pix_clk")
