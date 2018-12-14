from .tools import *
from ..fhdl.ast import *
from ..fhdl.ir import *
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
