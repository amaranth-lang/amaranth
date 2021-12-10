from amaranth.hdl.cd import *

from .utils import *


class ClockDomainTestCase(FHDLTestCase):
    def test_name(self):
        sync = ClockDomain()
        self.assertEqual(sync.name, "sync")
        self.assertEqual(sync.clk.name, "clk")
        self.assertEqual(sync.rst.name, "rst")
        self.assertEqual(sync.local, False)
        pix = ClockDomain()
        self.assertEqual(pix.name, "pix")
        self.assertEqual(pix.clk.name, "pix_clk")
        self.assertEqual(pix.rst.name, "pix_rst")
        cd_pix = ClockDomain()
        self.assertEqual(cd_pix.name, "pix")
        dom = [ClockDomain("foo")][0]
        self.assertEqual(dom.name, "foo")
        with self.assertRaisesRegex(ValueError,
                r"^Clock domain name must be specified explicitly$"):
            ClockDomain()
        cd_reset = ClockDomain(local=True)
        self.assertEqual(cd_reset.local, True)

    def test_edge(self):
        sync = ClockDomain()
        self.assertEqual(sync.clk_edge, "pos")
        sync = ClockDomain(clk_edge="pos")
        self.assertEqual(sync.clk_edge, "pos")
        sync = ClockDomain(clk_edge="neg")
        self.assertEqual(sync.clk_edge, "neg")

    def test_edge_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"^Domain clock edge must be one of 'pos' or 'neg', not 'xxx'$"):
            ClockDomain("sync", clk_edge="xxx")

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

    def test_wrong_name_comb(self):
        with self.assertRaisesRegex(ValueError,
                r"^Domain 'comb' may not be clocked$"):
            comb = ClockDomain()
