import warnings

from amaranth.hdl import *
from amaranth.sim import *
from amaranth.lib.io import *
from amaranth.lib.wiring import *

from .utils import *


class PinSignatureTestCase(FHDLTestCase):
    def assertSignatureEqual(self, signature, expected):
        self.assertEqual(signature.members, Signature(expected).members)


class PinSignatureCombTestCase(PinSignatureTestCase):
    def test_signature_i(self):
        sig_1 = Pin.Signature(1, dir="i")
        self.assertSignatureEqual(sig_1, {
            "i": In(1),
        })

        sig_2 = Pin.Signature(2, dir="i")
        self.assertSignatureEqual(sig_2, {
            "i": In(2),
        })

    def test_signature_o(self):
        sig_1 = Pin.Signature(1, dir="o")
        self.assertSignatureEqual(sig_1, {
            "o": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="o")
        self.assertSignatureEqual(sig_2, {
            "o": Out(2),
        })

    def test_signature_oe(self):
        sig_1 = Pin.Signature(1, dir="oe")
        self.assertSignatureEqual(sig_1, {
            "o":  Out(1),
            "oe": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="oe")
        self.assertSignatureEqual(sig_2, {
            "o":  Out(2),
            "oe": Out(1),
        })

    def test_signature_io(self):
        sig_1 = Pin.Signature(1, dir="io")
        self.assertSignatureEqual(sig_1, {
            "i":  In(1),
            "o":  Out(1),
            "oe": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="io")
        self.assertSignatureEqual(sig_2, {
            "i":  In(2),
            "o":  Out(2),
            "oe": Out(1),
        })


class PinSignatureSDRTestCase(PinSignatureTestCase):
    def test_signature_i(self):
        sig_1 = Pin.Signature(1, dir="i", xdr=1)
        self.assertSignatureEqual(sig_1, {
            "i_clk": Out(1),
            "i": In(1),
        })

        sig_2 = Pin.Signature(2, dir="i", xdr=1)
        self.assertSignatureEqual(sig_2, {
            "i_clk": Out(1),
            "i": In(2),
        })

    def test_signature_o(self):
        sig_1 = Pin.Signature(1, dir="o", xdr=1)
        self.assertSignatureEqual(sig_1, {
            "o_clk": Out(1),
            "o": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="o", xdr=1)
        self.assertSignatureEqual(sig_2, {
            "o_clk": Out(1),
            "o": Out(2),
        })

    def test_signature_oe(self):
        sig_1 = Pin.Signature(1, dir="oe", xdr=1)
        self.assertSignatureEqual(sig_1, {
            "o_clk": Out(1),
            "o":  Out(1),
            "oe": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="oe", xdr=1)
        self.assertSignatureEqual(sig_2, {
            "o_clk": Out(1),
            "o":  Out(2),
            "oe": Out(1),
        })

    def test_signature_io(self):
        sig_1 = Pin.Signature(1, dir="io", xdr=1)
        self.assertSignatureEqual(sig_1, {
            "i_clk": Out(1),
            "i":  In(1),
            "o_clk": Out(1),
            "o":  Out(1),
            "oe": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="io", xdr=1)
        self.assertSignatureEqual(sig_2, {
            "i_clk": Out(1),
            "i":  In(2),
            "o_clk": Out(1),
            "o":  Out(2),
            "oe": Out(1),
        })


class PinSignatureDDRTestCase(PinSignatureTestCase):
    def test_signature_i(self):
        sig_1 = Pin.Signature(1, dir="i", xdr=2)
        self.assertSignatureEqual(sig_1, {
            "i_clk": Out(1),
            "i0": In(1),
            "i1": In(1),
        })

        sig_2 = Pin.Signature(2, dir="i", xdr=2)
        self.assertSignatureEqual(sig_2, {
            "i_clk": Out(1),
            "i0": In(2),
            "i1": In(2),
        })

    def test_signature_o(self):
        sig_1 = Pin.Signature(1, dir="o", xdr=2)
        self.assertSignatureEqual(sig_1, {
            "o_clk": Out(1),
            "o0": Out(1),
            "o1": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="o", xdr=2)
        self.assertSignatureEqual(sig_2, {
            "o_clk": Out(1),
            "o0": Out(2),
            "o1": Out(2),
        })

    def test_signature_oe(self):
        sig_1 = Pin.Signature(1, dir="oe", xdr=2)
        self.assertSignatureEqual(sig_1, {
            "o_clk": Out(1),
            "o0": Out(1),
            "o1": Out(1),
            "oe": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="oe", xdr=2)
        self.assertSignatureEqual(sig_2, {
            "o_clk": Out(1),
            "o0": Out(2),
            "o1": Out(2),
            "oe": Out(1),
        })

    def test_signature_io(self):
        sig_1 = Pin.Signature(1, dir="io", xdr=2)
        self.assertSignatureEqual(sig_1, {
            "i_clk": Out(1),
            "i0": In(1),
            "i1": In(1),
            "o_clk": Out(1),
            "o0": Out(1),
            "o1": Out(1),
            "oe": Out(1),
        })

        sig_2 = Pin.Signature(2, dir="io", xdr=2)
        self.assertSignatureEqual(sig_2, {
            "i_clk": Out(1),
            "i0": In(2),
            "i1": In(2),
            "o_clk": Out(1),
            "o0": Out(2),
            "o1": Out(2),
            "oe": Out(1),
        })


class PinSignatureReprCase(FHDLTestCase):
    def test_repr(self):
        sig_0 = Pin.Signature(1, dir="i")
        self.assertRepr(sig_0, "Pin.Signature(1, dir='i')")
        sig_0 = Pin.Signature(2, dir="o", xdr=1)
        self.assertRepr(sig_0, "Pin.Signature(2, dir='o', xdr=1)")
        sig_0 = Pin.Signature(3, dir="io", xdr=2)
        self.assertRepr(sig_0, "Pin.Signature(3, dir='io', xdr=2)")


class PinTestCase(FHDLTestCase):
    def test_attributes(self):
        pin = Pin(2, dir="io", xdr=2)
        self.assertEqual(pin.width, 2)
        self.assertEqual(pin.dir,   "io")
        self.assertEqual(pin.xdr,   2)
        self.assertEqual(pin.signature.width, 2)
        self.assertEqual(pin.signature.dir,   "io")
        self.assertEqual(pin.signature.xdr,   2)
        self.assertEqual(pin.name, "pin")
        self.assertEqual(pin.path, ("pin",))
        self.assertEqual(pin.i0.name, "pin__i0")
        pin = Pin(2, dir="io", xdr=2, name="testpin")
        self.assertEqual(pin.name, "testpin")
        self.assertEqual(pin.path, ("testpin",))
        self.assertEqual(pin.i0.name, "testpin__i0")
        pin = Pin(2, dir="io", xdr=2, path=["a", "b"])
        self.assertEqual(pin.name, "b")
        self.assertEqual(pin.path, ("a", "b"))
        self.assertEqual(pin.i0.name, "a__b__i0")
