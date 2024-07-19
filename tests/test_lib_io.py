# amaranth: UnusedElaboratable=no

from amaranth.hdl import *
from amaranth.sim import *
from amaranth.hdl._ir import build_netlist
from amaranth.lib.io import *
from amaranth.lib.wiring import *
from amaranth.lib import wiring, data
from amaranth._utils import _ignore_deprecated

from .utils import *


class DirectionTestCase(FHDLTestCase):
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

    def test_empty(self):
        io = IOPort(1)
        port = SingleEndedPort(io, invert=False)
        eport = port[0:0]
        self.assertRepr(eport, "SingleEndedPort((io-slice (io-port io) 0:0), invert=False, direction=Direction.Bidir)")


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

    def test_empty(self):
        iop = IOPort(1)
        ion = IOPort(1)
        port = DifferentialPort(iop, ion, invert=False)
        eport = port[0:0]
        self.assertRepr(eport, "DifferentialPort((io-slice (io-port iop) 0:0), (io-slice (io-port ion) 0:0), invert=False, direction=Direction.Bidir)")


class SimulationPortTestCase(FHDLTestCase):
    def test_construct(self):
        port_io = SimulationPort("io", 2)
        self.assertEqual(port_io.direction, Direction.Bidir)
        self.assertEqual(len(port_io), 2)
        self.assertEqual(port_io.invert, (False, False))
        self.assertIsInstance(port_io.i, Signal)
        self.assertEqual(port_io.i.shape(), unsigned(2))
        self.assertIsInstance(port_io.o, Signal)
        self.assertEqual(port_io.o.shape(), unsigned(2))
        self.assertEqual(port_io.o.init, 0)
        self.assertIsInstance(port_io.oe, Signal)
        self.assertEqual(port_io.oe.shape(), unsigned(2))
        self.assertEqual(port_io.oe.init, 0)
        self.assertRepr(port_io, "SimulationPort(i=(sig port_io__i), o=(sig port_io__o), oe=(sig port_io__oe), invert=False, direction=Direction.Bidir)")

        port_i = SimulationPort("i", 3, invert=True)
        self.assertEqual(port_i.direction, Direction.Input)
        self.assertEqual(len(port_i), 3)
        self.assertEqual(port_i.invert, (True, True, True))
        self.assertIsInstance(port_i.i, Signal)
        self.assertEqual(port_i.i.shape(), unsigned(3))
        with self.assertRaisesRegex(AttributeError,
                r"^Simulation port with input direction does not have an output signal$"):
            port_i.o
        with self.assertRaisesRegex(AttributeError,
                r"^Simulation port with input direction does not have an output enable signal$"):
            port_i.oe
        self.assertRepr(port_i, "SimulationPort(i=(sig port_i__i), invert=True, direction=Direction.Input)")

        port_o = SimulationPort("o", 2, invert=(True, False))
        self.assertEqual(port_o.direction, Direction.Output)
        self.assertEqual(len(port_o), 2)
        self.assertEqual(port_o.invert, (True, False))
        with self.assertRaisesRegex(AttributeError,
                r"^Simulation port with output direction does not have an input signal$"):
            port_o.i
        self.assertIsInstance(port_o.o, Signal)
        self.assertEqual(port_o.o.shape(), unsigned(2))
        self.assertEqual(port_o.o.init, 0)
        self.assertIsInstance(port_o.oe, Signal)
        self.assertEqual(port_o.oe.shape(), unsigned(2))
        self.assertEqual(port_o.oe.init, 0b11)
        self.assertRepr(port_o, "SimulationPort(o=(sig port_o__o), oe=(sig port_o__oe), invert=(True, False), direction=Direction.Output)")

    def test_construct_empty(self):
        port_i = SimulationPort("i", 0, invert=True)
        self.assertEqual(port_i.direction, Direction.Input)
        self.assertEqual(len(port_i), 0)
        self.assertEqual(port_i.invert, ())
        self.assertIsInstance(port_i.i, Signal)
        self.assertEqual(port_i.i.shape(), unsigned(0))
        self.assertRepr(port_i, "SimulationPort(i=(sig port_i__i), invert=False, direction=Direction.Input)")

    def test_name(self):
        port = SimulationPort("io", 2, name="nyaa")
        self.assertRepr(port, "SimulationPort(i=(sig nyaa__i), o=(sig nyaa__o), oe=(sig nyaa__oe), invert=False, direction=Direction.Bidir)")

    def test_name_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Name must be a string, not 1$"):
            SimulationPort("io", 1, name=1)

    def test_construct_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Width must be a non-negative integer, not 'a'$"):
            SimulationPort("io", "a")
        with self.assertRaisesRegex(TypeError,
                r"^Width must be a non-negative integer, not -1$"):
            SimulationPort("io", -1)
        with self.assertRaisesRegex(TypeError,
                r"^'invert' must be a bool or iterable of bool, not 3$"):
            SimulationPort("io", 1, invert=3)
        with self.assertRaisesRegex(TypeError,
                r"^'invert' must be a bool or iterable of bool, not \[1, 2\]$"):
            SimulationPort("io", 2, invert=[1, 2])
        with self.assertRaisesRegex(ValueError,
                r"^Length of 'invert' \(2\) doesn't match port width \(1\)$"):
            SimulationPort("io", 1, invert=(False, True))

    def test_slice(self):
        port_io = SimulationPort("io", 2)
        self.assertRepr(port_io[0], "SimulationPort(i=(slice (sig port_io__i) 0:1), o=(slice (sig port_io__o) 0:1), oe=(slice (sig port_io__oe) 0:1), invert=False, direction=Direction.Bidir)")

        port_i = SimulationPort("i", 3, invert=True)
        self.assertRepr(port_i[1:3], "SimulationPort(i=(slice (sig port_i__i) 1:3), invert=True, direction=Direction.Input)")

        port_o = SimulationPort("o", 2, invert=(True, False))
        self.assertRepr(port_o[1], "SimulationPort(o=(slice (sig port_o__o) 1:2), oe=(slice (sig port_o__oe) 1:2), invert=False, direction=Direction.Output)")

    def test_invert(self):
        port_io = SimulationPort("io", 2)
        self.assertRepr(~port_io, "SimulationPort(i=(sig port_io__i), o=(sig port_io__o), oe=(sig port_io__oe), invert=True, direction=Direction.Bidir)")

        port_i = SimulationPort("i", 3, invert=True)
        self.assertRepr(~port_i, "SimulationPort(i=(sig port_i__i), invert=False, direction=Direction.Input)")

        port_o = SimulationPort("o", 2, invert=(True, False))
        self.assertRepr(~port_o, "SimulationPort(o=(sig port_o__o), oe=(sig port_o__oe), invert=(False, True), direction=Direction.Output)")

    def test_add(self):
        port_io = SimulationPort("io", 2)
        port_io2 = SimulationPort("io", 2)
        port_i = SimulationPort("i", 3, invert=True)
        port_o = SimulationPort("o", 2, invert=(True, False))

        self.assertRepr(port_io + port_io2, "SimulationPort(i=(cat (sig port_io__i) (sig port_io2__i)), o=(cat (sig port_io__o) (sig port_io2__o)), oe=(cat (sig port_io__oe) (sig port_io2__oe)), invert=False, direction=Direction.Bidir)")
        self.assertRepr(port_io + port_i, "SimulationPort(i=(cat (sig port_io__i) (sig port_i__i)), invert=(False, False, True, True, True), direction=Direction.Input)")
        self.assertRepr(port_io + port_o, "SimulationPort(o=(cat (sig port_io__o) (sig port_o__o)), oe=(cat (sig port_io__oe) (sig port_o__oe)), invert=(False, False, True, False), direction=Direction.Output)")

    def test_add_wrong(self):
        io = IOPort(1)
        with self.assertRaisesRegex(TypeError,
                r"^unsupported operand type\(s\) for \+: 'SimulationPort' and 'SingleEndedPort'$"):
            SimulationPort("io", 2) + SingleEndedPort(io)


class BufferTestCase(FHDLTestCase):
    def test_signature(self):
        sig_i = Buffer.Signature("i", 4)
        self.assertEqual(sig_i.direction, Direction.Input)
        self.assertEqual(sig_i.width, 4)
        self.assertEqual(sig_i.members, wiring.SignatureMembers({
            "i": wiring.In(4),
        }))
        sig_o = Buffer.Signature("o", 4)
        self.assertEqual(sig_o.direction, Direction.Output)
        self.assertEqual(sig_o.width, 4)
        self.assertEqual(sig_o.members, wiring.SignatureMembers({
            "o": wiring.Out(4),
            "oe": wiring.Out(1, init=1),
        }))
        sig_io = Buffer.Signature("io", 4)
        self.assertEqual(sig_io.direction, Direction.Bidir)
        self.assertEqual(sig_io.width, 4)
        self.assertEqual(sig_io.members, wiring.SignatureMembers({
            "i": wiring.In(4),
            "o": wiring.Out(4),
            "oe": wiring.Out(1, init=0),
        }))
        self.assertNotEqual(sig_i, sig_io)
        self.assertEqual(sig_i, sig_i)
        self.assertRepr(sig_io, "Buffer.Signature(Direction.Bidir, 4)")

    def test_construct(self):
        io = IOPort(4)
        port = SingleEndedPort(io)
        buf = Buffer("i", port)
        self.assertEqual(buf.direction, Direction.Input)
        self.assertIs(buf.port, port)
        self.assertRepr(buf.signature, "Buffer.Signature(Direction.Input, 4).flip()")

    def test_construct_wrong(self):
        io = IOPort(4)
        port_i = SingleEndedPort(io, direction="i")
        port_o = SingleEndedPort(io, direction="o")
        with self.assertRaisesRegex(TypeError,
                r"^'port' must be a 'PortLike', not \(io-port io\)$"):
            Buffer("io", io)
        with self.assertRaisesRegex(ValueError,
                r"^Input port cannot be used with Bidir buffer$"):
            Buffer("io", port_i)
        with self.assertRaisesRegex(ValueError,
                r"^Output port cannot be used with Input buffer$"):
            Buffer("i", port_o)

    def test_elaborate(self):
        io = IOPort(4)

        port = SingleEndedPort(io)
        buf = Buffer("io", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, buf.o, buf.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (output 'i' 1.0:4)
                (io inout 'io' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (output 'i' 1.0:4)
            ))
            (cell 1 0 (iob inout 0.0:4 0.2:6 0.6))
        )
        """)

        port = SingleEndedPort(io, invert=[False, True, False, True])
        buf = Buffer("io", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, buf.o, buf.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (output 'i' 2.0:4)
                (io inout 'io' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (output 'i' 2.0:4)
            ))
            (cell 1 0 (^ 0.2:6 4'd10))
            (cell 2 0 (^ 3.0:4 4'd10))
            (cell 3 0 (iob inout 0.0:4 1.0:4 0.6))
        )
        """)

        buf = Buffer("i", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'i' 1.0:4)
                (io input 'io' 0.0:4)
            )
            (cell 0 0 (top
                (output 'i' 1.0:4)
            ))
            (cell 1 0 (^ 2.0:4 4'd10))
            (cell 2 0 (iob input 0.0:4))
        )
        """)

        buf = Buffer("o", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.o, buf.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (io output 'io' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
            ))
            (cell 1 0 (^ 0.2:6 4'd10))
            (cell 2 0 (iob output 0.0:4 1.0:4 0.6))
        )
        """)

    def test_elaborate_diff(self):
        iop = IOPort(4)
        ion = IOPort(4)

        port = DifferentialPort(iop, ion)
        buf = Buffer("io", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, buf.o, buf.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (output 'i' 1.0:4)
                (io inout 'iop' 0.0:4)
                (io output 'ion' 1.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (output 'i' 1.0:4)
            ))
            (cell 1 0 (iob inout 0.0:4 0.2:6 0.6))
            (cell 2 0 (~ 0.2:6))
            (cell 3 0 (iob output 1.0:4 2.0:4 0.6))
        )
        """)

        port = DifferentialPort(iop, ion, invert=[False, True, False, True])
        buf = Buffer("io", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, buf.o, buf.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (output 'i' 2.0:4)
                (io inout 'iop' 0.0:4)
                (io output 'ion' 1.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (output 'i' 2.0:4)
            ))
            (cell 1 0 (^ 0.2:6 4'd10))
            (cell 2 0 (^ 3.0:4 4'd10))
            (cell 3 0 (iob inout 0.0:4 1.0:4 0.6))
            (cell 4 0 (~ 1.0:4))
            (cell 5 0 (iob output 1.0:4 4.0:4 0.6))
        )
        """)

        buf = Buffer("i", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (output 'i' 1.0:4)
                (io input 'iop' 0.0:4)
            )
            (cell 0 0 (top
                (output 'i' 1.0:4)
            ))
            (cell 1 0 (^ 2.0:4 4'd10))
            (cell 2 0 (iob input 0.0:4))
        )
        """)

        buf = Buffer("o", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.o, buf.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (io output 'iop' 0.0:4)
                (io output 'ion' 1.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
            ))
            (cell 1 0 (^ 0.2:6 4'd10))
            (cell 2 0 (iob output 0.0:4 1.0:4 0.6))
            (cell 3 0 (~ 1.0:4))
            (cell 4 0 (iob output 1.0:4 3.0:4 0.6))
        )
        """)

    def test_elaborate_sim(self):
        port = SimulationPort("io", 4)
        buf = Buffer("io", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, buf.o, buf.oe, port.i, port.o, port.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (input 'port__i' 0.7:11)
                (output 'i' 5.0:4)
                (output 'port__o' 0.2:6)
                (output 'port__oe' (cat 0.6 0.6 0.6 0.6))
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (input 'port__i' 7:11)
                (output 'i' 5.0:4)
                (output 'port__o' 0.2:6)
                (output 'port__oe' (cat 0.6 0.6 0.6 0.6))
            ))
            (cell 1 0 (m 0.6 0.2 0.7))
            (cell 2 0 (m 0.6 0.3 0.8))
            (cell 3 0 (m 0.6 0.4 0.9))
            (cell 4 0 (m 0.6 0.5 0.10))
            (cell 5 0 (assignment_list 4'd0 (1 0:1 1.0) (1 1:2 2.0) (1 2:3 3.0) (1 3:4 4.0)))
        )
        """)

        port = SimulationPort("io", 4, invert=[False, True, False, True])
        buf = Buffer("io", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, buf.o, buf.oe, port.i, port.o, port.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (input 'port__i' 0.7:11)
                (output 'i' 2.0:4)
                (output 'port__o' 1.0:4)
                (output 'port__oe' (cat 0.6 0.6 0.6 0.6))
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (input 'port__i' 7:11)
                (output 'i' 2.0:4)
                (output 'port__o' 1.0:4)
                (output 'port__oe' (cat 0.6 0.6 0.6 0.6))
            ))
            (cell 1 0 (^ 0.2:6 4'd10))
            (cell 2 0 (^ 7.0:4 4'd10))
            (cell 3 0 (m 0.6 1.0 0.7))
            (cell 4 0 (m 0.6 1.1 0.8))
            (cell 5 0 (m 0.6 1.2 0.9))
            (cell 6 0 (m 0.6 1.3 0.10))
            (cell 7 0 (assignment_list 4'd0 (1 0:1 3.0) (1 1:2 4.0) (1 2:3 5.0) (1 3:4 6.0)))
        )
        """)

        buf = Buffer("i", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, port.i])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'port__i' 0.2:6)
                (output 'i' 1.0:4)
            )
            (cell 0 0 (top
                (input 'port__i' 2:6)
                (output 'i' 1.0:4)
            ))
            (cell 1 0 (^ 0.2:6 4'd10))
        )
        """)

        buf = Buffer("o", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.o, buf.oe, port.o, port.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (output 'port__o' 1.0:4)
                (output 'port__oe' (cat 0.6 0.6 0.6 0.6))
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (output 'port__o' 1.0:4)
                (output 'port__oe' (cat 0.6 0.6 0.6 0.6))
            ))
            (cell 1 0 (^ 0.2:6 4'd10))
        )
        """)

        # check that a port without `port.o`/`port.oe` works
        port = SimulationPort("i", 4, invert=[False, True, False, True])
        buf = Buffer("i", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, port.i])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'port__i' 0.2:6)
                (output 'i' 1.0:4)
            )
            (cell 0 0 (top
                (input 'port__i' 2:6)
                (output 'i' 1.0:4)
            ))
            (cell 1 0 (^ 0.2:6 4'd10))
        )
        """)


class FFBufferTestCase(FHDLTestCase):
    def test_signature(self):
        sig_i = FFBuffer.Signature("i", 4)
        self.assertEqual(sig_i.direction, Direction.Input)
        self.assertEqual(sig_i.width, 4)
        self.assertEqual(sig_i.members, wiring.SignatureMembers({
            "i": wiring.In(4),
        }))
        sig_o = FFBuffer.Signature("o", 4)
        self.assertEqual(sig_o.direction, Direction.Output)
        self.assertEqual(sig_o.width, 4)
        self.assertEqual(sig_o.members, wiring.SignatureMembers({
            "o": wiring.Out(4),
            "oe": wiring.Out(1, init=1),
        }))
        sig_io = FFBuffer.Signature("io", 4)
        self.assertEqual(sig_io.direction, Direction.Bidir)
        self.assertEqual(sig_io.width, 4)
        self.assertEqual(sig_io.members, wiring.SignatureMembers({
            "i": wiring.In(4),
            "o": wiring.Out(4),
            "oe": wiring.Out(1, init=0),
        }))
        self.assertNotEqual(sig_i, sig_io)
        self.assertEqual(sig_i, sig_i)
        self.assertRepr(sig_io, "FFBuffer.Signature(Direction.Bidir, 4)")

    def test_construct(self):
        io = IOPort(4)
        port = SingleEndedPort(io)
        buf = FFBuffer("i", port)
        self.assertEqual(buf.direction, Direction.Input)
        self.assertIs(buf.port, port)
        self.assertRepr(buf.signature, "FFBuffer.Signature(Direction.Input, 4).flip()")
        self.assertEqual(buf.i_domain, "sync")
        self.assertIs(buf.o_domain, None)
        buf = FFBuffer("i", port, i_domain="inp")
        self.assertEqual(buf.i_domain, "inp")
        buf = FFBuffer("o", port)
        self.assertEqual(buf.direction, Direction.Output)
        self.assertIs(buf.port, port)
        self.assertRepr(buf.signature, "FFBuffer.Signature(Direction.Output, 4).flip()")
        self.assertIs(buf.i_domain, None)
        self.assertEqual(buf.o_domain, "sync")
        buf = FFBuffer("o", port, o_domain="out")
        self.assertEqual(buf.o_domain, "out")
        buf = FFBuffer("io", port)
        self.assertEqual(buf.direction, Direction.Bidir)
        self.assertIs(buf.port, port)
        self.assertRepr(buf.signature, "FFBuffer.Signature(Direction.Bidir, 4).flip()")
        self.assertEqual(buf.i_domain, "sync")
        self.assertEqual(buf.o_domain, "sync")
        buf = FFBuffer("io", port, i_domain="input", o_domain="output")
        self.assertEqual(buf.i_domain, "input")
        self.assertEqual(buf.o_domain, "output")

    def test_construct_wrong(self):
        io = IOPort(4)
        port = SingleEndedPort(io)
        port_i = SingleEndedPort(io, direction="i")
        port_o = SingleEndedPort(io, direction="o")
        with self.assertRaisesRegex(TypeError,
                r"^'port' must be a 'PortLike', not \(io-port io\)$"):
            FFBuffer("io", io)
        with self.assertRaisesRegex(ValueError,
                r"^Input port cannot be used with Bidir buffer$"):
            FFBuffer("io", port_i)
        with self.assertRaisesRegex(ValueError,
                r"^Output port cannot be used with Input buffer$"):
            FFBuffer("i", port_o)
        with self.assertRaisesRegex(ValueError,
                r"^Input buffer doesn't have an output domain$"):
            FFBuffer("i", port, o_domain="output")
        with self.assertRaisesRegex(ValueError,
                r"^Output buffer doesn't have an input domain$"):
            FFBuffer("o", port, i_domain="input")

    def test_elaborate(self):
        io = IOPort(4)

        port = SingleEndedPort(io)
        m = Module()
        m.domains.inp = ClockDomain()
        m.domains.outp = ClockDomain()
        m.submodules.buf = buf = FFBuffer("io", port, i_domain="inp", o_domain="outp")
        nl = build_netlist(Fragment.get(m, None), [
            buf.i, buf.o, buf.oe,
            ClockSignal("inp"), ResetSignal("inp"),
            ClockSignal("outp"), ResetSignal("outp"),
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (input 'inp_clk' 0.7)
                (input 'inp_rst' 0.8)
                (input 'outp_clk' 0.9)
                (input 'outp_rst' 0.10)
                (output 'i' 2.0:4)
                (io inout 'io' 0.0:4)
            )
            (module 1 0 ('top' 'buf')
                (input 'o$11' 0.2:6)
                (input 'oe$12' 0.6)
                (input 'inp_clk' 0.7)
                (input 'inp_rst' 0.8)
                (input 'outp_clk' 0.9)
                (input 'outp_rst' 0.10)
                (output 'i_ff' 2.0:4)
                (io inout 'io' 0.0:4)
            )
            (module 2 1 ('top' 'buf' 'io_buffer')
                (output 'i' 1.0:4)
                (input 'o' 3.0:4)
                (input 'oe' 4.0)
                (io inout 'io' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (input 'inp_clk' 7:8)
                (input 'inp_rst' 8:9)
                (input 'outp_clk' 9:10)
                (input 'outp_rst' 10:11)
                (output 'i' 2.0:4)
            ))
            (cell 1 2 (iob inout 0.0:4 3.0:4 4.0))
            (cell 2 1 (flipflop 1.0:4 0 pos 0.7 0))
            (cell 3 1 (flipflop 0.2:6 0 pos 0.9 0))
            (cell 4 1 (flipflop 0.6 0 pos 0.9 0))
        )
        """)

        port = SingleEndedPort(io, invert=[False, True, False, True])
        m = Module()
        m.domains.inp = ClockDomain(reset_less=True)
        m.domains.outp = ClockDomain(reset_less=True)
        m.submodules.buf = buf = FFBuffer("io", port, i_domain="inp", o_domain="outp")
        nl = build_netlist(Fragment.get(m, None), [
            buf.i, buf.o, buf.oe,
            ClockSignal("inp"), ClockSignal("outp"),
        ])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (input 'inp_clk' 0.7)
                (input 'outp_clk' 0.8)
                (output 'i' 4.0:4)
                (io inout 'io' 0.0:4)
            )
            (module 1 0 ('top' 'buf')
                (input 'o$9' 0.2:6)
                (input 'oe$10' 0.6)
                (input 'inp_clk' 0.7)
                (input 'outp_clk' 0.8)
                (output 'i_ff' 4.0:4)
                (io inout 'io' 0.0:4)
            )
            (module 2 1 ('top' 'buf' 'io_buffer')
                (output 'i' 2.0:4)
                (input 'o' 5.0:4)
                (input 'oe' 6.0)
                (io inout 'io' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (input 'inp_clk' 7:8)
                (input 'outp_clk' 8:9)
                (output 'i' 4.0:4)
            ))
            (cell 1 2 (^ 5.0:4 4'd10))
            (cell 2 2 (^ 3.0:4 4'd10))
            (cell 3 2 (iob inout 0.0:4 1.0:4 6.0))
            (cell 4 1 (flipflop 2.0:4 0 pos 0.7 0))
            (cell 5 1 (flipflop 0.2:6 0 pos 0.8 0))
            (cell 6 1 (flipflop 0.6 0 pos 0.8 0))
        )
        """)

        buf = FFBuffer("i", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'clk' 0.2)
                (input 'rst' 0.3)
                (output 'i' 3.0:4)
                (io input 'io' 0.0:4)
            )
            (module 1 0 ('top' 'io_buffer')
                (output 'i' 1.0:4)
                (io input 'io' 0.0:4)
            )
            (cell 0 0 (top
                (input 'clk' 2:3)
                (input 'rst' 3:4)
                (output 'i' 3.0:4)
            ))
            (cell 1 1 (^ 2.0:4 4'd10))
            (cell 2 1 (iob input 0.0:4))
            (cell 3 0 (flipflop 1.0:4 0 pos 0.2 0))
        )
        """)

        buf = FFBuffer("o", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.o, buf.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (input 'clk' 0.7)
                (input 'rst' 0.8)
                (io output 'io' 0.0:4)
            )
            (module 1 0 ('top' 'io_buffer')
                (input 'o' 3.0:4)
                (input 'oe' 4.0)
                (io output 'io' 0.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (input 'clk' 7:8)
                (input 'rst' 8:9)
            ))
            (cell 1 1 (^ 3.0:4 4'd10))
            (cell 2 1 (iob output 0.0:4 1.0:4 4.0))
            (cell 3 0 (flipflop 0.2:6 0 pos 0.7 0))
            (cell 4 0 (flipflop 0.6 0 pos 0.7 0))
        )
        """)

    def test_elaborate_sim(self):
        port = SimulationPort("io", 4)
        buf = FFBuffer("io", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, buf.o, buf.oe, port.i, port.o, port.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (input 'port__i' 0.7:11)
                (input 'clk' 0.11)
                (input 'rst' 0.12)
                (output 'i' 5.0:4)
                (output 'port__o' 6.0:4)
                (output 'port__oe' (cat 7.0 7.0 7.0 7.0))
            )
            (module 1 0 ('top' 'io_buffer')
                (input 'port__i' 0.7:11)
                (input 'port__o' 6.0:4)
                (input 'oe' 7.0)
                (output 'i' 8.0:4)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (input 'port__i' 7:11)
                (input 'clk' 11:12)
                (input 'rst' 12:13)
                (output 'i' 5.0:4)
                (output 'port__o' 6.0:4)
                (output 'port__oe' (cat 7.0 7.0 7.0 7.0))
            ))
            (cell 1 1 (m 7.0 6.0 0.7))
            (cell 2 1 (m 7.0 6.1 0.8))
            (cell 3 1 (m 7.0 6.2 0.9))
            (cell 4 1 (m 7.0 6.3 0.10))
            (cell 5 0 (flipflop 8.0:4 0 pos 0.11 0))
            (cell 6 0 (flipflop 0.2:6 0 pos 0.11 0))
            (cell 7 0 (flipflop 0.6 0 pos 0.11 0))
            (cell 8 1 (assignment_list 4'd0 (1 0:1 1.0) (1 1:2 2.0) (1 2:3 3.0) (1 3:4 4.0)))
        )
        """)

        port = SimulationPort("io", 4, invert=[False, True, False, True])
        buf = FFBuffer("io", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, buf.o, buf.oe, port.i, port.o, port.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (input 'port__i' 0.7:11)
                (input 'clk' 0.11)
                (input 'rst' 0.12)
                (output 'i' 7.0:4)
                (output 'port__o' 1.0:4)
                (output 'port__oe' (cat 9.0 9.0 9.0 9.0))
            )
            (module 1 0 ('top' 'io_buffer')
                (input 'port__i' 0.7:11)
                (output 'o_inv' 1.0:4)
                (output 'i' 2.0:4)
                (input 'o' 8.0:4)
                (input 'oe' 9.0)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (input 'port__i' 7:11)
                (input 'clk' 11:12)
                (input 'rst' 12:13)
                (output 'i' 7.0:4)
                (output 'port__o' 1.0:4)
                (output 'port__oe' (cat 9.0 9.0 9.0 9.0))
            ))
            (cell 1 1 (^ 8.0:4 4'd10))
            (cell 2 1 (^ 10.0:4 4'd10))
            (cell 3 1 (m 9.0 1.0 0.7))
            (cell 4 1 (m 9.0 1.1 0.8))
            (cell 5 1 (m 9.0 1.2 0.9))
            (cell 6 1 (m 9.0 1.3 0.10))
            (cell 7 0 (flipflop 2.0:4 0 pos 0.11 0))
            (cell 8 0 (flipflop 0.2:6 0 pos 0.11 0))
            (cell 9 0 (flipflop 0.6 0 pos 0.11 0))
            (cell 10 1 (assignment_list 4'd0 (1 0:1 3.0) (1 1:2 4.0) (1 2:3 5.0) (1 3:4 6.0)))
        )
        """)

        buf = FFBuffer("i", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.i, port.i])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'port__i' 0.2:6)
                (input 'clk' 0.6)
                (input 'rst' 0.7)
                (output 'i' 2.0:4)
            )
            (module 1 0 ('top' 'io_buffer')
                (input 'i_inv' 0.2:6)
                (output 'i' 1.0:4)
            )
            (cell 0 0 (top
                (input 'port__i' 2:6)
                (input 'clk' 6:7)
                (input 'rst' 7:8)
                (output 'i' 2.0:4)
            ))
            (cell 1 1 (^ 0.2:6 4'd10))
            (cell 2 0 (flipflop 1.0:4 0 pos 0.6 0))
        )
        """)

        buf = FFBuffer("o", port)
        nl = build_netlist(Fragment.get(buf, None), [buf.o, buf.oe, port.o, port.oe])
        self.assertRepr(nl, """
        (
            (module 0 None ('top')
                (input 'o' 0.2:6)
                (input 'oe' 0.6)
                (input 'clk' 0.7)
                (input 'rst' 0.8)
                (output 'port__o' 1.0:4)
                (output 'port__oe' (cat 3.0 3.0 3.0 3.0))
            )
            (module 1 0 ('top' 'io_buffer')
                (output 'o_inv' 1.0:4)
                (input 'o' 2.0:4)
                (input 'oe' 3.0)
            )
            (cell 0 0 (top
                (input 'o' 2:6)
                (input 'oe' 6:7)
                (input 'clk' 7:8)
                (input 'rst' 8:9)
                (output 'port__o' 1.0:4)
                (output 'port__oe' (cat 3.0 3.0 3.0 3.0))
            ))
            (cell 1 1 (^ 2.0:4 4'd10))
            (cell 2 0 (flipflop 0.2:6 0 pos 0.7 0))
            (cell 3 0 (flipflop 0.6 0 pos 0.7 0))
        )
        """)


class DDRBufferTestCase(FHDLTestCase):
    def test_signature(self):
        sig_i = DDRBuffer.Signature("i", 4)
        self.assertEqual(sig_i.direction, Direction.Input)
        self.assertEqual(sig_i.width, 4)
        self.assertEqual(sig_i.members, wiring.SignatureMembers({
            "i": wiring.In(data.ArrayLayout(4, 2)),
        }))
        sig_o = DDRBuffer.Signature("o", 4)
        self.assertEqual(sig_o.direction, Direction.Output)
        self.assertEqual(sig_o.width, 4)
        self.assertEqual(sig_o.members, wiring.SignatureMembers({
            "o": wiring.Out(data.ArrayLayout(4, 2)),
            "oe": wiring.Out(1, init=1),
        }))
        sig_io = DDRBuffer.Signature("io", 4)
        self.assertEqual(sig_io.direction, Direction.Bidir)
        self.assertEqual(sig_io.width, 4)
        self.assertEqual(sig_io.members, wiring.SignatureMembers({
            "i": wiring.In(data.ArrayLayout(4, 2)),
            "o": wiring.Out(data.ArrayLayout(4, 2)),
            "oe": wiring.Out(1, init=0),
        }))
        self.assertNotEqual(sig_i, sig_io)
        self.assertEqual(sig_i, sig_i)
        self.assertRepr(sig_io, "DDRBuffer.Signature(Direction.Bidir, 4)")

    def test_construct(self):
        io = IOPort(4)
        port = SingleEndedPort(io)
        buf = DDRBuffer("i", port)
        self.assertEqual(buf.direction, Direction.Input)
        self.assertIs(buf.port, port)
        self.assertRepr(buf.signature, "DDRBuffer.Signature(Direction.Input, 4).flip()")
        self.assertEqual(buf.i_domain, "sync")
        self.assertIs(buf.o_domain, None)
        buf = DDRBuffer("i", port, i_domain="inp")
        self.assertEqual(buf.i_domain, "inp")
        buf = DDRBuffer("o", port)
        self.assertEqual(buf.direction, Direction.Output)
        self.assertIs(buf.port, port)
        self.assertRepr(buf.signature, "DDRBuffer.Signature(Direction.Output, 4).flip()")
        self.assertIs(buf.i_domain, None)
        self.assertEqual(buf.o_domain, "sync")
        buf = DDRBuffer("o", port, o_domain="out")
        self.assertEqual(buf.o_domain, "out")
        buf = DDRBuffer("io", port)
        self.assertEqual(buf.direction, Direction.Bidir)
        self.assertIs(buf.port, port)
        self.assertRepr(buf.signature, "DDRBuffer.Signature(Direction.Bidir, 4).flip()")
        self.assertEqual(buf.i_domain, "sync")
        self.assertEqual(buf.o_domain, "sync")
        buf = DDRBuffer("io", port, i_domain="input", o_domain="output")
        self.assertEqual(buf.i_domain, "input")
        self.assertEqual(buf.o_domain, "output")

    def test_construct_wrong(self):
        io = IOPort(4)
        port = SingleEndedPort(io)
        port_i = SingleEndedPort(io, direction="i")
        port_o = SingleEndedPort(io, direction="o")
        with self.assertRaisesRegex(TypeError,
                r"^'port' must be a 'PortLike', not \(io-port io\)$"):
            DDRBuffer("io", io)
        with self.assertRaisesRegex(ValueError,
                r"^Input port cannot be used with Bidir buffer$"):
            DDRBuffer("io", port_i)
        with self.assertRaisesRegex(ValueError,
                r"^Output port cannot be used with Input buffer$"):
            DDRBuffer("i", port_o)
        with self.assertRaisesRegex(ValueError,
                r"^Input buffer doesn't have an output domain$"):
            DDRBuffer("i", port, o_domain="output")
        with self.assertRaisesRegex(ValueError,
                r"^Output buffer doesn't have an input domain$"):
            DDRBuffer("o", port, i_domain="input")


class PinSignatureTestCase(FHDLTestCase):
    def assertSignatureEqual(self, signature, expected):
        self.assertEqual(signature.members, Signature(expected).members)


class PinSignatureCombTestCase(PinSignatureTestCase):
    def test_signature_i(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="i")
        self.assertSignatureEqual(sig_1, {
            "i": In(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="i")
        self.assertSignatureEqual(sig_2, {
            "i": In(2),
        })

    def test_signature_o(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="o")
        self.assertSignatureEqual(sig_1, {
            "o": Out(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="o")
        self.assertSignatureEqual(sig_2, {
            "o": Out(2),
        })

    def test_signature_oe(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="oe")
        self.assertSignatureEqual(sig_1, {
            "o":  Out(1),
            "oe": Out(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="oe")
        self.assertSignatureEqual(sig_2, {
            "o":  Out(2),
            "oe": Out(1),
        })

    def test_signature_io(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="io")
        self.assertSignatureEqual(sig_1, {
            "i":  In(1),
            "o":  Out(1),
            "oe": Out(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="io")
        self.assertSignatureEqual(sig_2, {
            "i":  In(2),
            "o":  Out(2),
            "oe": Out(1),
        })


class PinSignatureSDRTestCase(PinSignatureTestCase):
    def test_signature_i(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="i", xdr=1)
        self.assertSignatureEqual(sig_1, {
            "i_clk": Out(1),
            "i": In(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="i", xdr=1)
        self.assertSignatureEqual(sig_2, {
            "i_clk": Out(1),
            "i": In(2),
        })

    def test_signature_o(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="o", xdr=1)
        self.assertSignatureEqual(sig_1, {
            "o_clk": Out(1),
            "o": Out(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="o", xdr=1)
        self.assertSignatureEqual(sig_2, {
            "o_clk": Out(1),
            "o": Out(2),
        })

    def test_signature_oe(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="oe", xdr=1)
        self.assertSignatureEqual(sig_1, {
            "o_clk": Out(1),
            "o":  Out(1),
            "oe": Out(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="oe", xdr=1)
        self.assertSignatureEqual(sig_2, {
            "o_clk": Out(1),
            "o":  Out(2),
            "oe": Out(1),
        })

    def test_signature_io(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="io", xdr=1)
        self.assertSignatureEqual(sig_1, {
            "i_clk": Out(1),
            "i":  In(1),
            "o_clk": Out(1),
            "o":  Out(1),
            "oe": Out(1),
        })

        with _ignore_deprecated():
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
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="i", xdr=2)
        self.assertSignatureEqual(sig_1, {
            "i_clk": Out(1),
            "i0": In(1),
            "i1": In(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="i", xdr=2)
        self.assertSignatureEqual(sig_2, {
            "i_clk": Out(1),
            "i0": In(2),
            "i1": In(2),
        })

    def test_signature_o(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="o", xdr=2)
        self.assertSignatureEqual(sig_1, {
            "o_clk": Out(1),
            "o0": Out(1),
            "o1": Out(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="o", xdr=2)
        self.assertSignatureEqual(sig_2, {
            "o_clk": Out(1),
            "o0": Out(2),
            "o1": Out(2),
        })

    def test_signature_oe(self):
        with _ignore_deprecated():
            sig_1 = Pin.Signature(1, dir="oe", xdr=2)
        self.assertSignatureEqual(sig_1, {
            "o_clk": Out(1),
            "o0": Out(1),
            "o1": Out(1),
            "oe": Out(1),
        })

        with _ignore_deprecated():
            sig_2 = Pin.Signature(2, dir="oe", xdr=2)
        self.assertSignatureEqual(sig_2, {
            "o_clk": Out(1),
            "o0": Out(2),
            "o1": Out(2),
            "oe": Out(1),
        })

    def test_signature_io(self):
        with _ignore_deprecated():
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

        with _ignore_deprecated():
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
        with _ignore_deprecated():
            sig_0 = Pin.Signature(1, dir="i")
        self.assertRepr(sig_0, "Pin.Signature(1, dir='i')")
        with _ignore_deprecated():
            sig_0 = Pin.Signature(2, dir="o", xdr=1)
        self.assertRepr(sig_0, "Pin.Signature(2, dir='o', xdr=1)")
        with _ignore_deprecated():
            sig_0 = Pin.Signature(3, dir="io", xdr=2)
        self.assertRepr(sig_0, "Pin.Signature(3, dir='io', xdr=2)")


class PinTestCase(FHDLTestCase):
    def test_attributes(self):
        with _ignore_deprecated():
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
        with _ignore_deprecated():
            pin = Pin(2, dir="io", xdr=2, name="testpin")
        self.assertEqual(pin.name, "testpin")
        self.assertEqual(pin.path, ("testpin",))
        self.assertEqual(pin.i0.name, "testpin__i0")
        with _ignore_deprecated():
            pin = Pin(2, dir="io", xdr=2, path=["a", "b"])
        self.assertEqual(pin.name, "a__b")
        self.assertEqual(pin.path, ("a", "b"))
        self.assertEqual(pin.i0.name, "a__b__i0")
