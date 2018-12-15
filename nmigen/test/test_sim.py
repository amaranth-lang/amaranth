from .tools import *
from ..hdl.ast import *
from ..hdl.ir import *
from ..back.pysim import *


class SimulatorUnitTestCase(FHDLTestCase):
    def assertOperator(self, stmt, inputs, output):
        inputs = [Value.wrap(i) for i in inputs]
        output = Value.wrap(output)

        isigs = [Signal(i.shape(), name=n) for i, n in zip(inputs, "abcd")]
        osig  = Signal(output.shape(), name="y")

        frag = Fragment()
        frag.add_statements(osig.eq(stmt(*isigs)))
        frag.add_driver(osig)

        with Simulator(frag,
                vcd_file =open("test.vcd",  "w"),
                gtkw_file=open("test.gtkw", "w"),
                traces=[*isigs, osig]) as sim:
            def process():
                for isig, input in zip(isigs, inputs):
                    yield isig.eq(input)
                yield Delay()
                self.assertEqual((yield osig), output.value)
            sim.add_process(process)
            sim.run()

    def test_invert(self):
        stmt = lambda a: ~a
        self.assertOperator(stmt, [C(0b0000, 4)], C(0b1111, 4))
        self.assertOperator(stmt, [C(0b1010, 4)], C(0b0101, 4))
        self.assertOperator(stmt, [C(0,      4)], C(-1,     4))

    def test_neg(self):
        stmt = lambda a: -a
        self.assertOperator(stmt, [C(0b0000, 4)], C(0b0000, 4))
        self.assertOperator(stmt, [C(0b0001, 4)], C(0b1111, 4))
        self.assertOperator(stmt, [C(0b1010, 4)], C(0b0110, 4))
        self.assertOperator(stmt, [C(1,      4)], C(-1,     4))
        self.assertOperator(stmt, [C(5,      4)], C(-5,     4))

    def test_bool(self):
        stmt = lambda a: a.bool()
        self.assertOperator(stmt, [C(0, 4)], C(0))
        self.assertOperator(stmt, [C(1, 4)], C(1))
        self.assertOperator(stmt, [C(2, 4)], C(1))

    def test_add(self):
        stmt = lambda a, b: a + b
        self.assertOperator(stmt, [C(0,  4), C(1,  4)], C(1,   4))
        self.assertOperator(stmt, [C(-5, 4), C(-5, 4)], C(-10, 5))

    def test_sub(self):
        stmt = lambda a, b: a - b
        self.assertOperator(stmt, [C(2,  4), C(1,  4)], C(1,   4))
        self.assertOperator(stmt, [C(0,  4), C(1,  4)], C(-1,  4))
        self.assertOperator(stmt, [C(0,  4), C(10, 4)], C(-10, 5))

    def test_and(self):
        stmt = lambda a, b: a & b
        self.assertOperator(stmt, [C(0b1100, 4), C(0b1010, 4)], C(0b1000, 4))

    def test_or(self):
        stmt = lambda a, b: a | b
        self.assertOperator(stmt, [C(0b1100, 4), C(0b1010, 4)], C(0b1110, 4))

    def test_xor(self):
        stmt = lambda a, b: a ^ b
        self.assertOperator(stmt, [C(0b1100, 4), C(0b1010, 4)], C(0b0110, 4))

    def test_shl(self):
        stmt = lambda a, b: a << b
        self.assertOperator(stmt, [C(0b1001, 4), C(0)],  C(0b1001,    5))
        self.assertOperator(stmt, [C(0b1001, 4), C(3)],  C(0b1001000, 7))
        self.assertOperator(stmt, [C(0b1001, 4), C(-2)], C(0b10,      7))

    def test_shr(self):
        stmt = lambda a, b: a >> b
        self.assertOperator(stmt, [C(0b1001, 4), C(0)],  C(0b1001,    4))
        self.assertOperator(stmt, [C(0b1001, 4), C(2)],  C(0b10,      4))
        self.assertOperator(stmt, [C(0b1001, 4), C(-2)], C(0b100100,  5))

    def test_eq(self):
        stmt = lambda a, b: a == b
        self.assertOperator(stmt, [C(0, 4), C(0, 4)], C(1))
        self.assertOperator(stmt, [C(0, 4), C(1, 4)], C(0))
        self.assertOperator(stmt, [C(1, 4), C(0, 4)], C(0))

    def test_ne(self):
        stmt = lambda a, b: a != b
        self.assertOperator(stmt, [C(0, 4), C(0, 4)], C(0))
        self.assertOperator(stmt, [C(0, 4), C(1, 4)], C(1))
        self.assertOperator(stmt, [C(1, 4), C(0, 4)], C(1))

    def test_lt(self):
        stmt = lambda a, b: a < b
        self.assertOperator(stmt, [C(0, 4), C(0, 4)], C(0))
        self.assertOperator(stmt, [C(0, 4), C(1, 4)], C(1))
        self.assertOperator(stmt, [C(1, 4), C(0, 4)], C(0))

    def test_ge(self):
        stmt = lambda a, b: a >= b
        self.assertOperator(stmt, [C(0, 4), C(0, 4)], C(1))
        self.assertOperator(stmt, [C(0, 4), C(1, 4)], C(0))
        self.assertOperator(stmt, [C(1, 4), C(0, 4)], C(1))

    def test_gt(self):
        stmt = lambda a, b: a > b
        self.assertOperator(stmt, [C(0, 4), C(0, 4)], C(0))
        self.assertOperator(stmt, [C(0, 4), C(1, 4)], C(0))
        self.assertOperator(stmt, [C(1, 4), C(0, 4)], C(1))

    def test_le(self):
        stmt = lambda a, b: a <= b
        self.assertOperator(stmt, [C(0, 4), C(0, 4)], C(1))
        self.assertOperator(stmt, [C(0, 4), C(1, 4)], C(1))
        self.assertOperator(stmt, [C(1, 4), C(0, 4)], C(0))

    def test_mux(self):
        stmt = lambda a, b, c: Mux(c, a, b)
        self.assertOperator(stmt, [C(2, 4), C(3, 4), C(0)], C(3, 4))
        self.assertOperator(stmt, [C(2, 4), C(3, 4), C(1)], C(2, 4))

    def test_slice(self):
        stmt1 = lambda a: a[2]
        self.assertOperator(stmt1, [C(0b10110100, 8)], C(0b1,  1))
        stmt2 = lambda a: a[2:4]
        self.assertOperator(stmt2, [C(0b10110100, 8)], C(0b01, 2))

    def test_part(self):
        stmt = lambda a, b: a.part(b, 3)
        self.assertOperator(stmt, [C(0b10110100, 8), C(0)], C(0b100, 3))
        self.assertOperator(stmt, [C(0b10110100, 8), C(2)], C(0b101, 3))
        self.assertOperator(stmt, [C(0b10110100, 8), C(3)], C(0b110, 3))

    def test_cat(self):
        self.assertOperator(Cat, [C(0b10, 2), C(0b01, 2)], C(0b0110, 4))

    def test_repl(self):
        stmt = lambda a: Repl(a, 3)
        self.assertOperator(stmt, [C(0b10, 2)], C(0b101010, 6))

    def test_array(self):
        array = Array([1, 4, 10])
        stmt = lambda a: array[a]
        self.assertOperator(stmt, [C(0)], C(1))
        self.assertOperator(stmt, [C(1)], C(4))
        self.assertOperator(stmt, [C(2)], C(10))

    def test_array_index(self):
        array = Array(Array(x * y for y in range(10)) for x in range(10))
        stmt = lambda a, b: array[a][b]
        for x in range(10):
            for y in range(10):
                self.assertOperator(stmt, [C(x), C(y)], C(x * y))

    def test_array_attr(self):
        from collections import namedtuple
        pair = namedtuple("pair", ("p", "n"))

        array = Array(pair(x, -x) for x in range(10))
        stmt = lambda a: array[a].p + array[a].n
        for i in range(10):
            self.assertOperator(stmt, [C(i)], C(0))
