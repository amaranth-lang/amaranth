from amaranth.hdl import *
from amaranth.sim import *
from amaranth.lib.io import *
from amaranth.lib.wiring import *

from .utils import *


class DirectionTestCase(FHDLTestCase):
    def test_or(self):
        self.assertIs(Direction.Input | Direction.Input, Direction.Input)
        self.assertIs(Direction.Input | Direction.Output, Direction.Bidir)
        self.assertIs(Direction.Input | Direction.Bidir, Direction.Bidir)
        self.assertIs(Direction.Output | Direction.Input, Direction.Bidir)
        self.assertIs(Direction.Output | Direction.Output, Direction.Output)
        self.assertIs(Direction.Output | Direction.Bidir, Direction.Bidir)
        self.assertIs(Direction.Bidir | Direction.Input, Direction.Bidir)
        self.assertIs(Direction.Bidir | Direction.Output, Direction.Bidir)
        self.assertIs(Direction.Bidir | Direction.Bidir, Direction.Bidir)
        with self.assertRaises(TypeError):
            Direction.Bidir | 3

    def test_and(self):
        self.assertIs(Direction.Input & Direction.Input, Direction.Input)
        self.assertIs(Direction.Input & Direction.Bidir, Direction.Input)
        self.assertIs(Direction.Output & Direction.Output, Direction.Output)
        self.assertIs(Direction.Output & Direction.Bidir, Direction.Output)
        self.assertIs(Direction.Bidir & Direction.Input, Direction.Input)
        self.assertIs(Direction.Bidir & Direction.Output, Direction.Output)
        self.assertIs(Direction.Bidir & Direction.Bidir, Direction.Bidir)
        with self.assertRaisesRegex(ValueError,
                r"Cannot combine input port with output port"):
            Direction.Output & Direction.Input
        with self.assertRaisesRegex(ValueError,
                r"Cannot combine input port with output port"):
            Direction.Input & Direction.Output
        with self.assertRaises(TypeError):
            Direction.Bidir & 3


class SingleEndedPortTestCase(FHDLTestCase):
    def test_construct(self):
        io = IOPort(4)
        port = SingleEndedPort(io)
        self.assertIs(port.io, io)
        self.assertEqual(port.invert, (False, False, False, False))
        self.assertEqual(port.direction, Direction.Bidir)
        self.assertEqual(len(port), 4)
        self.assertRepr(port, "SingleEndedPort((io-port io), invert=False, direction=Direction.Bidir)")
        port = SingleEndedPort(io, invert=True, direction='i')
        self.assertEqual(port.invert, (True, True, True, True))
        self.assertRepr(port, "SingleEndedPort((io-port io), invert=True, direction=Direction.Input)")
        port = SingleEndedPort(io, invert=[True, False, True, False], direction=Direction.Output)
        self.assertIsInstance(port.invert, tuple)
        self.assertEqual(port.invert, (True, False, True, False))
        self.assertRepr(port, "SingleEndedPort((io-port io), invert=(True, False, True, False), direction=Direction.Output)")

    def test_construct_wrong(self):
        io = IOPort(4)
        sig = Signal(4)
        with self.assertRaisesRegex(TypeError,
                r"^Object \(sig sig\) cannot be converted to an IO value$"):
            SingleEndedPort(sig)
        with self.assertRaisesRegex(TypeError,
                r"^'invert' must be a bool or iterable of bool, not 3$"):
            SingleEndedPort(io, invert=3)
        with self.assertRaisesRegex(TypeError,
                r"^'invert' must be a bool or iterable of bool, not \[1, 2, 3, 4\]$"):
            SingleEndedPort(io, invert=[1, 2, 3, 4])
        with self.assertRaisesRegex(ValueError,
                r"^Length of 'invert' \(5\) doesn't match length of 'io' \(4\)$"):
            SingleEndedPort(io, invert=[False, False, False, False, False])
        with self.assertRaisesRegex(ValueError,
                r"^'bidir' is not a valid Direction$"):
            SingleEndedPort(io, direction="bidir")

    def test_slice(self):
        io = IOPort(8)
        port = SingleEndedPort(io, invert=(True, False, False, True, True, False, False, True), direction="o")
        self.assertRepr(port[2:5], "SingleEndedPort((io-slice (io-port io) 2:5), invert=(False, True, True), direction=Direction.Output)")
        self.assertRepr(port[7], "SingleEndedPort((io-slice (io-port io) 7:8), invert=True, direction=Direction.Output)")

    def test_cat(self):
        ioa = IOPort(3)
        iob = IOPort(2)
        porta = SingleEndedPort(ioa, direction=Direction.Input)
        portb = SingleEndedPort(iob, invert=True, direction=Direction.Input)
        cport = porta + portb
        self.assertRepr(cport, "SingleEndedPort((io-cat (io-port ioa) (io-port iob)), invert=(False, False, False, True, True), direction=Direction.Input)")
        with self.assertRaises(TypeError):
            porta + iob

    def test_invert(self):
        io = IOPort(4)
        port = SingleEndedPort(io, invert=[True, False, True, False], direction=Direction.Output)
        iport = ~port
        self.assertRepr(iport, "SingleEndedPort((io-port io), invert=(False, True, False, True), direction=Direction.Output)")


class DifferentialPortTestCase(FHDLTestCase):
    def test_construct(self):
        iop = IOPort(4)
        ion = IOPort(4)
        port = DifferentialPort(iop, ion)
        self.assertIs(port.p, iop)
        self.assertIs(port.n, ion)
        self.assertEqual(port.invert, (False, False, False, False))
        self.assertEqual(port.direction, Direction.Bidir)
        self.assertEqual(len(port), 4)
        self.assertRepr(port, "DifferentialPort((io-port iop), (io-port ion), invert=False, direction=Direction.Bidir)")
        port = DifferentialPort(iop, ion, invert=True, direction='i')
        self.assertEqual(port.invert, (True, True, True, True))
        self.assertRepr(port, "DifferentialPort((io-port iop), (io-port ion), invert=True, direction=Direction.Input)")
        port = DifferentialPort(iop, ion, invert=[True, False, True, False], direction=Direction.Output)
        self.assertIsInstance(port.invert, tuple)
        self.assertEqual(port.invert, (True, False, True, False))
        self.assertRepr(port, "DifferentialPort((io-port iop), (io-port ion), invert=(True, False, True, False), direction=Direction.Output)")

    def test_construct_wrong(self):
        iop = IOPort(4)
        ion = IOPort(4)
        sig = Signal(4)
        with self.assertRaisesRegex(TypeError,
                r"^Object \(sig sig\) cannot be converted to an IO value$"):
            DifferentialPort(iop, sig)
        with self.assertRaisesRegex(TypeError,
                r"^Object \(sig sig\) cannot be converted to an IO value$"):
            DifferentialPort(sig, ion)
        with self.assertRaisesRegex(ValueError,
                r"^Length of 'p' \(4\) doesn't match length of 'n' \(3\)$"):
            DifferentialPort(iop, ion[:3])
        with self.assertRaisesRegex(TypeError,
                r"^'invert' must be a bool or iterable of bool, not 3$"):
            DifferentialPort(iop, ion, invert=3)
        with self.assertRaisesRegex(TypeError,
                r"^'invert' must be a bool or iterable of bool, not \[1, 2, 3, 4\]$"):
            DifferentialPort(iop, ion, invert=[1, 2, 3, 4])
        with self.assertRaisesRegex(ValueError,
                r"^Length of 'invert' \(5\) doesn't match length of 'p' \(4\)$"):
            DifferentialPort(iop, ion, invert=[False, False, False, False, False])
        with self.assertRaisesRegex(ValueError,
                r"^'bidir' is not a valid Direction$"):
            DifferentialPort(iop, ion, direction="bidir")

    def test_slice(self):
        iop = IOPort(8)
        ion = IOPort(8)
        port = DifferentialPort(iop, ion, invert=(True, False, False, True, True, False, False, True), direction="o")
        self.assertRepr(port[2:5], "DifferentialPort((io-slice (io-port iop) 2:5), (io-slice (io-port ion) 2:5), invert=(False, True, True), direction=Direction.Output)")
        self.assertRepr(port[7], "DifferentialPort((io-slice (io-port iop) 7:8), (io-slice (io-port ion) 7:8), invert=True, direction=Direction.Output)")

    def test_cat(self):
        ioap = IOPort(3)
        ioan = IOPort(3)
        iobp = IOPort(2)
        iobn = IOPort(2)
        porta = DifferentialPort(ioap, ioan, direction=Direction.Input)
        portb = DifferentialPort(iobp, iobn, invert=True, direction=Direction.Input)
        cport = porta + portb
        self.assertRepr(cport, "DifferentialPort((io-cat (io-port ioap) (io-port iobp)), (io-cat (io-port ioan) (io-port iobn)), invert=(False, False, False, True, True), direction=Direction.Input)")
        with self.assertRaises(TypeError):
            porta + SingleEndedPort(ioap)

    def test_invert(self):
        iop = IOPort(4)
        ion = IOPort(4)
        port = DifferentialPort(iop, ion, invert=[True, False, True, False], direction=Direction.Output)
        iport = ~port
        self.assertRepr(iport, "DifferentialPort((io-port iop), (io-port ion), invert=(False, True, False, True), direction=Direction.Output)")


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
        self.assertEqual(pin.name, "a__b")
        self.assertEqual(pin.path, ("a", "b"))
        self.assertEqual(pin.i0.name, "a__b__i0")
