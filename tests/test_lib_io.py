from amaranth.hdl import *
from amaranth.hdl.rec import *
from amaranth.sim import *
from amaranth.lib.io import *

from .utils import *


class PinLayoutTestCase(FHDLTestCase):
    def assertLayoutEqual(self, layout, expected):
        casted_layout = {}
        for name, (shape, dir) in layout.items():
            casted_layout[name] = (Shape.cast(shape), dir)

        self.assertEqual(casted_layout, expected)


class PinLayoutCombTestCase(PinLayoutTestCase):
    def test_pin_layout_i(self):
        layout_1 = pin_layout(1, dir="i")
        self.assertLayoutEqual(layout_1.fields, {
            "i": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="i")
        self.assertLayoutEqual(layout_2.fields, {
            "i": ((2, False), DIR_NONE),
        })

    def test_pin_layout_o(self):
        layout_1 = pin_layout(1, dir="o")
        self.assertLayoutEqual(layout_1.fields, {
            "o": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="o")
        self.assertLayoutEqual(layout_2.fields, {
            "o": ((2, False), DIR_NONE),
        })

    def test_pin_layout_oe(self):
        layout_1 = pin_layout(1, dir="oe")
        self.assertLayoutEqual(layout_1.fields, {
            "o":  ((1, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="oe")
        self.assertLayoutEqual(layout_2.fields, {
            "o":  ((2, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

    def test_pin_layout_io(self):
        layout_1 = pin_layout(1, dir="io")
        self.assertLayoutEqual(layout_1.fields, {
            "i":  ((1, False), DIR_NONE),
            "o":  ((1, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="io")
        self.assertLayoutEqual(layout_2.fields, {
            "i":  ((2, False), DIR_NONE),
            "o":  ((2, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })


class PinLayoutSDRTestCase(PinLayoutTestCase):
    def test_pin_layout_i(self):
        layout_1 = pin_layout(1, dir="i", xdr=1)
        self.assertLayoutEqual(layout_1.fields, {
            "i_clk": ((1, False), DIR_NONE),
            "i": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="i", xdr=1)
        self.assertLayoutEqual(layout_2.fields, {
            "i_clk": ((1, False), DIR_NONE),
            "i": ((2, False), DIR_NONE),
        })

    def test_pin_layout_o(self):
        layout_1 = pin_layout(1, dir="o", xdr=1)
        self.assertLayoutEqual(layout_1.fields, {
            "o_clk": ((1, False), DIR_NONE),
            "o": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="o", xdr=1)
        self.assertLayoutEqual(layout_2.fields, {
            "o_clk": ((1, False), DIR_NONE),
            "o": ((2, False), DIR_NONE),
        })

    def test_pin_layout_oe(self):
        layout_1 = pin_layout(1, dir="oe", xdr=1)
        self.assertLayoutEqual(layout_1.fields, {
            "o_clk": ((1, False), DIR_NONE),
            "o":  ((1, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="oe", xdr=1)
        self.assertLayoutEqual(layout_2.fields, {
            "o_clk": ((1, False), DIR_NONE),
            "o":  ((2, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

    def test_pin_layout_io(self):
        layout_1 = pin_layout(1, dir="io", xdr=1)
        self.assertLayoutEqual(layout_1.fields, {
            "i_clk": ((1, False), DIR_NONE),
            "i":  ((1, False), DIR_NONE),
            "o_clk": ((1, False), DIR_NONE),
            "o":  ((1, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="io", xdr=1)
        self.assertLayoutEqual(layout_2.fields, {
            "i_clk": ((1, False), DIR_NONE),
            "i":  ((2, False), DIR_NONE),
            "o_clk": ((1, False), DIR_NONE),
            "o":  ((2, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })


class PinLayoutDDRTestCase(PinLayoutTestCase):
    def test_pin_layout_i(self):
        layout_1 = pin_layout(1, dir="i", xdr=2)
        self.assertLayoutEqual(layout_1.fields, {
            "i_clk": ((1, False), DIR_NONE),
            "i0": ((1, False), DIR_NONE),
            "i1": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="i", xdr=2)
        self.assertLayoutEqual(layout_2.fields, {
            "i_clk": ((1, False), DIR_NONE),
            "i0": ((2, False), DIR_NONE),
            "i1": ((2, False), DIR_NONE),
        })

    def test_pin_layout_o(self):
        layout_1 = pin_layout(1, dir="o", xdr=2)
        self.assertLayoutEqual(layout_1.fields, {
            "o_clk": ((1, False), DIR_NONE),
            "o0": ((1, False), DIR_NONE),
            "o1": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="o", xdr=2)
        self.assertLayoutEqual(layout_2.fields, {
            "o_clk": ((1, False), DIR_NONE),
            "o0": ((2, False), DIR_NONE),
            "o1": ((2, False), DIR_NONE),
        })

    def test_pin_layout_oe(self):
        layout_1 = pin_layout(1, dir="oe", xdr=2)
        self.assertLayoutEqual(layout_1.fields, {
            "o_clk": ((1, False), DIR_NONE),
            "o0": ((1, False), DIR_NONE),
            "o1": ((1, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="oe", xdr=2)
        self.assertLayoutEqual(layout_2.fields, {
            "o_clk": ((1, False), DIR_NONE),
            "o0": ((2, False), DIR_NONE),
            "o1": ((2, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

    def test_pin_layout_io(self):
        layout_1 = pin_layout(1, dir="io", xdr=2)
        self.assertLayoutEqual(layout_1.fields, {
            "i_clk": ((1, False), DIR_NONE),
            "i0": ((1, False), DIR_NONE),
            "i1": ((1, False), DIR_NONE),
            "o_clk": ((1, False), DIR_NONE),
            "o0": ((1, False), DIR_NONE),
            "o1": ((1, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })

        layout_2 = pin_layout(2, dir="io", xdr=2)
        self.assertLayoutEqual(layout_2.fields, {
            "i_clk": ((1, False), DIR_NONE),
            "i0": ((2, False), DIR_NONE),
            "i1": ((2, False), DIR_NONE),
            "o_clk": ((1, False), DIR_NONE),
            "o0": ((2, False), DIR_NONE),
            "o1": ((2, False), DIR_NONE),
            "oe": ((1, False), DIR_NONE),
        })


class PinTestCase(FHDLTestCase):
    def test_attributes(self):
        pin = Pin(2, dir="io", xdr=2)
        self.assertEqual(pin.width, 2)
        self.assertEqual(pin.dir,   "io")
        self.assertEqual(pin.xdr,   2)
