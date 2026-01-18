from .utils import *

from amaranth.hdl import *
from amaranth.sim import Simulator
from amaranth.lib import fixed

class TestFixedShape(FHDLTestCase):

    def test_shape_uq_init(self):

        s = fixed.UQ(6, 5)
        self.assertEqual(s.i_bits, 6)
        self.assertEqual(s.f_bits, 5)
        self.assertFalse(s.signed)

        s = fixed.UQ(0, 1)
        self.assertEqual(s.i_bits, 0)
        self.assertEqual(s.f_bits, 1)
        self.assertFalse(s.signed)

        s = fixed.UQ(1, 0)
        self.assertEqual(s.i_bits, 1)
        self.assertEqual(s.f_bits, 0)
        self.assertFalse(s.signed)

        with self.assertRaises(TypeError):
            fixed.UQ(-1, 0)

        with self.assertRaises(TypeError):
            fixed.UQ(1, -1)

    def test_shape_sq_init(self):

        s = fixed.SQ(6, 5)
        self.assertEqual(s.i_bits, 6)
        self.assertEqual(s.f_bits, 5)
        self.assertTrue(s.signed)

        s = fixed.SQ(1, 0)
        self.assertEqual(s.i_bits, 1)
        self.assertEqual(s.f_bits, 0)
        self.assertTrue(s.signed)

        with self.assertRaises(TypeError):
            fixed.SQ(0, 1)

        with self.assertRaises(TypeError):
            fixed.SQ(-1, 0)

        with self.assertRaises(TypeError):
            fixed.SQ(1, -1)

    def test_cast_from_shape(self):

        s = fixed.Shape.cast(signed(12), f_bits=4)
        self.assertEqual(s.i_bits, 8)
        self.assertEqual(s.f_bits, 4)
        self.assertTrue(s.signed)

        with self.assertRaises(TypeError):
            fixed.Shape.cast("not a shape")

    def test_cast_to_shape(self):

        fixed_shape = fixed.Shape(unsigned(11), f_bits=5)
        hdl_shape = fixed_shape.as_shape()
        self.assertEqual(hdl_shape.width, 11)
        self.assertFalse(hdl_shape.signed)

    def test_min_max(self):

        self.assertEqual(fixed.UQ(2, 4).max().as_value().__repr__(), "(const 6'd63)")
        self.assertEqual(fixed.UQ(2, 4).min().as_value().__repr__(), "(const 6'd0)")
        self.assertEqual(fixed.UQ(2, 4).max().as_float(), 3.9375)
        self.assertEqual(fixed.UQ(2, 4).min().as_float(), 0)

        self.assertEqual(fixed.UQ(0, 2).max().as_value().__repr__(), "(const 2'd3)")
        self.assertEqual(fixed.UQ(0, 2).min().as_value().__repr__(), "(const 2'd0)")
        self.assertEqual(fixed.UQ(0, 2).max().as_float(), 0.75)
        self.assertEqual(fixed.UQ(0, 2).min().as_float(), 0)

        self.assertEqual(fixed.SQ(2, 4).max().as_value().__repr__(), "(const 6'sd31)")
        self.assertEqual(fixed.SQ(2, 4).min().as_value().__repr__(), "(const 6'sd-32)")
        self.assertEqual(fixed.SQ(2, 4).max().as_float(), 1.9375)
        self.assertEqual(fixed.SQ(2, 4).min().as_float(), -2)

        self.assertEqual(fixed.SQ(1, 0).max().as_value().__repr__(), "(const 1'sd0)")
        self.assertEqual(fixed.SQ(1, 0).min().as_value().__repr__(), "(const 1'sd-1)")
        self.assertEqual(fixed.SQ(1, 0).max().as_float(), 0)
        self.assertEqual(fixed.SQ(1, 0).min().as_float(), -1)

    def test_from_bits(self):

        self.assertEqual(fixed.UQ(2, 4).from_bits(0b100000).as_float(), 2.0)
        self.assertEqual(fixed.UQ(2, 4).from_bits(0b010000).as_float(), 1.0)
        self.assertEqual(fixed.UQ(2, 4).from_bits(0b001000).as_float(), 0.5)
        self.assertEqual(fixed.UQ(2, 4).from_bits(0b000100).as_float(), 0.25)
        self.assertEqual(fixed.UQ(2, 4).from_bits(0b000000).as_float(), 0)

        self.assertEqual(fixed.SQ(2, 4).from_bits(0b000000).as_float(), 0)
        self.assertEqual(fixed.SQ(2, 4).from_bits(0b000001).as_float(), 0.0625)
        self.assertEqual(fixed.SQ(2, 4).from_bits(0b111111).as_float(), -0.0625)
        self.assertEqual(fixed.SQ(2, 4).from_bits(0b010000).as_float(), 1)
        self.assertEqual(fixed.SQ(2, 4).from_bits(0b100000).as_float(), -2)

class TestFixedValue(FHDLTestCase):

    def assertFixedEqual(self, expression, expected, force_expected_shape=False):

        m = Module()
        output = Signal.like(expected if force_expected_shape else expression)
        m.d.comb += output.eq(expression)

        async def testbench(ctx):
            out = ctx.get(output)
            self.assertEqual(out.i_bits, expected.i_bits)
            self.assertEqual(out.f_bits, expected.f_bits)
            self.assertEqual(out.as_float(), expected.as_float())
            self.assertEqual(out.as_value().value, expected.as_value().value)
            self.assertEqual(out.signed, expected.signed)

        sim = Simulator(m)
        sim.add_testbench(testbench)
        sim.run()

    def assertFixedBool(self, expression, expected):

        m = Module()
        output = Signal.like(expression)
        m.d.comb += output.eq(expression)

        async def testbench(ctx):
            self.assertEqual(ctx.get(output), 1 if expected else 0)

        sim = Simulator(m)
        sim.add_testbench(testbench)
        sim.run()

    def test_mul(self):

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 2)) * fixed.Const(0.25, fixed.SQ(1, 2)),
            fixed.Const(0.375, fixed.SQ(4, 4))
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 2)) * fixed.Const(-0.25, fixed.SQ(1, 2)),
            fixed.Const(-0.375, fixed.SQ(4, 4))
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 2)) * 3,
            fixed.Const(4.5, fixed.UQ(5, 2))
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 2)) * -3,
            fixed.Const(-4.5, fixed.SQ(6, 2))
        )

        with self.assertRaises(TypeError):

            self.assertFixedEqual(
                fixed.Const(1.5, fixed.UQ(3, 2)) * 3.5,
                fixed.Const(4.5, fixed.UQ(5, 2))
            )


    def test_add(self):

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 3)) + fixed.Const(0.25, fixed.SQ(1, 2)),
            fixed.Const(1.75, fixed.SQ(5, 3)),
        )

        self.assertFixedEqual(
            fixed.Const(0.5, fixed.UQ(3, 3)) + fixed.Const(-0.75, fixed.SQ(1, 2)),
            fixed.Const(-0.25, fixed.SQ(5, 3))
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 3)) + fixed.Const(0.25, fixed.UQ(1, 2)),
            fixed.Const(1.75, fixed.UQ(4, 3)),
        )

    def test_sub(self):

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.SQ(3, 3)) - fixed.Const(1.75, fixed.SQ(2, 2)),
            fixed.Const(-0.25, fixed.SQ(4, 3)),
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 3)) - fixed.Const(2, fixed.UQ(2, 2)),
            fixed.Const(-0.5, fixed.SQ(4, 3)),
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 3)) - 3,
            fixed.Const(-1.5, fixed.SQ(4, 3)),
        )

        self.assertFixedEqual(
            3 - fixed.Const(1.5, fixed.UQ(3, 3)),
            fixed.Const(1.5, fixed.SQ(5, 3)),
        )

    def test_shift(self):

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 3)) << 1,
            fixed.Const(3.0, fixed.UQ(4, 2)),
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 3)) >> 1,
            fixed.Const(0.75, fixed.UQ(2, 4)),
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.SQ(3, 3)) >> 3,
            fixed.Const(0.1875, fixed.SQ(1, 6)),
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.SQ(3, 3)) >> Const(3, unsigned(2)),
            fixed.Const(0.1875, fixed.SQ(1, 6)),
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 3)) >> Const(3, unsigned(2)),
            fixed.Const(0.1875, fixed.UQ(0, 6)),
        )

        self.assertFixedEqual(
            fixed.Const(1.5, fixed.UQ(3, 3)) >> 3,
            fixed.Const(0.1875, fixed.UQ(0, 6)),
        )

        self.assertFixedEqual(
            fixed.Const(-1.5, fixed.SQ(3, 3)) << 4,
            fixed.Const(-24.0, fixed.SQ(7, 0)),
        )

        with self.assertRaises(ValueError):
            fixed.Const(1.5, fixed.UQ(3, 3)) << -1

        with self.assertRaises(ValueError):
            fixed.Const(1.5, fixed.UQ(3, 3)) >> -1

        with self.assertRaises(TypeError):
            fixed.Const(1.5, fixed.UQ(3, 3)) << Const(-1, signed(2))

        with self.assertRaises(TypeError):
            fixed.Const(1.5, fixed.UQ(3, 3)) >> Const(-1, signed(2))

    def test_abs(self):

        # fixed.SQ -> fixed.UQ

        self.assertFixedEqual(
            abs(fixed.Const(-1.5, fixed.SQ(3, 3))),
            fixed.Const(1.5, fixed.UQ(3, 3))
        )

        self.assertFixedEqual(
            abs(fixed.Const(-1, fixed.SQ(1, 2))),
            fixed.Const(1, fixed.UQ(1, 2))
        )

        self.assertFixedEqual(
            abs(fixed.Const(-4, fixed.SQ(3, 3))),
            fixed.Const(4, fixed.UQ(3, 3))
        )

        # fixed.UQ -> fixed.UQ

        self.assertFixedEqual(
            abs(fixed.Const(7, fixed.UQ(3, 3))),
            fixed.Const(7, fixed.UQ(3, 3))
        )

    def test_neg(self):

        # fixed.SQ -> fixed.SQ

        self.assertFixedEqual(
            -fixed.Const(-1.5, fixed.SQ(3, 3)),
            fixed.Const(1.5, fixed.SQ(4, 3))
        )

        self.assertFixedEqual(
            -fixed.Const(-1, fixed.SQ(1, 2)),
            fixed.Const(1, fixed.SQ(2, 2))
        )

        self.assertFixedEqual(
            -fixed.Const(1.5, fixed.SQ(2, 2)),
            fixed.Const(-1.5, fixed.SQ(3, 2))
        )

        # fixed.UQ -> fixed.SQ

        self.assertFixedEqual(
            -fixed.Const(1.5, fixed.UQ(2, 2)),
            fixed.Const(-1.5, fixed.SQ(3, 2))
        )

    def test_clamp(self):

        self.assertFixedEqual(
            fixed.Const(3, fixed.SQ(3, 3)).clamp(
                fixed.Const(-1),
                fixed.Const(1)),
            fixed.Const(1, fixed.SQ(3, 3))
        )

        self.assertFixedEqual(
            fixed.Const(3, fixed.SQ(3, 3)).clamp(
                fixed.Const(-3),
                fixed.Const(-2)),
            fixed.Const(-2, fixed.SQ(3, 3))
        )

        self.assertFixedEqual(
            fixed.Const(3, fixed.SQ(3, 3)).clamp(
                fixed.Const(-0.5),
                fixed.Const(0.5)),
            fixed.Const(0.5, fixed.SQ(3, 3))
        )

    def test_saturate(self):

        # fixed.SQ -> fixed.SQ

        self.assertFixedEqual(
            fixed.Const(-2, fixed.SQ(3, 3)).saturate(fixed.SQ(1, 1)),
            fixed.Const(-1, fixed.SQ(1, 1))
        )

        self.assertFixedEqual(
            fixed.Const(-10.25, fixed.SQ(5, 3)).saturate(fixed.SQ(3, 1)),
            fixed.Const(-4, fixed.SQ(3, 1))
        )

        self.assertFixedEqual(
            fixed.Const(14.25, fixed.SQ(8, 3)).saturate(fixed.SQ(4, 2)),
            fixed.Const(7.75, fixed.SQ(4, 2))
        )

        self.assertFixedEqual(
            fixed.Const(0.995, fixed.SQ(1, 8)).saturate(fixed.SQ(1, 4)),
            fixed.Const(0.9375, fixed.SQ(1, 4))
        )

        with self.assertRaises(ValueError):
            fixed.Const(0, fixed.SQ(8, 0)).saturate(fixed.SQ(9, 0)),

        # XXX: this 'odd' behaviour is an artifact of truncation rounding,
        # and should be revisited when we have more rounding strategies.

        self.assertFixedEqual(
            fixed.Const(-0.995, fixed.SQ(2, 8)).saturate(fixed.SQ(2, 4)),
            fixed.Const(-1, fixed.SQ(2, 4))
        )

        # fixed.UQ -> fixed.UQ

        self.assertFixedEqual(
            fixed.Const(15, fixed.UQ(5, 2)).saturate(fixed.UQ(3, 1)),
            fixed.Const(7.5, fixed.UQ(3, 1))
        )

        # fixed.SQ -> fixed.UQ

        self.assertFixedEqual(
            fixed.Const(14.25, fixed.SQ(8, 3)).saturate(fixed.UQ(2, 2)),
            fixed.Const(3.75, fixed.UQ(2, 2))
        )

        self.assertFixedEqual(
            fixed.Const(-14.25, fixed.SQ(8, 3)).saturate(fixed.UQ(2, 2)),
            fixed.Const(0, fixed.UQ(2, 2))
        )

        # fixed.UQ -> fixed.SQ

        self.assertFixedEqual(
            fixed.Const(255, fixed.UQ(8, 2)).saturate(fixed.SQ(8, 2)),
            fixed.Const(127.75, fixed.SQ(8, 2))
        )

    def test_lt(self):

        self.assertFixedBool(
            fixed.Const(0.75, fixed.SQ(1, 2)) < fixed.Const(0.5, fixed.SQ(1, 2)), False)
        self.assertFixedBool(
            fixed.Const(0.5, fixed.SQ(1, 2)) < fixed.Const(0.75, fixed.SQ(1, 2)), True)
        self.assertFixedBool(
            fixed.Const(0.75, fixed.SQ(1, 2)) < fixed.Const(-0.5, fixed.SQ(1, 2)), False)
        self.assertFixedBool(
            fixed.Const(-0.5, fixed.SQ(1, 2)) < fixed.Const(0.75, fixed.SQ(1, 2)), True)
        self.assertFixedBool(
            fixed.Const(-0.25, fixed.SQ(1, 2)) < fixed.Const(0, fixed.SQ(1, 2)), True)
        self.assertFixedBool(
            fixed.Const(0.25, fixed.SQ(1, 2)) < fixed.Const(0, fixed.SQ(1, 2)), False)
        self.assertFixedBool(
            fixed.Const(-0.25, fixed.SQ(1, 2)) < fixed.Const(0), True)
        self.assertFixedBool(
            fixed.Const(0.25, fixed.SQ(1, 2)) < fixed.Const(0), False)
        self.assertFixedBool(
            fixed.Const(0, fixed.SQ(1, 2)) < fixed.Const(0), False)
        self.assertFixedBool(
            fixed.Const(0) < fixed.Const(0), False)
        self.assertFixedBool(
            fixed.Const(0) < 1, True)
        self.assertFixedBool(
            fixed.Const(0) < -1, False)

    def test_equality(self):

        self.assertFixedBool(fixed.Const(0) == 0, True)
        self.assertFixedBool(fixed.Const(0) == fixed.Const(0), True)
        self.assertFixedBool(fixed.Const(0.5) == fixed.Const(0.5), True)
        self.assertFixedBool(fixed.Const(0.5) == fixed.Const(0.75), False)
        self.assertFixedBool(fixed.Const(0.501) == fixed.Const(0.5), False)

        self.assertFixedBool(fixed.Const(0.5) != fixed.Const(0.5), False)
        self.assertFixedBool(fixed.Const(0.5) != fixed.Const(0.75), True)

        with self.assertRaises(TypeError):
            self.assertFixedBool(0.5 == fixed.Const(0.5), False)

    def test_eq(self):

        self.assertFixedEqual(
            fixed.Const(-1, fixed.SQ(2, 1)),
            fixed.Const(-1, fixed.SQ(5, 1)),
            force_expected_shape=True
        )

        self.assertFixedEqual(
            fixed.SQ(1, 1).max(),
            fixed.Const(0.5, fixed.SQ(5, 1)),
            force_expected_shape=True
        )

        self.assertFixedEqual(
            fixed.SQ(1, 1).max(),
            fixed.Const(0.5, fixed.SQ(5, 1)),
            force_expected_shape=True
        )

        self.assertFixedEqual(
            fixed.Const(0.25, fixed.SQ(5, 5)),
            fixed.Const(0.0, fixed.SQ(5, 1)),
            force_expected_shape=True
        )

        # XXX: truncation rounding again

        self.assertFixedEqual(
            fixed.Const(-0.25, fixed.SQ(5, 5)),
            fixed.Const(-0.5, fixed.SQ(5, 1)),
            force_expected_shape=True
        )

        # XXX: .eq() from fixed.SQ <-> fixed.UQ may over/underflow.
        # fixed.SQ -> fixed.UQ: may overflow if fixed.SQ is negative
        # fixed.UQ -> fixed.SQ: may overflow if i_bits (fixed.UQ) >= i_bits (fixed.SQ)
        # same signedness: may overflow if i_bits > i_bits
        # Should these really be prohibited completely?

        self.assertFixedEqual(
            fixed.Const(-10, fixed.SQ(5, 2)),
            fixed.Const(22, fixed.UQ(5, 2)),
            force_expected_shape=True
        )

        self.assertFixedEqual(
            fixed.Const(15, fixed.UQ(4, 2)),
            fixed.Const(-1, fixed.SQ(4, 2)),
            force_expected_shape=True
        )


    def test_float_size_determination(self):

        self.assertFixedEqual(
            fixed.Const(0.03125),
            fixed.Const(0.03125, fixed.UQ(0, 5))
        )

        self.assertFixedEqual(
            fixed.Const(-0.03125),
            fixed.Const(-0.03125, fixed.SQ(1, 5))
        )

        self.assertFixedEqual(
            fixed.Const(-0.5),
            fixed.Const(-0.5, fixed.SQ(1, 1))
        )

        self.assertFixedEqual(
            fixed.Const(10),
            fixed.Const(10, fixed.UQ(4, 0))
        )

        self.assertFixedEqual(
            fixed.Const(-10),
            fixed.Const(-10, fixed.SQ(5, 0))
        )

        self.assertFixedEqual(
            fixed.Const(0),
            fixed.Const(0, fixed.UQ(1, 0))
        )

        self.assertFixedEqual(
            fixed.Const(-1.0),
            fixed.Const(-1.0, fixed.SQ(1, 0))
        )

        self.assertFixedEqual(
            fixed.Const(-2.0),
            fixed.Const(-2.0, fixed.SQ(2, 0))
        )

        self.assertFixedEqual(
            fixed.Const(-2),
            fixed.Const(-2, fixed.SQ(2, 0))
        )

        self.assertFixedEqual(
            fixed.Const(2),
            fixed.Const(2, fixed.UQ(2, 0))
        )
