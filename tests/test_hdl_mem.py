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
