import warnings

from amaranth.hdl import *
from amaranth.sim import *
with warnings.catch_warnings():
    warnings.filterwarnings(action="ignore", category=DeprecationWarning)
    from amaranth.lib.coding import *

from .utils import *


class EncoderTestCase(FHDLTestCase):
    def test_basic(self):
        enc = Encoder(4)
        async def testbench(ctx):
            self.assertEqual(ctx.get(enc.n), 1)
            self.assertEqual(ctx.get(enc.o), 0)

            ctx.set(enc.i, 0b0001)
            self.assertEqual(ctx.get(enc.n), 0)
            self.assertEqual(ctx.get(enc.o), 0)

            ctx.set(enc.i, 0b0100)
            self.assertEqual(ctx.get(enc.n), 0)
            self.assertEqual(ctx.get(enc.o), 2)

            ctx.set(enc.i, 0b0110)
            self.assertEqual(ctx.get(enc.n), 1)
            self.assertEqual(ctx.get(enc.o), 0)

        sim = Simulator(enc)
        sim.add_testbench(testbench)
        sim.run()


class PriorityEncoderTestCase(FHDLTestCase):
    def test_basic(self):
        enc = PriorityEncoder(4)
        async def testbench(ctx):
            self.assertEqual(ctx.get(enc.n), 1)
            self.assertEqual(ctx.get(enc.o), 0)

            ctx.set(enc.i, 0b0001)
            self.assertEqual(ctx.get(enc.n), 0)
            self.assertEqual(ctx.get(enc.o), 0)

            ctx.set(enc.i, 0b0100)
            self.assertEqual(ctx.get(enc.n), 0)
            self.assertEqual(ctx.get(enc.o), 2)

            ctx.set(enc.i, 0b0110)
            self.assertEqual(ctx.get(enc.n), 0)
            self.assertEqual(ctx.get(enc.o), 1)

        sim = Simulator(enc)
        sim.add_testbench(testbench)
        sim.run()


class DecoderTestCase(FHDLTestCase):
    def test_basic(self):
        dec = Decoder(4)
        async def testbench(ctx):
            self.assertEqual(ctx.get(dec.o), 0b0001)

            ctx.set(dec.i, 1)
            self.assertEqual(ctx.get(dec.o), 0b0010)

            ctx.set(dec.i, 3)
            self.assertEqual(ctx.get(dec.o), 0b1000)

            ctx.set(dec.n, 1)
            self.assertEqual(ctx.get(dec.o), 0b0000)

        sim = Simulator(dec)
        sim.add_testbench(testbench)
        sim.run()


class ReversibleSpec(Elaboratable):
    def __init__(self, encoder_cls, decoder_cls, i_width, args):
        self.encoder_cls = encoder_cls
        self.decoder_cls = decoder_cls
        self.coder_args  = args
        self.i           = Signal(i_width)

    def elaborate(self, platform):
        m = Module()
        enc, dec = self.encoder_cls(*self.coder_args), self.decoder_cls(*self.coder_args)
        m.submodules += enc, dec
        m.d.comb += [
            enc.i.eq(self.i),
            dec.i.eq(enc.o),
            Assert(enc.i == dec.o)
        ]
        return m


class HammingDistanceSpec(Elaboratable):
    def __init__(self, distance, encoder_cls, i_width, args):
        self.distance    = distance
        self.encoder_cls = encoder_cls
        self.coder_args  = args
        self.i1          = Signal(i_width)
        self.i2          = Signal(i_width)

    def elaborate(self, platform):
        m = Module()
        enc1, enc2 = self.encoder_cls(*self.coder_args), self.encoder_cls(*self.coder_args)
        m.submodules += enc1, enc2
        m.d.comb += [
            enc1.i.eq(self.i1),
            enc2.i.eq(self.i2),
            Assume(enc1.i + 1 == enc2.i),
            Assert(sum(enc1.o ^ enc2.o) == self.distance)
        ]
        return m


class GrayCoderTestCase(FHDLTestCase):
    def test_reversible(self):
        spec = ReversibleSpec(encoder_cls=GrayEncoder, decoder_cls=GrayDecoder, i_width=16,
                              args=(16,))
        self.assertFormal(spec, [spec.i], mode="prove")

    def test_distance(self):
        spec = HammingDistanceSpec(distance=1, encoder_cls=GrayEncoder, i_width=16, args=(16,))
        self.assertFormal(spec, [spec.i1, spec.i2], mode="prove")
