# Based on latest iteration of fixed point types RFC, which
# is an effort undertaken by the Amaranth community, as well
# as an early (incomplete) RFC implementation by zyp@
#
# RFC (community): https://github.com/amaranth-lang/rfcs/pull/41
# Early implementation (zyp@): https://github.com/amaranth-lang/amaranth/pull/1005
#
# SPDX-License-Identifier: BSD-3-Clause

from .. import hdl, Mux
from ..utils import bits_for

__all__ = ["Shape", "SQ", "UQ", "Value", "Const"]

class Shape(hdl.ShapeCastable):

    def __init__(self, shape, f_bits=0):
        self._storage_shape = shape
        self.i_bits, self.f_bits = shape.width-f_bits, f_bits
        if self.i_bits < 0 or self.f_bits < 0:
            raise TypeError(f"fixed.Shape may not be created with negative bit widths (i_bits={self.i_bits}, f_bits={self.f_bits})")
        if shape.signed and self.i_bits == 0:
           raise TypeError(f"A signed fixed.Shape cannot be created with i_bits=0")
        if self.i_bits + self.f_bits == 0:
            raise TypeError(f"fixed.Shape may not be created with zero width")

    @property
    def signed(self):
        return self._storage_shape.signed

    @staticmethod
    def cast(shape, f_bits=0):
        if not isinstance(shape, hdl.Shape):
            raise TypeError(f"Object {shape!r} cannot be converted to a fixed.Shape")
        return Shape(shape, f_bits)

    def const(self, value):
        if value is None:
            value = 0
        return Const(value, self)._target

    def as_shape(self):
        return self._storage_shape

    def __call__(self, target):
        return Value(self, target)

    def min(self):
        c = Const(0, self)
        c._value = c._min_value()
        return c

    def max(self):
        c = Const(0, self)
        c._value = c._max_value()
        return c

    def from_bits(self, raw):
        c = Const(0, self)
        c._value = raw
        if self.signed and raw > c._max_value():
            # 2s complement signed value, but `raw` was unsigned.
            c._value = c._min_value() + c._value - c._max_value() - 1
        if c._value < c._min_value() or c._value > c._max_value():
            raise ValueError(
                f"{raw} outside expected range {c._min_value()}, {c._max_value()}")
        return c

    def __repr__(self):
        return f"{'SQ' if self.signed else 'UQ'}({self.i_bits}, {self.f_bits})"


class SQ(Shape):
    def __init__(self, i_bits, f_bits):
        super().__init__(hdl.Shape(i_bits + f_bits, signed=True), f_bits)


class UQ(Shape):
    def __init__(self, i_bits, f_bits):
        super().__init__(hdl.Shape(i_bits + f_bits, signed=False), f_bits)


class Value(hdl.ValueCastable):
    def __init__(self, shape, target):
        self._shape = shape
        if self.signed and not target.shape().signed:
            # When methods bit-pick or concatenate to
            # the _target of a Value, and then use this
            # to reconstruct a Value, we may lose the
            # signedness of its underlying _target.
            self._target = target.as_signed()
        else:
            self._target = target

    @property
    def signed(self):
        return self._shape.signed

    @staticmethod
    def cast(value, f_bits=0):
        return Shape.cast(value.shape(), f_bits)(value)

    @property
    def i_bits(self):
        return self._shape.i_bits

    @property
    def f_bits(self):
        return self._shape.f_bits

    def shape(self):
        return self._shape

    def as_value(self):
        return self._target

    def eq(self, other):
        if isinstance(other, hdl.Value):
            return self.as_value().eq(other)
        elif isinstance(other, int) or isinstance(other, float):
            other = Const(other, self.shape())
        elif not isinstance(other, Value):
            raise TypeError(f"Object {other!r} cannot be converted to a fixed.Value")
        other = other.reshape(self.f_bits)
        return self.as_value().eq(other.as_value())

    def reshape(self, f_bits):
        # If we're increasing precision, extend with more fractional bits. If we're
        # reducing precision, truncate bits.
        shape = hdl.Shape(self.i_bits + f_bits, signed=self.signed)
        if f_bits > self.f_bits:
            result = Shape(shape, f_bits)(hdl.Cat(hdl.Const(0, f_bits - self.f_bits), self.as_value()))
        else:
            result = Shape(shape, f_bits)(self.as_value()[self.f_bits - f_bits:])
        return result

    def truncate(self, f_bits=0):
        if f_bits > self.f_bits:
            raise ValueError(
                f"`.truncate(f_bits={f_bits}) exceeds the underlying type's f_bits={self.f_bits}. "
                "Use `.reshape()` to instead extend `f_bits`."
            )
        return self.reshape(f_bits)

    def clamp(self, lo, hi):
        if not isinstance(lo, Value) or not isinstance(hi, Value):
            raise TypeError(f"Cannot `clamp` as lo, hi are not fixed.Value")
        lo = lo.reshape(self.f_bits)
        hi = hi.reshape(self.f_bits)
        return Value(self.shape(), Mux(
            self > hi, hi,
            Mux(self < lo, lo, self)
        ))

    def saturate(self, shape):
        if not isinstance(shape, Shape):
            raise TypeError(f"Cannot `saturate` to bounds of {shape!r} as it is not a fixed.Shape")
        if not shape.i_bits <= self.i_bits:
            raise ValueError(f"Cannot `saturate`: shape.i_bits={shape.i_bits} > self.i_bits={self.i_bits} would have no effect.")
        clamped = self.reshape(shape.f_bits).clamp(shape.min(), shape.max())
        return Value(shape, clamped.as_value())

    def _binary_op(self, rhs, operator, callable_f_bits = lambda a, b: max(a, b), pre_reshape=True, post_cast=True):
        if isinstance(rhs, hdl.Value):
            rhs = Value.cast(rhs)
        elif isinstance(rhs, int):
            rhs = Const(rhs)
        elif not isinstance(rhs, Value):
            raise TypeError(f"Object {rhs!r} cannot be converted to a fixed.Value")
        f_bits = callable_f_bits(self.f_bits, rhs.f_bits)
        if pre_reshape:
            lhs = self.reshape(f_bits)
            rhs = rhs.reshape(f_bits)
        else:
            lhs = self
        value = getattr(lhs.as_value(), operator)(rhs.as_value())
        return Value.cast(value, f_bits) if post_cast else value

    def __mul__(self, other):
        return self._binary_op(other, '__mul__', lambda a, b: a + b, pre_reshape=False)

    __rmul__ = __mul__

    def __add__(self, other):
        return self._binary_op(other, '__add__')

    __radd__ = __add__

    def __sub__(self, other):
        return self._binary_op(other, '__sub__')

    def __rsub__(self, other):
        return -self.__sub__(other)

    def __pos__(self):
        return self

    def __neg__(self):
        return Value.cast(-self.as_value(), self.f_bits)

    def __abs__(self):
        return Value.cast(abs(self.as_value()), self.f_bits)

    def __lshift__(self, other):
        if isinstance(other, int):
            if other < 0:
                raise ValueError("Shift amount cannot be negative")

            if other > self.f_bits:
                value = hdl.Cat(hdl.Const(0, other - self.f_bits), self.as_value())
                return Value.cast(value.as_signed() if self.signed else value)
            else:
                return Value.cast(self.as_value(), self.f_bits - other)
        elif not isinstance(other, hdl.Value):
            raise TypeError("Shift amount must be an integer value")
        if other.signed:
            raise TypeError("Shift amount must be unsigned")
        return Value.cast(self.as_value() << other, self.f_bits)

    def __rshift__(self, other):
        if isinstance(other, int):
            if other < 0:
                raise ValueError("Shift amount cannot be negative")
            # Extend f_bits by fixed shift amount.
            i_bits = self.i_bits - other
            f_bits = self.f_bits + other
            numerator = self.as_value()
        elif isinstance(other, hdl.Value):
            if other.shape().signed:
                raise TypeError("Shift amount must be unsigned")
            # Extend by maximum possible shift represented by hdl.Value.
            f_bits = self.f_bits + 2**other.shape().width - 1
            i_bits = self.i_bits - (f_bits - self.f_bits)
            numerator = self.reshape(f_bits).as_value() >> other
        else:
            raise TypeError("Shift amount must be an integer value")
        # Always keep at least 1 sign bit and prohibit negative i_bits.
        # TODO: should we concat to _target for sign extension? (likely unnecessary)
        if self.signed:
            return SQ(max(1, i_bits), f_bits)(numerator)
        else:
            return UQ(max(0, i_bits), f_bits)(numerator)

    def _binary_compare(self, other, operator):
        return self._binary_op(other, operator, post_cast=False)

    def __lt__(self, other):
        return self._binary_compare(other, '__lt__')

    def __ge__(self, other):
        return self._binary_compare(other, '__ge__')

    def __gt__(self, other):
        return self._binary_compare(other, '__gt__')

    def __le__(self, other):
        return self._binary_compare(other, '__le__')

    def __eq__(self, other):
        return self._binary_compare(other, '__eq__')

    def __repr__(self):
        return f"fixed.Value({self._shape!r}, {self._target!r})"


class Const(Value):
    def __init__(self, value, shape=None, clamp=False):

        if isinstance(value, float) or isinstance(value, int):
            num, den = value.as_integer_ratio()
        elif isinstance(value, Const):
            # FIXME: Memory inits seem to construct a fixed.Const with fixed.Const
            self._shape = value._shape
            self._value = value._value
            return
        else:
            raise TypeError(f"Object {value!r} cannot be converted to a fixed.Const")

        # Determine smallest possible shape if not already selected.
        if shape is None:
            signed = num < 0
            f_bits = bits_for(den) - 1
            i_bits = max(0, bits_for(abs(num)) - f_bits)
            shape = SQ(i_bits+1, f_bits) if signed else UQ(i_bits, f_bits)

        # Scale value to given precision.
        if 2**shape.f_bits > den:
            num *= 2**shape.f_bits // den
        elif 2**shape.f_bits < den:
            num = round(num / (den // 2**shape.f_bits))
        value = num

        self._shape = shape

        if value > self._max_value():
            if clamp:
                value = self._max_value()
            else:
                raise ValueError(f"Constant {value!r} does not fit in {shape!r}.")

        if value < self._min_value():
            if clamp:
                value = self._min_value()
            else:
                raise ValueError(f"Constant {value!r} does not fit in {shape!r}. ")

        self._value = value

    def _max_value(self):
        return 2**(self._shape.i_bits +
                   self._shape.f_bits - (1 if self.signed else 0)) - 1

    def _min_value(self):
        if self._shape.signed:
            return -1 * 2**(self._shape.i_bits +
                            self._shape.f_bits - 1)
        else:
            return 0

    @property
    def _target(self):
        return hdl.Const(self._value, self._shape.as_shape())

    def as_integer_ratio(self):
        return self._value, 2**self.f_bits

    def as_float(self):
        return self._value / 2**self.f_bits

    def __repr__(self):
        return f"fixed.Const({self.as_float()}, {self._shape!r})"

