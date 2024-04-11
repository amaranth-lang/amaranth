# amaranth: UnusedElaboratable=no

from amaranth.hdl import *
from amaranth.hdl._mem import *
from amaranth._utils import _ignore_deprecated

from .utils import *


class MemoryDataTestCase(FHDLTestCase):
    def test_repr(self):
        data = MemoryData(shape=8, depth=4, init=[])
        self.assertRepr(data, "(memory-data data)")

    def test_row(self):
        data = MemoryData(shape=8, depth=4, init=[])
        self.assertRepr(data[2], "(memory-row (memory-data data) 2)")

    def test_row_wrong(self):
        data = MemoryData(shape=8, depth=4, init=[])
        with self.assertRaisesRegex(IndexError,
                r"^Index 4 is out of bounds \(memory has 4 rows\)$"):
            data[4]

    def test_row_elab(self):
        data = MemoryData(shape=8, depth=4, init=[])
        m = Module()
        a = Signal(8)
        with self.assertRaisesRegex(ValueError,
                r"^Value \(memory-row \(memory-data data\) 0\) can only be used in simulator processes$"):
            m.d.comb += a.eq(data[0])
        with self.assertRaisesRegex(ValueError,
                r"^Value \(memory-row \(memory-data data\) 0\) can only be used in simulator processes$"):
            m.d.comb += data[0].eq(1)

class MemoryTestCase(FHDLTestCase):
    def test_name(self):
        with _ignore_deprecated():
            m1 = Memory(width=8, depth=4)
            self.assertEqual(m1.name, "m1")
            m2 = [Memory(width=8, depth=4)][0]
            self.assertEqual(m2.name, "$memory")
            m3 = Memory(width=8, depth=4, name="foo")
            self.assertEqual(m3.name, "foo")

    def test_geometry(self):
        with _ignore_deprecated():
            m = Memory(width=8, depth=4)
            self.assertEqual(m.width, 8)
            self.assertEqual(m.depth, 4)

    def test_geometry_wrong(self):
        with _ignore_deprecated():
            with self.assertRaisesRegex(TypeError,
                    r"^Memory width must be a non-negative integer, not -1$"):
                m = Memory(width=-1, depth=4)
            with self.assertRaisesRegex(TypeError,
                    r"^Memory depth must be a non-negative integer, not -1$"):
                m = Memory(width=8, depth=-1)

    def test_init(self):
        with _ignore_deprecated():
            m = Memory(width=8, depth=4, init=range(4))
            self.assertEqual(list(m.init), [0, 1, 2, 3])

    def test_init_wrong_count(self):
        with _ignore_deprecated():
            with self.assertRaisesRegex(ValueError,
                    r"^Memory initialization value count exceeds memory depth \(8 > 4\)$"):
                m = Memory(width=8, depth=4, init=range(8))

    def test_init_wrong_type(self):
        with _ignore_deprecated():
            with self.assertRaisesRegex(TypeError,
                    (r"^Memory initialization value at address 1: "
                        r"'str' object cannot be interpreted as an integer$")):
                m = Memory(width=8, depth=4, init=[1, "0"])

    def test_attrs(self):
        with _ignore_deprecated():
            m1 = Memory(width=8, depth=4)
            self.assertEqual(m1.attrs, {})
            m2 = Memory(width=8, depth=4, attrs={"ram_block": True})
            self.assertEqual(m2.attrs, {"ram_block": True})

    def test_read_port_transparent(self):
        with _ignore_deprecated():
            mem    = Memory(width=8, depth=4)
            rdport = mem.read_port()
            self.assertEqual(rdport.memory, mem)
            self.assertEqual(rdport.domain, "sync")
            self.assertEqual(rdport.transparent, True)
            self.assertEqual(len(rdport.addr), 2)
            self.assertEqual(len(rdport.data), 8)
            self.assertEqual(len(rdport.en), 1)
            self.assertIsInstance(rdport.en, Signal)
            self.assertEqual(rdport.en.init, 1)

    def test_read_port_non_transparent(self):
        with _ignore_deprecated():
            mem    = Memory(width=8, depth=4)
            rdport = mem.read_port(transparent=False)
            self.assertEqual(rdport.memory, mem)
            self.assertEqual(rdport.domain, "sync")
            self.assertEqual(rdport.transparent, False)
            self.assertEqual(len(rdport.en), 1)
            self.assertIsInstance(rdport.en, Signal)
            self.assertEqual(rdport.en.init, 1)

    def test_read_port_asynchronous(self):
        with _ignore_deprecated():
            mem    = Memory(width=8, depth=4)
            rdport = mem.read_port(domain="comb")
            self.assertEqual(rdport.memory, mem)
            self.assertEqual(rdport.domain, "comb")
            self.assertEqual(rdport.transparent, True)
            self.assertEqual(len(rdport.en), 1)
            self.assertIsInstance(rdport.en, Const)
            self.assertEqual(rdport.en.value, 1)

    def test_read_port_wrong(self):
        with _ignore_deprecated():
            mem = Memory(width=8, depth=4)
            with self.assertRaisesRegex(ValueError,
                    r"^Read port cannot be simultaneously asynchronous and non-transparent$"):
                mem.read_port(domain="comb", transparent=False)

    def test_write_port(self):
        with _ignore_deprecated():
            mem    = Memory(width=8, depth=4)
            wrport = mem.write_port()
            self.assertEqual(wrport.memory, mem)
            self.assertEqual(wrport.domain, "sync")
            self.assertEqual(wrport.granularity, 8)
            self.assertEqual(len(wrport.addr), 2)
            self.assertEqual(len(wrport.data), 8)
            self.assertEqual(len(wrport.en), 1)

    def test_write_port_granularity(self):
        with _ignore_deprecated():
            mem    = Memory(width=8, depth=4)
            wrport = mem.write_port(granularity=2)
            self.assertEqual(wrport.memory, mem)
            self.assertEqual(wrport.domain, "sync")
            self.assertEqual(wrport.granularity, 2)
            self.assertEqual(len(wrport.addr), 2)
            self.assertEqual(len(wrport.data), 8)
            self.assertEqual(len(wrport.en), 4)

    def test_write_port_granularity_wrong(self):
        with _ignore_deprecated():
            mem = Memory(width=8, depth=4)
        with self.assertRaisesRegex(TypeError,
                r"^Write port granularity must be a non-negative integer, not -1$"):
            mem.write_port(granularity=-1)
        with self.assertRaisesRegex(ValueError,
                r"^Write port granularity must not be greater than memory width \(10 > 8\)$"):
            mem.write_port(granularity=10)
        with self.assertRaisesRegex(ValueError,
                r"^Write port granularity must divide memory width evenly$"):
            mem.write_port(granularity=3)

    def test_deprecated(self):
        with self.assertWarnsRegex(DeprecationWarning,
                r"^`amaranth.hdl.Memory` is deprecated.*$"):
            mem = Memory(width=8, depth=4)


class DummyPortTestCase(FHDLTestCase):
    def test_name(self):
        with _ignore_deprecated():
            p1 = DummyPort(data_width=8, addr_width=2)
            self.assertEqual(p1.addr.name, "p1_addr")
            p2 = [DummyPort(data_width=8, addr_width=2)][0]
            self.assertEqual(p2.addr.name, "dummy_addr")
            p3 = DummyPort(data_width=8, addr_width=2, name="foo")
            self.assertEqual(p3.addr.name, "foo_addr")

    def test_sizes(self):
        with _ignore_deprecated():
            p1 = DummyPort(data_width=8, addr_width=2)
            self.assertEqual(p1.addr.width, 2)
            self.assertEqual(p1.data.width, 8)
            self.assertEqual(p1.en.width, 1)
            p2 = DummyPort(data_width=8, addr_width=2, granularity=2)
            self.assertEqual(p2.en.width, 4)

    def test_deprecated(self):
        with self.assertWarnsRegex(DeprecationWarning,
                r"^`DummyPort` is deprecated.*$"):
            DummyPort(data_width=8, addr_width=2)
