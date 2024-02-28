# amaranth: UnusedElaboratable=no

from amaranth.hdl._ast import *
from amaranth.hdl._mem import MemoryInstance
from amaranth.lib.memory import *
from amaranth.lib.data import *
from amaranth.lib.wiring import In, Out, SignatureMembers

from .utils import *

class MyStruct(Struct):
    a: unsigned(3)
    b: signed(2)


class WritePortTestCase(FHDLTestCase):
    def test_signature(self):
        sig = WritePort.Signature(addr_width=2, shape=signed(4))
        self.assertEqual(sig.addr_width, 2)
        self.assertEqual(sig.shape, signed(4))
        self.assertEqual(sig.granularity, None)
        self.assertEqual(sig.members, SignatureMembers({
            "addr": In(2),
            "data": In(signed(4)),
            "en": In(1),
        }))
        sig = WritePort.Signature(addr_width=2, shape=8, granularity=2)
        self.assertEqual(sig.addr_width, 2)
        self.assertEqual(sig.shape, 8)
        self.assertEqual(sig.members, SignatureMembers({
            "addr": In(2),
            "data": In(8),
            "en": In(4),
        }))
        sig = WritePort.Signature(addr_width=2, shape=ArrayLayout(9, 8), granularity=2)
        self.assertEqual(sig.addr_width, 2)
        self.assertEqual(sig.shape, ArrayLayout(9, 8))
        self.assertEqual(sig.members, SignatureMembers({
            "addr": In(2),
            "data": In(ArrayLayout(9, 8)),
            "en": In(4),
        }))
        sig = WritePort.Signature(addr_width=2, shape=0, granularity=0)
        self.assertEqual(sig.addr_width, 2)
        self.assertEqual(sig.shape, 0)
        self.assertEqual(sig.members, SignatureMembers({
            "addr": In(2),
            "data": In(0),
            "en": In(0),
        }))
        sig = WritePort.Signature(addr_width=2, shape=ArrayLayout(9, 0), granularity=0)
        self.assertEqual(sig.addr_width, 2)
        self.assertEqual(sig.shape, ArrayLayout(9, 0))
        self.assertEqual(sig.members, SignatureMembers({
            "addr": In(2),
            "data": In(ArrayLayout(9, 0)),
            "en": In(0),
        }))

    def test_signature_wrong(self):
        with self.assertRaisesRegex(TypeError,
                "^`addr_width` must be a non-negative int, not -2$"):
            WritePort.Signature(addr_width=-2, shape=8)
        with self.assertRaisesRegex(TypeError,
                "^Granularity must be a non-negative int or None, not -2$"):
            WritePort.Signature(addr_width=4, shape=8, granularity=-2)
        with self.assertRaisesRegex(ValueError,
                "^Granularity cannot be specified with signed shape$"):
            WritePort.Signature(addr_width=2, shape=signed(8), granularity=2)
        with self.assertRaisesRegex(TypeError,
                "^Granularity can only be specified for plain unsigned `Shape` or `ArrayLayout`$"):
            WritePort.Signature(addr_width=2, shape=MyStruct, granularity=2)
        with self.assertRaisesRegex(ValueError,
                "^Granularity must be positive$"):
            WritePort.Signature(addr_width=2, shape=8, granularity=0)
        with self.assertRaisesRegex(ValueError,
                "^Granularity must be positive$"):
            WritePort.Signature(addr_width=2, shape=ArrayLayout(8, 8), granularity=0)
        with self.assertRaisesRegex(ValueError,
                "^Granularity must divide data width$"):
            WritePort.Signature(addr_width=2, shape=8, granularity=3)
        with self.assertRaisesRegex(ValueError,
                "^Granularity must divide data array length$"):
            WritePort.Signature(addr_width=2, shape=ArrayLayout(8, 8), granularity=3)

    def test_signature_eq(self):
        sig = WritePort.Signature(addr_width=2, shape=8)
        self.assertEqual(sig, WritePort.Signature(addr_width=2, shape=8))
        self.assertNotEqual(sig, WritePort.Signature(addr_width=2, shape=7))
        self.assertNotEqual(sig, WritePort.Signature(addr_width=1, shape=8))
        self.assertNotEqual(sig, WritePort.Signature(addr_width=2, shape=8, granularity=8))
        sig = WritePort.Signature(addr_width=2, shape=8, granularity=4)
        self.assertEqual(sig, WritePort.Signature(addr_width=2, shape=8, granularity=4))
        self.assertNotEqual(sig, WritePort.Signature(addr_width=2, shape=8, granularity=8))

    def test_constructor(self):
        signature = WritePort.Signature(shape=MyStruct, addr_width=4)
        port = WritePort(signature, memory=None, domain="sync")
        self.assertEqual(port.signature, signature)
        self.assertIsNone(port.memory)
        self.assertEqual(port.domain, "sync")
        self.assertIsInstance(port.addr, Signal)
        self.assertEqual(port.addr.shape(), unsigned(4))
        self.assertIsInstance(port.data, View)
        self.assertEqual(port.data.shape(), MyStruct)
        self.assertIsInstance(port.en, Signal)
        self.assertEqual(port.en.shape(), unsigned(1))

        signature = WritePort.Signature(shape=8, addr_width=4, granularity=2)
        port = WritePort(signature, memory=None, domain="sync")
        self.assertEqual(port.signature, signature)
        self.assertIsNone(port.memory)
        self.assertEqual(port.domain, "sync")
        self.assertIsInstance(port.addr, Signal)
        self.assertEqual(port.addr.shape(), unsigned(4))
        self.assertIsInstance(port.data, Signal)
        self.assertEqual(port.data.shape(), unsigned(8))
        self.assertIsInstance(port.en, Signal)
        self.assertEqual(port.en.shape(), unsigned(4))

        m = Memory(depth=16, shape=8, init=[])
        port = WritePort(signature, memory=m, domain="sync")
        self.assertIs(port.memory, m)
        self.assertEqual(m.w_ports, (port,))

    def test_constructor_wrong(self):
        signature = ReadPort.Signature(shape=8, addr_width=4)
        with self.assertRaisesRegex(TypeError,
                r"^Expected `WritePort.Signature`, not ReadPort.Signature\(.*\)$"):
            WritePort(signature, memory=None, domain="sync")
        signature = WritePort.Signature(shape=8, addr_width=4, granularity=2)
        with self.assertRaisesRegex(TypeError,
                r"^Domain has to be a string, not None$"):
            WritePort(signature, memory=None, domain=None)
        with self.assertRaisesRegex(TypeError,
                r"^Expected `Memory` or `None`, not 'a'$"):
            WritePort(signature, memory="a", domain="sync")
        with self.assertRaisesRegex(ValueError,
                r"^Write port domain cannot be \"comb\"$"):
            WritePort(signature, memory=None, domain="comb")
        signature = WritePort.Signature(shape=8, addr_width=4)
        m = Memory(depth=8, shape=8, init=[])
        with self.assertRaisesRegex(ValueError,
                r"^Memory address width 3 doesn't match port address width 4$"):
            WritePort(signature, memory=m, domain="sync")
        m = Memory(depth=16, shape=signed(8), init=[])
        with self.assertRaisesRegex(ValueError,
                r"^Memory shape signed\(8\) doesn't match port shape 8$"):
            WritePort(signature, memory=m, domain="sync")


class ReadPortTestCase(FHDLTestCase):
    def test_signature(self):
        sig = ReadPort.Signature(addr_width=2, shape=signed(4))
        self.assertEqual(sig.addr_width, 2)
        self.assertEqual(sig.shape, signed(4))
        self.assertEqual(sig.members, SignatureMembers({
            "addr": In(2),
            "data": Out(signed(4)),
            "en": In(1, init=1),
        }))
        sig = ReadPort.Signature(addr_width=2, shape=8)
        self.assertEqual(sig.addr_width, 2)
        self.assertEqual(sig.shape, 8)
        self.assertEqual(sig.members, SignatureMembers({
            "addr": In(2),
            "data": Out(8),
            "en": In(1, init=1),
        }))
        sig = ReadPort.Signature(addr_width=2, shape=MyStruct)
        self.assertEqual(sig.addr_width, 2)
        self.assertEqual(sig.shape, MyStruct)
        self.assertEqual(sig.members, SignatureMembers({
            "addr": In(2),
            "data": Out(MyStruct),
            "en": In(1, init=1),
        }))

    def test_signature_wrong(self):
        with self.assertRaisesRegex(TypeError,
                "^`addr_width` must be a non-negative int, not -2$"):
            ReadPort.Signature(addr_width=-2, shape=8)

    def test_signature_eq(self):
        sig = ReadPort.Signature(addr_width=2, shape=8)
        self.assertEqual(sig, ReadPort.Signature(addr_width=2, shape=8))
        self.assertNotEqual(sig, ReadPort.Signature(addr_width=2, shape=7))
        self.assertNotEqual(sig, ReadPort.Signature(addr_width=1, shape=8))
        self.assertNotEqual(sig, WritePort.Signature(addr_width=2, shape=8))

    def test_constructor(self):
        signature = ReadPort.Signature(shape=MyStruct, addr_width=4)
        port = ReadPort(signature, memory=None, domain="sync")
        self.assertEqual(port.signature, signature)
        self.assertIsNone(port.memory)
        self.assertEqual(port.domain, "sync")
        self.assertIsInstance(port.addr, Signal)
        self.assertEqual(port.addr.shape(), unsigned(4))
        self.assertIsInstance(port.data, View)
        self.assertEqual(port.data.shape(), MyStruct)
        self.assertIsInstance(port.en, Signal)
        self.assertEqual(port.en.shape(), unsigned(1))
        self.assertEqual(port.transparent_for, ())

        signature = ReadPort.Signature(shape=8, addr_width=4)
        port = ReadPort(signature, memory=None, domain="comb")
        self.assertEqual(port.signature, signature)
        self.assertIsNone(port.memory)
        self.assertEqual(port.domain, "comb")
        self.assertIsInstance(port.addr, Signal)
        self.assertEqual(port.addr.shape(), unsigned(4))
        self.assertIsInstance(port.data, Signal)
        self.assertEqual(port.data.shape(), unsigned(8))
        self.assertIsInstance(port.en, Const)
        self.assertEqual(port.en.shape(), unsigned(1))
        self.assertEqual(port.en.value, 1)
        self.assertEqual(port.transparent_for, ())

        m = Memory(depth=16, shape=8, init=[])
        port = ReadPort(signature, memory=m, domain="sync")
        self.assertIs(port.memory, m)
        self.assertEqual(m.r_ports, (port,))
        write_port = m.write_port()
        port = ReadPort(signature, memory=m, domain="sync", transparent_for=[write_port])
        self.assertIs(port.memory, m)
        self.assertEqual(port.transparent_for, (write_port,))

    def test_constructor_wrong(self):
        signature = WritePort.Signature(shape=8, addr_width=4)
        with self.assertRaisesRegex(TypeError,
                r"^Expected `ReadPort.Signature`, not WritePort.Signature\(.*\)$"):
            ReadPort(signature, memory=None, domain="sync")
        signature = ReadPort.Signature(shape=8, addr_width=4)
        with self.assertRaisesRegex(TypeError,
                r"^Domain has to be a string, not None$"):
            ReadPort(signature, memory=None, domain=None)
        with self.assertRaisesRegex(TypeError,
                r"^Expected `Memory` or `None`, not 'a'$"):
            ReadPort(signature, memory="a", domain="sync")
        signature = ReadPort.Signature(shape=8, addr_width=4)
        m = Memory(depth=8, shape=8, init=[])
        with self.assertRaisesRegex(ValueError,
                r"^Memory address width 3 doesn't match port address width 4$"):
            ReadPort(signature, memory=m, domain="sync")
        m = Memory(depth=16, shape=signed(8), init=[])
        with self.assertRaisesRegex(ValueError,
                r"^Memory shape signed\(8\) doesn't match port shape 8$"):
            ReadPort(signature, memory=m, domain="sync")
        m = Memory(depth=16, shape=8, init=[])
        port = m.read_port()
        with self.assertRaisesRegex(TypeError,
                r"^`transparent_for` must contain only `WritePort` instances$"):
            ReadPort(signature, memory=m, domain="sync", transparent_for=[port])
        write_port = m.write_port()
        m2 = Memory(depth=16, shape=8, init=[])
        with self.assertRaisesRegex(ValueError,
                r"^Transparent write ports must belong to the same memory$"):
            ReadPort(signature, memory=m2, domain="sync", transparent_for=[write_port])
        with self.assertRaisesRegex(ValueError,
                r"^Transparent write ports must belong to the same domain$"):
            ReadPort(signature, memory=m, domain="other", transparent_for=[write_port])


class MemoryTestCase(FHDLTestCase):
    def test_constructor(self):
        m = Memory(shape=8, depth=4, init=[1, 2, 3])
        self.assertEqual(m.shape, 8)
        self.assertEqual(m.depth, 4)
        self.assertEqual(m.init.shape, 8)
        self.assertEqual(m.init.depth, 4)
        self.assertEqual(m.attrs, {})
        self.assertIsInstance(m.init, Memory.Init)
        self.assertEqual(list(m.init), [1, 2, 3, 0])
        self.assertEqual(m.init._raw, [1, 2, 3, 0])
        self.assertRepr(m.init, "Memory.Init([1, 2, 3, 0])")
        self.assertEqual(m.r_ports, ())
        self.assertEqual(m.w_ports, ())

    def test_constructor_shapecastable(self):
        init = [
            {"a": 0, "b": 1},
            {"a": 2, "b": 3},
        ]
        m = Memory(shape=MyStruct, depth=4, init=init, attrs={"ram_style": "block"})
        self.assertEqual(m.shape, MyStruct)
        self.assertEqual(m.depth, 4)
        self.assertEqual(m.attrs, {"ram_style": "block"})
        self.assertIsInstance(m.init, Memory.Init)
        self.assertEqual(list(m.init), [{"a": 0, "b": 1}, {"a": 2, "b": 3}, None, None])
        self.assertEqual(m.init._raw, [8, 0x1a, 0, 0])

    def test_constructor_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"^Memory depth must be a non-negative integer, not 'a'$"):
            Memory(shape=8, depth="a", init=[])
        with self.assertRaisesRegex(TypeError,
                r"^Memory depth must be a non-negative integer, not -1$"):
            Memory(shape=8, depth=-1, init=[])
        with self.assertRaisesRegex(TypeError,
                r"^Object 'a' cannot be converted to an Amaranth shape$"):
            Memory(shape="a", depth=3, init=[])
        with self.assertRaisesRegex(TypeError,
                (r"^Memory initialization value at address 1: "
                    r"'str' object cannot be interpreted as an integer$")):
            Memory(shape=8, depth=4, init=[1, "0"])

    def test_init_set(self):
        m = Memory(shape=8, depth=4, init=[])
        m.init[1] = 2
        self.assertEqual(list(m.init), [0, 2, 0, 0])
        self.assertEqual(m.init._raw, [0, 2, 0, 0])
        m.init[2:] = [4, 5]
        self.assertEqual(list(m.init), [0, 2, 4, 5])

    def test_init_set_shapecastable(self):
        m = Memory(shape=MyStruct, depth=4, init=[])
        m.init[1] = {"a": 1, "b": 2}
        self.assertEqual(list(m.init), [None, {"a": 1, "b": 2}, None, None])
        self.assertEqual(m.init._raw, [0, 0x11, 0, 0])

    def test_init_set_wrong(self):
        m = Memory(shape=8, depth=4, init=[])
        with self.assertRaisesRegex(TypeError,
                r"^'str' object cannot be interpreted as an integer$"):
            m.init[0] = "a"
        m = Memory(shape=MyStruct, depth=4, init=[])
        # underlying TypeError message differs between PyPy and CPython
        with self.assertRaises(TypeError):
            m.init[0] = 1

    def test_init_set_slice_wrong(self):
        m = Memory(shape=8, depth=4, init=[])
        with self.assertRaisesRegex(ValueError,
                r"^Changing length of Memory.init is not allowed$"):
            m.init[1:] = [1, 2]
        with self.assertRaisesRegex(TypeError,
                r"^Deleting items from Memory.init is not allowed$"):
            del m.init[1:2]
        with self.assertRaisesRegex(TypeError,
                r"^Inserting items into Memory.init is not allowed$"):
            m.init.insert(1, 3)

    def test_port(self):
        for depth, addr_width in [
            (0, 0),
            (1, 0),
            (3, 2),
            (4, 2),
            (5, 3),
        ]:
            m = Memory(shape=8, depth=depth, init=[])
            rp = m.read_port()
            self.assertEqual(rp.signature.addr_width, addr_width)
            self.assertEqual(rp.signature.shape, 8)
            wp = m.write_port()
            self.assertEqual(wp.signature.addr_width, addr_width)
            self.assertEqual(wp.signature.shape, 8)
            self.assertEqual(m.r_ports, (rp,))
            self.assertEqual(m.w_ports, (wp,))

    def test_elaborate(self):
        m = Memory(shape=MyStruct, depth=4, init=[{"a": 1, "b": 2}])
        wp = m.write_port()
        rp0 = m.read_port(domain="sync", transparent_for=[wp])
        rp1 = m.read_port(domain="comb")
        f = m.elaborate(None)
        self.assertIsInstance(f, MemoryInstance)
        self.assertIs(f._identity, m._identity)
        self.assertEqual(f._depth, 4)
        self.assertEqual(f._width, 5)
        self.assertEqual(f._init, (0x11, 0, 0, 0))
        self.assertEqual(f._write_ports[0]._domain, "sync")
        self.assertEqual(f._write_ports[0]._granularity, 5)
        self.assertIs(f._write_ports[0]._addr, wp.addr)
        self.assertIs(f._write_ports[0]._data, wp.data.as_value())
        self.assertIs(f._write_ports[0]._en, wp.en)
        self.assertEqual(f._read_ports[0]._domain, "sync")
        self.assertEqual(f._read_ports[0]._transparent_for, (0,))
        self.assertIs(f._read_ports[0]._addr, rp0.addr)
        self.assertIs(f._read_ports[0]._data, rp0.data.as_value())
        self.assertIs(f._read_ports[0]._en, rp0.en)
        self.assertEqual(f._read_ports[1]._domain, "comb")
        self.assertEqual(f._read_ports[1]._transparent_for, ())
        self.assertIs(f._read_ports[1]._addr, rp1.addr)
        self.assertIs(f._read_ports[1]._data, rp1.data.as_value())
        self.assertIs(f._read_ports[1]._en, rp1.en)
