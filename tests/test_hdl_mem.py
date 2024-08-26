# amaranth: UnusedElaboratable=no

from amaranth.hdl import *
from amaranth.hdl._mem import *

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


class InitTestCase(FHDLTestCase):
    def test_ones(self):
        init = MemoryData.Init([-1, 12], shape=8, depth=2)
        self.assertEqual(list(init), [0xff, 12])
        init = MemoryData.Init([-1, -12], shape=signed(8), depth=2)
        self.assertEqual(list(init), [-1, -12])

    def test_trunc(self):
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Initial value -2 is signed, but the memory shape is unsigned\(8\)$"):
            init = MemoryData.Init([-2, 12], shape=8, depth=2)
        self.assertEqual(list(init), [0xfe, 12])
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Initial value 258 will be truncated to the memory shape unsigned\(8\)$"):
            init = MemoryData.Init([258, 129], shape=8, depth=2)
        self.assertEqual(list(init), [2, 129])
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Initial value 128 will be truncated to the memory shape signed\(8\)$"):
            init = MemoryData.Init([128], shape=signed(8), depth=1)
        self.assertEqual(list(init), [-128])
        with self.assertWarnsRegex(SyntaxWarning,
                r"^Initial value -129 will be truncated to the memory shape signed\(8\)$"):
            init = MemoryData.Init([-129], shape=signed(8), depth=1)
        self.assertEqual(list(init), [127])
