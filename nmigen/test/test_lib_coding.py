from .tools import *
from ..hdl.ast import *
from ..back.pysim import *
from ..lib.coding import *


class EncoderTestCase(FHDLTestCase):
    def test_basic(self):
        enc = Encoder(4)
        with Simulator(enc) as sim:
            def process():
                self.assertEqual((yield enc.n), 1)
                self.assertEqual((yield enc.o), 0)

                yield enc.i.eq(0b0001)
                yield Delay()
                self.assertEqual((yield enc.n), 0)
                self.assertEqual((yield enc.o), 0)

                yield enc.i.eq(0b0100)
                yield Delay()
                self.assertEqual((yield enc.n), 0)
                self.assertEqual((yield enc.o), 2)

                yield enc.i.eq(0b0110)
                yield Delay()
                self.assertEqual((yield enc.n), 1)
                self.assertEqual((yield enc.o), 0)

            sim.add_process(process)


class PriorityEncoderTestCase(FHDLTestCase):
    def test_basic(self):
        enc = PriorityEncoder(4)
        with Simulator(enc) as sim:
            def process():
                self.assertEqual((yield enc.n), 1)
                self.assertEqual((yield enc.o), 0)

                yield enc.i.eq(0b0001)
                yield Delay()
                self.assertEqual((yield enc.n), 0)
                self.assertEqual((yield enc.o), 0)

                yield enc.i.eq(0b0100)
                yield Delay()
                self.assertEqual((yield enc.n), 0)
                self.assertEqual((yield enc.o), 2)

                yield enc.i.eq(0b0110)
                yield Delay()
                self.assertEqual((yield enc.n), 0)
                self.assertEqual((yield enc.o), 1)

            sim.add_process(process)


class DecoderTestCase(FHDLTestCase):
    def test_basic(self):
        dec = Decoder(4)
        with Simulator(dec) as sim:
            def process():
                self.assertEqual((yield enc.o), 0b0001)

                yield enc.i.eq(1)
                yield Delay()
                self.assertEqual((yield enc.o), 0b0010)

                yield enc.i.eq(3)
                yield Delay()
                self.assertEqual((yield enc.o), 0b1000)

                yield enc.n.eq(1)
                yield Delay()
                self.assertEqual((yield enc.o), 0b0000)

            sim.add_process(process)
