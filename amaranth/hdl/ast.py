from abc import ABCMeta, abstractmethod
import inspect
import warnings
import functools
from collections import OrderedDict
from collections.abc import Iterable, MutableMapping, MutableSet, MutableSequence
from enum import Enum, EnumMeta
from itertools import chain

from ._repr import *
from .. import tracer
from .._utils import *
from .._utils import _ignore_deprecated
from .._unused import *


__all__ = [
    "Shape", "signed", "unsigned", "ShapeCastable", "ShapeLike",
    "Value", "Const", "C", "AnyConst", "AnySeq", "Operator", "Mux", "Part", "Slice", "Cat", "Repl",
    "Array", "ArrayProxy",
    "Signal", "ClockSignal", "ResetSignal",
    "ValueCastable", "ValueLike",
    "Sample", "Past", "Stable", "Rose", "Fell", "Initial",
    "Statement", "Switch",
    "Property", "Assign", "Assert", "Assume", "Cover",
    "ValueKey", "ValueDict", "ValueSet", "SignalKey", "SignalDict", "SignalSet",
]


class DUID:
    """Deterministic Unique IDentifier."""
    __next_uid = 0
    def __init__(self):
        self.duid = DUID.__next_uid
        DUID.__next_uid += 1


class ShapeCastable:
    """Interface of user-defined objects that can be cast to :class:`Shape` s.

    An object deriving from :class:`ShapeCastable` is automatically converted to a :class:`Shape`
    when it is used in a context where a :class:`Shape` is expected. Such objects can contain
    a richer description of the shape than what is supported by the core Amaranth language, yet
    still be transparently used with it.
    """
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, "as_shape"):
            raise TypeError(f"Class '{cls.__name__}' deriving from `ShapeCastable` must override "
                            f"the `as_shape` method")
        if not (hasattr(cls, "__call__") and inspect.isfunction(cls.__call__)):
            raise TypeError(f"Class '{cls.__name__}' deriving from `ShapeCastable` must override "
                            f"the `__call__` method")
        if not hasattr(cls, "const"):
            raise TypeError(f"Class '{cls.__name__}' deriving from `ShapeCastable` must override "
                            f"the `const` method")

    def _value_repr(self, value):
        return (Repr(FormatInt(), value),)


class Shape:
    """Bit width and signedness of a value.

    A ``Shape`` can be constructed using:
      * explicit bit width and signedness;
      * aliases :func:`signed` and :func:`unsigned`;
      * casting from a variety of objects.

    A ``Shape`` can be cast from:
      * an integer, where the integer specifies the bit width;
      * a range, where the result is wide enough to represent any element of the range, and is
        signed if any element of the range is signed;
      * an :class:`Enum` with all integer members or :class:`IntEnum`, where the result is wide
        enough to represent any member of the enumeration, and is signed if any member of
        the enumeration is signed.

    Parameters
    ----------
    width : int
        The number of bits in the representation, including the sign bit (if any).
    signed : bool
        If ``False``, the value is unsigned. If ``True``, the value is signed two's complement.
    """
    def __init__(self, width=1, signed=False):
        if not isinstance(width, int):
            raise TypeError(f"Width must be an integer, not {width!r}")
        if not signed and width < 0:
            raise TypeError(f"Width of an unsigned value must be zero or a positive integer, "
                            f"not {width}")
        if signed and width <= 0:
            raise TypeError(f"Width of a signed value must be a positive integer, not {width}")
        self.width = width
        self.signed = bool(signed)

    # The algorithm for inferring shape for standard Python enumerations is factored out so that
    # `Shape.cast()` and Amaranth's `EnumMeta.as_shape()` can both use it.
    @staticmethod
    def _cast_plain_enum(obj):
        signed = False
        width  = 0
        for member in obj:
            try:
                member_shape = Const.cast(member.value).shape()
            except TypeError as e:
                raise TypeError("Only enumerations whose members have constant-castable "
                                "values can be used in Amaranth code")
            if not signed and member_shape.signed:
                signed = True
                width  = max(width + 1, member_shape.width)
            elif signed and not member_shape.signed:
                width  = max(width, member_shape.width + 1)
            else:
                width  = max(width, member_shape.width)
        return Shape(width, signed)

    @staticmethod
    def cast(obj, *, src_loc_at=0):
        while True:
            if isinstance(obj, Shape):
                return obj
            elif isinstance(obj, ShapeCastable):
                new_obj = obj.as_shape()
            elif isinstance(obj, int):
                return Shape(obj)
            elif isinstance(obj, range):
                if len(obj) == 0:
                    return Shape(0)
                signed = obj[0] < 0 or obj[-1] < 0
                width  = max(bits_for(obj[0], signed),
                             bits_for(obj[-1], signed))
                return Shape(width, signed)
            elif isinstance(obj, type) and issubclass(obj, Enum):
                # For compatibility with third party enumerations, handle them as if they were
                # defined as subclasses of lib.enum.Enum with no explicitly specified shape.
                return Shape._cast_plain_enum(obj)
            else:
                raise TypeError(f"Object {obj!r} cannot be converted to an Amaranth shape")
            if new_obj is obj:
                raise RecursionError(f"Shape-castable object {obj!r} casts to itself")
            obj = new_obj

    def __repr__(self):
        if self.signed:
            return f"signed({self.width})"
        else:
            return f"unsigned({self.width})"

    def __eq__(self, other):
        return (isinstance(other, Shape) and
                self.width == other.width and self.signed == other.signed)


class _ShapeLikeMeta(type):
    def __subclasscheck__(cls, subclass):
        return issubclass(subclass, (Shape, ShapeCastable, int, range, EnumMeta)) or subclass is ShapeLike

    def __instancecheck__(cls, instance):
        if isinstance(instance, (Shape, ShapeCastable, range)):
            return True
        if isinstance(instance, int):
            return instance >= 0
        if isinstance(instance, EnumMeta):
            for member in instance:
                if not isinstance(member.value, ValueLike):
                    return False
            return True
        return False


@final
class ShapeLike(metaclass=_ShapeLikeMeta):
    """An abstract class representing all objects that can be cast to a :class:`Shape`.

    ``issubclass(cls, ShapeLike)`` returns ``True`` for:

    - :class:`Shape`
    - :class:`ShapeCastable` and its subclasses
    - ``int`` and its subclasses
    - ``range`` and its subclasses
    - :class:`enum.EnumMeta` and its subclasses
    - :class:`ShapeLike` itself

    ``isinstance(obj, ShapeLike)`` returns ``True`` for:

    - :class:`Shape` instances
    - :class:`ShapeCastable` instances
    - non-negative ``int`` values
    - ``range`` instances
    - :class:`enum.Enum` subclasses where all values are :ref:`value-like <lang-valuelike>`

    This class is only usable for the above checks — no instances and no (non-virtual)
    subclasses can be created.
    """

    def __new__(cls, *args, **kwargs):
        raise TypeError("ShapeLike is an abstract class and cannot be constructed")


def unsigned(width):
    """Shorthand for ``Shape(width, signed=False)``."""
    return Shape(width, signed=False)


def signed(width):
    """Shorthand for ``Shape(width, signed=True)``."""
    return Shape(width, signed=True)


def _overridable_by_reflected(method_name):
    """Allow overriding the decorated method.

    Allows :class:`ValueCastable` to override the decorated method by implementing
    a reflected method named ``method_name``. Intended for operators, but
    also usable for other methods that have a reflected counterpart.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(self, other):
            if isinstance(other, ValueCastable) and hasattr(other, method_name):
                res = getattr(other, method_name)(self)
                if res is not NotImplemented:
                    return res
            return f(self, other)
        return wrapper
    return decorator


class Value(metaclass=ABCMeta):
    @staticmethod
    def cast(obj):
        """Converts ``obj`` to an Amaranth value.

        Booleans and integers are wrapped into a :class:`Const`. Enumerations whose members are
        all integers are converted to a :class:`Const` with a shape that fits every member.
        :class:`ValueCastable` objects are recursively cast to an Amaranth value.
        """
        while True:
            if isinstance(obj, Value):
                return obj
            elif isinstance(obj, ValueCastable):
                new_obj = obj.as_value()
            elif isinstance(obj, Enum):
                return Const(obj.value, Shape.cast(type(obj)))
            elif isinstance(obj, int):
                return Const(obj)
            else:
                raise TypeError(f"Object {obj!r} cannot be converted to an Amaranth value")
            if new_obj is obj:
                raise RecursionError(f"Value-castable object {obj!r} casts to itself")
            obj = new_obj

    def __init__(self, *, src_loc_at=0):
        super().__init__()
        self.src_loc = tracer.get_src_loc(1 + src_loc_at)

    def __bool__(self):
        raise TypeError("Attempted to convert Amaranth value to Python boolean")

    def __pos__(self):
        return self

    def __invert__(self):
        return Operator("~", [self])
    def __neg__(self):
        return Operator("-", [self])

    @_overridable_by_reflected("__radd__")
    def __add__(self, other):
        return Operator("+", [self, other], src_loc_at=1)
    def __radd__(self, other):
        return Operator("+", [other, self])
    @_overridable_by_reflected("__rsub__")
    def __sub__(self, other):
        return Operator("-", [self, other], src_loc_at=1)
    def __rsub__(self, other):
        return Operator("-", [other, self])

    @_overridable_by_reflected("__rmul__")
    def __mul__(self, other):
        return Operator("*", [self, other], src_loc_at=1)
    def __rmul__(self, other):
        return Operator("*", [other, self])

    @_overridable_by_reflected("__rmod__")
    def __mod__(self, other):
        return Operator("%", [self, other], src_loc_at=1)
    def __rmod__(self, other):
        return Operator("%", [other, self])
    @_overridable_by_reflected("__rfloordiv__")
    def __floordiv__(self, other):
        return Operator("//", [self, other], src_loc_at=1)
    def __rfloordiv__(self, other):
        return Operator("//", [other, self])

    def __check_shamt(self):
        if self.shape().signed:
            # Neither Python nor HDLs implement shifts by negative values; prohibit any shifts
            # by a signed value to make sure the shift amount can always be interpreted as
            # an unsigned value.
            raise TypeError("Shift amount must be unsigned")
    @_overridable_by_reflected("__rlshift__")
    def __lshift__(self, other):
        other = Value.cast(other)
        other.__check_shamt()
        return Operator("<<", [self, other], src_loc_at=1)
    def __rlshift__(self, other):
        self.__check_shamt()
        return Operator("<<", [other, self])
    @_overridable_by_reflected("__rrshift__")
    def __rshift__(self, other):
        other = Value.cast(other)
        other.__check_shamt()
        return Operator(">>", [self, other], src_loc_at=1)
    def __rrshift__(self, other):
        self.__check_shamt()
        return Operator(">>", [other, self])

    @_overridable_by_reflected("__rand__")
    def __and__(self, other):
        return Operator("&", [self, other], src_loc_at=1)
    def __rand__(self, other):
        return Operator("&", [other, self])
    @_overridable_by_reflected("__rxor__")
    def __xor__(self, other):
        return Operator("^", [self, other], src_loc_at=1)
    def __rxor__(self, other):
        return Operator("^", [other, self])
    @_overridable_by_reflected("__ror__")
    def __or__(self, other):
        return Operator("|", [self, other], src_loc_at=1)
    def __ror__(self, other):
        return Operator("|", [other, self])

    @_overridable_by_reflected("__eq__")
    def __eq__(self, other):
        return Operator("==", [self, other], src_loc_at=1)
    @_overridable_by_reflected("__ne__")
    def __ne__(self, other):
        return Operator("!=", [self, other], src_loc_at=1)
    @_overridable_by_reflected("__gt__")
    def __lt__(self, other):
        return Operator("<", [self, other], src_loc_at=1)
    @_overridable_by_reflected("__ge__")
    def __le__(self, other):
        return Operator("<=", [self, other], src_loc_at=1)
    @_overridable_by_reflected("__lt__")
    def __gt__(self, other):
        return Operator(">", [self, other], src_loc_at=1)
    @_overridable_by_reflected("__le__")
    def __ge__(self, other):
        return Operator(">=", [self, other], src_loc_at=1)

    def __abs__(self):
        if self.shape().signed:
            return Mux(self >= 0, self, -self)[:len(self)]
        else:
            return self

    def __len__(self):
        return self.shape().width

    def __getitem__(self, key):
        n = len(self)
        if isinstance(key, int):
            if key not in range(-n, n):
                raise IndexError(f"Index {key} is out of bounds for a {n}-bit value")
            if key < 0:
                key += n
            return Slice(self, key, key + 1, src_loc_at=1)
        elif isinstance(key, slice):
            start, stop, step = key.indices(n)
            if step != 1:
                return Cat(self[i] for i in range(start, stop, step))
            return Slice(self, start, stop, src_loc_at=1)
        else:
            raise TypeError(f"Cannot index value with {key!r}")

    def as_unsigned(self):
        """Conversion to unsigned.

        Returns
        -------
        Value, out
            This ``Value`` reinterpreted as a unsigned integer.
        """
        return Operator("u", [self])

    def as_signed(self):
        """Conversion to signed.

        Returns
        -------
        Value, out
            This ``Value`` reinterpreted as a signed integer.
        """
        return Operator("s", [self])

    def bool(self):
        """Conversion to boolean.

        Returns
        -------
        Value, out
            ``1`` if any bits are set, ``0`` otherwise.
        """
        return Operator("b", [self])

    def any(self):
        """Check if any bits are ``1``.

        Returns
        -------
        Value, out
            ``1`` if any bits are set, ``0`` otherwise.
        """
        return Operator("r|", [self])

    def all(self):
        """Check if all bits are ``1``.

        Returns
        -------
        Value, out
            ``1`` if all bits are set, ``0`` otherwise.
        """
        return Operator("r&", [self])

    def xor(self):
        """Compute pairwise exclusive-or of every bit.

        Returns
        -------
        Value, out
            ``1`` if an odd number of bits are set, ``0`` if an even number of bits are set.
        """
        return Operator("r^", [self])

    def implies(premise, conclusion):
        """Implication.

        Returns
        -------
        Value, out
            ``0`` if ``premise`` is true and ``conclusion`` is not, ``1`` otherwise.
        """
        return ~premise | conclusion

    def bit_select(self, offset, width):
        """Part-select with bit granularity.

        Selects a constant width but variable offset part of a ``Value``, such that successive
        parts overlap by all but 1 bit.

        Parameters
        ----------
        offset : Value, int
            Index of first selected bit.
        width : int
            Number of selected bits.

        Returns
        -------
        Part, out
            Selected part of the ``Value``
        """
        offset = Value.cast(offset)
        if type(offset) is Const and isinstance(width, int):
            return self[offset.value:offset.value + width]
        return Part(self, offset, width, stride=1, src_loc_at=1)

    def word_select(self, offset, width):
        """Part-select with word granularity.

        Selects a constant width but variable offset part of a ``Value``, such that successive
        parts do not overlap.

        Parameters
        ----------
        offset : Value, int
            Index of first selected word.
        width : int
            Number of selected bits.

        Returns
        -------
        Part, out
            Selected part of the ``Value``
        """
        offset = Value.cast(offset)
        if type(offset) is Const and isinstance(width, int):
            return self[offset.value * width:(offset.value + 1) * width]
        return Part(self, offset, width, stride=width, src_loc_at=1)

    def matches(self, *patterns):
        """Pattern matching.

        Matches against a set of patterns, which may be integers or bit strings, recognizing
        the same grammar as ``Case()``.

        Parameters
        ----------
        patterns : int or str
            Patterns to match against.

        Returns
        -------
        Value, out
            ``1`` if any pattern matches the value, ``0`` otherwise.
        """
        matches = []
        # This code should accept exactly the same patterns as `with m.Case(...):`.
        for pattern in patterns:
            if isinstance(pattern, str) and any(bit not in "01- \t" for bit in pattern):
                raise SyntaxError("Match pattern '{}' must consist of 0, 1, and - (don't care) "
                                  "bits, and may include whitespace"
                                  .format(pattern))
            if (isinstance(pattern, str) and
                    len("".join(pattern.split())) != len(self)):
                raise SyntaxError("Match pattern '{}' must have the same width as match value "
                                  "(which is {})"
                                  .format(pattern, len(self)))
            if isinstance(pattern, str):
                pattern = "".join(pattern.split()) # remove whitespace
                mask    = int(pattern.replace("0", "1").replace("-", "0"), 2)
                pattern = int(pattern.replace("-", "0"), 2)
                matches.append((self & mask) == pattern)
            else:
                try:
                    orig_pattern, pattern = pattern, Const.cast(pattern)
                except TypeError as e:
                    raise SyntaxError("Match pattern must be a string or a constant-castable "
                                      "expression, not {!r}"
                                      .format(pattern)) from e
                pattern_len = bits_for(pattern.value)
                if pattern_len > len(self):
                    warnings.warn("Match pattern '{!r}' ({}'{:b}) is wider than match value "
                                  "(which has width {}); comparison will never be true"
                                  .format(orig_pattern, pattern_len, pattern.value, len(self)),
                                  SyntaxWarning, stacklevel=2)
                    continue
                matches.append(self == pattern)
        if not matches:
            return Const(1)
        elif len(matches) == 1:
            return matches[0]
        else:
            return Cat(*matches).any()

    def shift_left(self, amount):
        """Shift left by constant amount.

        Parameters
        ----------
        amount : int
            Amount to shift by.

        Returns
        -------
        Value, out
            If the amount is positive, the input shifted left. Otherwise, the input shifted right.
        """
        if not isinstance(amount, int):
            raise TypeError(f"Shift amount must be an integer, not {amount!r}")
        if amount < 0:
            return self.shift_right(-amount)
        if self.shape().signed:
            return Cat(Const(0, amount), self).as_signed()
        else:
            return Cat(Const(0, amount), self) # unsigned

    def shift_right(self, amount):
        """Shift right by constant amount.

        Parameters
        ----------
        amount : int
            Amount to shift by.

        Returns
        -------
        Value, out
            If the amount is positive, the input shifted right. Otherwise, the input shifted left.
        """
        if not isinstance(amount, int):
            raise TypeError(f"Shift amount must be an integer, not {amount!r}")
        if amount < 0:
            return self.shift_left(-amount)
        if self.shape().signed:
            return self[amount:].as_signed()
        else:
            return self[amount:] # unsigned

    def rotate_left(self, amount):
        """Rotate left by constant amount.

        Parameters
        ----------
        amount : int
            Amount to rotate by.

        Returns
        -------
        Value, out
            If the amount is positive, the input rotated left. Otherwise, the input rotated right.
        """
        if not isinstance(amount, int):
            raise TypeError(f"Rotate amount must be an integer, not {amount!r}")
        if len(self) != 0:
            amount %= len(self)
        return Cat(self[-amount:], self[:-amount]) # meow :3

    def rotate_right(self, amount):
        """Rotate right by constant amount.

        Parameters
        ----------
        amount : int
            Amount to rotate by.

        Returns
        -------
        Value, out
            If the amount is positive, the input rotated right. Otherwise, the input rotated right.
        """
        if not isinstance(amount, int):
            raise TypeError(f"Rotate amount must be an integer, not {amount!r}")
        if len(self) != 0:
            amount %= len(self)
        return Cat(self[amount:], self[:amount])

    def replicate(self, count):
        """Replication.

        A ``Value`` is replicated (repeated) several times to be used
        on the RHS of assignments::

            len(v.replicate(n)) == len(v) * n

        Parameters
        ----------
        count : int
            Number of replications.

        Returns
        -------
        Value, out
            Replicated value.
        """
        if not isinstance(count, int) or count < 0:
            raise TypeError("Replication count must be a non-negative integer, not {!r}"
                            .format(count))
        return Cat(self for _ in range(count))

    def eq(self, value):
        """Assignment.

        Parameters
        ----------
        value : Value, in
            Value to be assigned.

        Returns
        -------
        Assign
            Assignment statement that can be used in combinatorial or synchronous context.
        """
        return Assign(self, value, src_loc_at=1)

    @abstractmethod
    def shape(self):
        """Bit width and signedness of a value.

        Returns
        -------
        Shape
            See :class:`Shape`.

        Examples
        --------
        >>> Signal(8).shape()
        Shape(width=8, signed=False)
        >>> Const(0xaa).shape()
        Shape(width=8, signed=False)
        """
        pass # :nocov:

    def _lhs_signals(self):
        raise TypeError(f"Value {self!r} cannot be used in assignments")

    @abstractmethod
    def _rhs_signals(self):
        raise NotImplementedError # :nocov:


@final
class Const(Value):
    """A constant, literal integer value.

    Parameters
    ----------
    value : int
    shape : int or tuple or None
        Either an integer ``width`` or a tuple ``(width, signed)`` specifying the number of bits
        in this constant and whether it is signed (can represent negative values).
        ``shape`` defaults to the minimum possible width and signedness of ``value``.

    Attributes
    ----------
    width : int
    signed : bool
    """
    src_loc = None

    # TODO(amaranth-0.5): remove
    @staticmethod
    @deprecated("instead of `Const.normalize(value, shape)`, use `Const(value, shape).value`")
    def normalize(value, shape):
        mask = (1 << shape.width) - 1
        value &= mask
        if shape.signed and value >> (shape.width - 1):
            value |= ~mask
        return value

    @staticmethod
    def cast(obj):
        """Converts ``obj`` to an Amaranth constant.

        First, ``obj`` is converted to a value using :meth:`Value.cast`. If it is a constant, it
        is returned. If it is a constant-castable expression, it is evaluated and returned.
        Otherwise, :exn:`TypeError` is raised.
        """
        obj = Value.cast(obj)
        if type(obj) is Const:
            return obj
        elif type(obj) is Cat:
            value = 0
            width = 0
            for part in obj.parts:
                const  = Const.cast(part)
                value |= const.value << width
                width += len(const)
            return Const(value, width)
        else:
            raise TypeError(f"Value {obj!r} cannot be converted to an Amaranth constant")

    def __init__(self, value, shape=None, *, src_loc_at=0):
        # We deliberately do not call Value.__init__ here.
        self.value = int(value)
        if shape is None:
            shape = Shape(bits_for(self.value), signed=self.value < 0)
        elif isinstance(shape, int):
            shape = Shape(shape, signed=self.value < 0)
        else:
            if isinstance(shape, range) and self.value == shape.stop:
                warnings.warn(
                    message="Value {!r} equals the non-inclusive end of the constant "
                            "shape {!r}; this is likely an off-by-one error"
                            .format(self.value, shape),
                    category=SyntaxWarning,
                    stacklevel=2)
            shape = Shape.cast(shape, src_loc_at=1 + src_loc_at)
        self.width  = shape.width
        self.signed = shape.signed
        if self.signed and self.value >> (self.width - 1) & 1:
            self.value |= -(1 << self.width)
        else:
            self.value &= (1 << self.width) - 1

    def shape(self):
        return Shape(self.width, self.signed)

    def _rhs_signals(self):
        return SignalSet()

    def __repr__(self):
        return "(const {}'{}d{})".format(self.width, "s" if self.signed else "", self.value)


C = Const  # shorthand


class AnyValue(Value, DUID):
    def __init__(self, shape, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        shape = Shape.cast(shape, src_loc_at=1 + src_loc_at)
        self.width  = shape.width
        self.signed = shape.signed

    def shape(self):
        return Shape(self.width, self.signed)

    def _rhs_signals(self):
        return SignalSet()


@final
class AnyConst(AnyValue):
    def __repr__(self):
        return "(anyconst {}'{})".format(self.width, "s" if self.signed else "")


@final
class AnySeq(AnyValue):
    def __repr__(self):
        return "(anyseq {}'{})".format(self.width, "s" if self.signed else "")


@final
class Operator(Value):
    def __init__(self, operator, operands, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)
        self.operator = operator
        self.operands = [Value.cast(op) for op in operands]

    def shape(self):
        def _bitwise_binary_shape(a_shape, b_shape):
            if not a_shape.signed and not b_shape.signed:
                # both operands unsigned
                return unsigned(max(a_shape.width, b_shape.width))
            elif a_shape.signed and b_shape.signed:
                # both operands signed
                return signed(max(a_shape.width, b_shape.width))
            elif not a_shape.signed and b_shape.signed:
                # first operand unsigned (add sign bit), second operand signed
                return signed(max(a_shape.width + 1, b_shape.width))
            else:
                # first signed, second operand unsigned (add sign bit)
                return signed(max(a_shape.width, b_shape.width + 1))

        op_shapes = list(map(lambda x: x.shape(), self.operands))
        if len(op_shapes) == 1:
            a_shape, = op_shapes
            if self.operator in ("+", "~"):
                return Shape(a_shape.width, a_shape.signed)
            if self.operator == "-":
                return Shape(a_shape.width + 1, True)
            if self.operator in ("b", "r|", "r&", "r^"):
                return Shape(1, False)
            if self.operator == "u":
                return Shape(a_shape.width, False)
            if self.operator == "s":
                return Shape(a_shape.width, True)
        elif len(op_shapes) == 2:
            a_shape, b_shape = op_shapes
            if self.operator == "+":
                o_shape = _bitwise_binary_shape(*op_shapes)
                return Shape(o_shape.width + 1, o_shape.signed)
            if self.operator == "-":
                o_shape = _bitwise_binary_shape(*op_shapes)
                return Shape(o_shape.width + 1, True)
            if self.operator == "*":
                return Shape(a_shape.width + b_shape.width, a_shape.signed or b_shape.signed)
            if self.operator == "//":
                return Shape(a_shape.width + b_shape.signed, a_shape.signed or b_shape.signed)
            if self.operator == "%":
                return Shape(b_shape.width, b_shape.signed)
            if self.operator in ("<", "<=", "==", "!=", ">", ">="):
                return Shape(1, False)
            if self.operator in ("&", "^", "|"):
                return _bitwise_binary_shape(*op_shapes)
            if self.operator == "<<":
                assert not b_shape.signed
                return Shape(a_shape.width + 2 ** b_shape.width - 1, a_shape.signed)
            if self.operator == ">>":
                assert not b_shape.signed
                return Shape(a_shape.width, a_shape.signed)
        elif len(op_shapes) == 3:
            if self.operator == "m":
                s_shape, a_shape, b_shape = op_shapes
                return _bitwise_binary_shape(a_shape, b_shape)
        raise NotImplementedError("Operator {}/{} not implemented"
                                  .format(self.operator, len(op_shapes))) # :nocov:

    def _lhs_signals(self):
        if self.operator in ("u", "s"):
            return union(op._lhs_signals() for op in self.operands)
        return super()._lhs_signals()

    def _rhs_signals(self):
        return union(op._rhs_signals() for op in self.operands)

    def __repr__(self):
        return "({} {})".format(self.operator, " ".join(map(repr, self.operands)))


def Mux(sel, val1, val0):
    """Choose between two values.

    Parameters
    ----------
    sel : Value, in
        Selector.
    val1 : Value, in
    val0 : Value, in
        Input values.

    Returns
    -------
    Value, out
        Output ``Value``. If ``sel`` is asserted, the Mux returns ``val1``, else ``val0``.
    """
    return Operator("m", [sel, val1, val0])


@final
class Slice(Value):
    def __init__(self, value, start, stop, *, src_loc_at=0):
        if not isinstance(start, int):
            raise TypeError(f"Slice start must be an integer, not {start!r}")
        if not isinstance(stop, int):
            raise TypeError(f"Slice stop must be an integer, not {stop!r}")

        value = Value.cast(value)
        n = len(value)
        if start not in range(-n, n+1):
            raise IndexError(f"Cannot start slice {start} bits into {n}-bit value")
        if start < 0:
            start += n
        if stop not in range(-n, n+1):
            raise IndexError(f"Cannot stop slice {stop} bits into {n}-bit value")
        if stop < 0:
            stop += n
        if start > stop:
            raise IndexError(f"Slice start {start} must be less than slice stop {stop}")

        super().__init__(src_loc_at=src_loc_at)
        self.value = value
        self.start = int(start)
        self.stop  = int(stop)

    def shape(self):
        return Shape(self.stop - self.start)

    def _lhs_signals(self):
        return self.value._lhs_signals()

    def _rhs_signals(self):
        return self.value._rhs_signals()

    def __repr__(self):
        return f"(slice {self.value!r} {self.start}:{self.stop})"


@final
class Part(Value):
    def __init__(self, value, offset, width, stride=1, *, src_loc_at=0):
        if not isinstance(width, int) or width < 0:
            raise TypeError(f"Part width must be a non-negative integer, not {width!r}")
        if not isinstance(stride, int) or stride <= 0:
            raise TypeError(f"Part stride must be a positive integer, not {stride!r}")

        value = Value.cast(value)
        offset = Value.cast(offset)
        if offset.shape().signed:
            raise TypeError("Part offset must be unsigned")

        super().__init__(src_loc_at=src_loc_at)
        self.value  = value
        self.offset = offset
        self.width  = width
        self.stride = stride

    def shape(self):
        return Shape(self.width)

    def _lhs_signals(self):
        return self.value._lhs_signals()

    def _rhs_signals(self):
        return self.value._rhs_signals() | self.offset._rhs_signals()

    def __repr__(self):
        return "(part {} {} {} {})".format(repr(self.value), repr(self.offset),
                                           self.width, self.stride)


@final
class Cat(Value):
    """Concatenate values.

    Form a compound ``Value`` from several smaller ones by concatenation.
    The first argument occupies the lower bits of the result.
    The return value can be used on either side of an assignment, that
    is, the concatenated value can be used as an argument on the RHS or
    as a target on the LHS. If it is used on the LHS, it must solely
    consist of ``Signal`` s, slices of ``Signal`` s, and other concatenations
    meeting these properties. The bit length of the return value is the sum of
    the bit lengths of the arguments::

        len(Cat(args)) == sum(len(arg) for arg in args)

    Parameters
    ----------
    *args : Values or iterables of Values, inout
        ``Value`` s to be concatenated.

    Returns
    -------
    Value, inout
        Resulting ``Value`` obtained by concatenation.
    """
    def __init__(self, *args, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.parts = []
        for index, arg in enumerate(flatten(args)):
            if isinstance(arg, Enum) and (not isinstance(type(arg), ShapeCastable) or
                                          not hasattr(arg, "_amaranth_shape_")):
                warnings.warn("Argument #{} of Cat() is an enumerated value {!r} without "
                              "a defined shape used in bit vector context; define the enumeration "
                              "by inheriting from the class in amaranth.lib.enum and specifying "
                              "the 'shape=' keyword argument"
                              .format(index + 1, arg),
                              SyntaxWarning, stacklevel=2 + src_loc_at)
            if isinstance(arg, int) and not isinstance(arg, Enum) and arg not in [0, 1]:
                warnings.warn("Argument #{} of Cat() is a bare integer {} used in bit vector "
                              "context; specify the width explicitly using C({}, {})"
                              .format(index + 1, arg, arg, bits_for(arg)),
                              SyntaxWarning, stacklevel=2 + src_loc_at)
            self.parts.append(Value.cast(arg))

    def shape(self):
        return Shape(sum(len(part) for part in self.parts))

    def _lhs_signals(self):
        return union((part._lhs_signals() for part in self.parts), start=SignalSet())

    def _rhs_signals(self):
        return union((part._rhs_signals() for part in self.parts), start=SignalSet())

    def __repr__(self):
        return "(cat {})".format(" ".join(map(repr, self.parts)))


# TODO(amaranth-0.5): remove
@deprecated("instead of `Repl(value, count)`, use `value.replicate(count)`")
def Repl(value, count):
    """Replicate a value

    An input value is replicated (repeated) several times
    to be used on the RHS of assignments::

        len(Repl(s, n)) == len(s) * n

    Parameters
    ----------
    value : Value, in
        Input value to be replicated.
    count : int
        Number of replications.

    Returns
    -------
    Value, out
        Replicated value.
    """
    if isinstance(value, int) and value not in [0, 1]:
        warnings.warn("Value argument of Repl() is a bare integer {} used in bit vector "
                        "context; consider specifying explicit width using C({}, {}) instead"
                        .format(value, value, bits_for(value)),
                        SyntaxWarning, stacklevel=3)

    return Value.cast(value).replicate(count)


class _SignalMeta(ABCMeta):
    def __call__(cls, shape=None, src_loc_at=0, **kwargs):
        signal = super().__call__(shape, **kwargs, src_loc_at=src_loc_at + 1)
        if isinstance(shape, ShapeCastable):
            return shape(signal)
        return signal


# @final
class Signal(Value, DUID, metaclass=_SignalMeta):
    """A varying integer value.

    Parameters
    ----------
    shape : ``Shape``-castable object or None
        Specification for the number of bits in this ``Signal`` and its signedness (whether it
        can represent negative values). See ``Shape.cast`` for details.
        If not specified, ``shape`` defaults to 1-bit and non-signed.
    name : str
        Name hint for this signal. If ``None`` (default) the name is inferred from the variable
        name this ``Signal`` is assigned to.
    reset : int or integral Enum
        Reset (synchronous) or default (combinatorial) value.
        When this ``Signal`` is assigned to in synchronous context and the corresponding clock
        domain is reset, the ``Signal`` assumes the given value. When this ``Signal`` is unassigned
        in combinatorial context (due to conditional assignments not being taken), the ``Signal``
        assumes its ``reset`` value. Defaults to 0.
    reset_less : bool
        If ``True``, do not generate reset logic for this ``Signal`` in synchronous statements.
        The ``reset`` value is only used as a combinatorial default or as the initial value.
        Defaults to ``False``.
    attrs : dict
        Dictionary of synthesis attributes.
    decoder : function or Enum
        A function converting integer signal values to human-readable strings (e.g. FSM state
        names). If an ``Enum`` subclass is passed, it is concisely decoded using format string
        ``"{0.name:}/{0.value:}"``, or a number if the signal value is not a member of
        the enumeration.

    Attributes
    ----------
    width : int
    signed : bool
    name : str
    reset : int
    reset_less : bool
    attrs : dict
    decoder : function
    """

    def __init__(self, shape=None, *, name=None, reset=None, reset_less=False,
                 attrs=None, decoder=None, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)

        if name is not None and not isinstance(name, str):
            raise TypeError(f"Name must be a string, not {name!r}")
        self.name = name or tracer.get_var_name(depth=2 + src_loc_at, default="$signal")

        orig_shape = shape
        if shape is None:
            shape = unsigned(1)
        else:
            shape = Shape.cast(shape, src_loc_at=1 + src_loc_at)
        self.width  = shape.width
        self.signed = shape.signed

        orig_reset = reset
        if isinstance(orig_shape, ShapeCastable):
            try:
                reset = Const.cast(orig_shape.const(reset))
            except Exception:
                raise TypeError("Reset value must be a constant initializer of {!r}"
                                .format(orig_shape))
            if reset.shape() != Shape.cast(orig_shape):
                raise ValueError("Constant returned by {!r}.const() must have the shape that "
                                 "it casts to, {!r}, and not {!r}"
                                 .format(orig_shape, Shape.cast(orig_shape),
                                         reset.shape()))
        else:
            if reset is None:
                reset = 0
            try:
                reset = Const.cast(reset)
            except TypeError:
                raise TypeError("Reset value must be a constant-castable expression, not {!r}"
                                .format(orig_reset))
        # Avoid false positives for all-zeroes and all-ones
        if orig_reset is not None and not (isinstance(orig_reset, int) and orig_reset in (0, -1)):
            if reset.shape().signed and not self.signed:
                warnings.warn(
                    message="Reset value {!r} is signed, but the signal shape is {!r}"
                            .format(orig_reset, shape),
                    category=SyntaxWarning,
                    stacklevel=2)
            elif (reset.shape().width > self.width or
                  reset.shape().width == self.width and
                    self.signed and not reset.shape().signed):
                warnings.warn(
                    message="Reset value {!r} will be truncated to the signal shape {!r}"
                            .format(orig_reset, shape),
                    category=SyntaxWarning,
                    stacklevel=2)
        self.reset = reset.value
        self.reset_less = bool(reset_less)

        if isinstance(orig_shape, range) and self.reset == orig_shape.stop:
            warnings.warn(
                message="Reset value {!r} equals the non-inclusive end of the signal "
                        "shape {!r}; this is likely an off-by-one error"
                        .format(self.reset, orig_shape),
                category=SyntaxWarning,
                stacklevel=2)

        self.attrs = OrderedDict(() if attrs is None else attrs)

        if decoder is not None:
            # The value representation is specified explicitly. Since we do not expose `hdl._repr`,
            # this is the only way to add a custom filter to the signal right now. The setter sets
            # `self._value_repr` as well as the compatibility `self.decoder`.
            self.decoder = decoder
        else:
            # If it's an enum, expose it via `self.decoder` for compatibility, whether it's a Python
            # enum or an Amaranth enum. This also sets the value representation, even for custom
            # shape-castables that implement their own `_value_repr`.
            if isinstance(orig_shape, type) and issubclass(orig_shape, Enum):
                self.decoder = orig_shape
            else:
                self.decoder = None
            # The value representation is specified implicitly in the shape of the signal.
            if isinstance(orig_shape, ShapeCastable):
                # A custom shape-castable always has a `_value_repr`, at least the default one.
                self._value_repr = tuple(orig_shape._value_repr(self))
            elif isinstance(orig_shape, type) and issubclass(orig_shape, Enum):
                # A non-Amaranth enum needs a value repr constructed for it.
                self._value_repr = (Repr(FormatEnum(orig_shape), self),)
            else:
                # Any other case is formatted as a plain integer.
                self._value_repr = (Repr(FormatInt(), self),)

    @property
    def decoder(self):
        return self._decoder

    @decoder.setter
    def decoder(self, decoder):
        # Compute the value representation that will be used by Amaranth.
        if decoder is None:
            self._value_repr = (Repr(FormatInt(), self),)
            self._decoder = None
        elif not (isinstance(decoder, type) and issubclass(decoder, Enum)):
            self._value_repr = (Repr(FormatCustom(decoder), self),)
            self._decoder = decoder
        else: # Violence. In the name of backwards compatibility!
            self._value_repr = (Repr(FormatEnum(decoder), self),)
            def enum_decoder(value):
                try:
                    return "{0.name:}/{0.value:}".format(decoder(value))
                except ValueError:
                    return str(value)
            self._decoder = enum_decoder

    # Not a @classmethod because amaranth.compat requires it.
    @staticmethod
    def like(other, *, name=None, name_suffix=None, src_loc_at=0, **kwargs):
        """Create Signal based on another.

        Parameters
        ----------
        other : Value
            Object to base this Signal on.
        """
        if name is not None:
            new_name = str(name)
        elif name_suffix is not None:
            new_name = other.name + str(name_suffix)
        else:
            new_name = tracer.get_var_name(depth=2 + src_loc_at, default="$like")
        if isinstance(other, ValueCastable):
            shape = other.shape()
        else:
            shape = Value.cast(other).shape()
        kw = dict(shape=shape, name=new_name)
        if isinstance(other, Signal):
            kw.update(reset=other.reset, reset_less=other.reset_less,
                      attrs=other.attrs, decoder=other.decoder)
        kw.update(kwargs)
        return Signal(**kw, src_loc_at=1 + src_loc_at)

    def shape(self):
        return Shape(self.width, self.signed)

    def _lhs_signals(self):
        return SignalSet((self,))

    def _rhs_signals(self):
        return SignalSet((self,))

    def __repr__(self):
        return f"(sig {self.name})"


@final
class ClockSignal(Value):
    """Clock signal for a clock domain.

    Any ``ClockSignal`` is equivalent to ``cd.clk`` for a clock domain with the corresponding name.
    All of these signals ultimately refer to the same signal, but they can be manipulated
    independently of the clock domain, even before the clock domain is created.

    Parameters
    ----------
    domain : str
        Clock domain to obtain a clock signal for. Defaults to ``"sync"``.
    """
    def __init__(self, domain="sync", *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        if not isinstance(domain, str):
            raise TypeError(f"Clock domain name must be a string, not {domain!r}")
        if domain == "comb":
            raise ValueError(f"Domain '{domain}' does not have a clock")
        self.domain = domain

    def shape(self):
        return Shape(1)

    def _lhs_signals(self):
        return SignalSet((self,))

    def _rhs_signals(self):
        raise NotImplementedError("ClockSignal must be lowered to a concrete signal") # :nocov:

    def __repr__(self):
        return f"(clk {self.domain})"


@final
class ResetSignal(Value):
    """Reset signal for a clock domain.

    Any ``ResetSignal`` is equivalent to ``cd.rst`` for a clock domain with the corresponding name.
    All of these signals ultimately refer to the same signal, but they can be manipulated
    independently of the clock domain, even before the clock domain is created.

    Parameters
    ----------
    domain : str
        Clock domain to obtain a reset signal for. Defaults to ``"sync"``.
    allow_reset_less : bool
        If the clock domain is reset-less, act as a constant ``0`` instead of reporting an error.
    """
    def __init__(self, domain="sync", allow_reset_less=False, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        if not isinstance(domain, str):
            raise TypeError(f"Clock domain name must be a string, not {domain!r}")
        if domain == "comb":
            raise ValueError(f"Domain '{domain}' does not have a reset")
        self.domain = domain
        self.allow_reset_less = allow_reset_less

    def shape(self):
        return Shape(1)

    def _lhs_signals(self):
        return SignalSet((self,))

    def _rhs_signals(self):
        raise NotImplementedError("ResetSignal must be lowered to a concrete signal") # :nocov:

    def __repr__(self):
        return f"(rst {self.domain})"


class Array(MutableSequence):
    """Addressable multiplexer.

    An array is similar to a ``list`` that can also be indexed by ``Value``s; indexing by an integer or a slice works the same as for Python lists, but indexing by a ``Value`` results
    in a proxy.

    The array proxy can be used as an ordinary ``Value``, i.e. participate in calculations and
    assignments, provided that all elements of the array are values. The array proxy also supports
    attribute access and further indexing, each returning another array proxy; this means that
    the results of indexing into arrays, arrays of records, and arrays of arrays can all
    be used as first-class values.

    It is an error to change an array or any of its elements after an array proxy was created.
    Changing the array directly will raise an exception. However, it is not possible to detect
    the elements being modified; if an element's attribute or element is modified after the proxy
    for it has been created, the proxy will refer to stale data.

    Examples
    --------

    Simple array::

        gpios = Array(Signal() for _ in range(10))
        with m.If(bus.we):
            m.d.sync += gpios[bus.addr].eq(bus.w_data)
        with m.Else():
            m.d.sync += bus.r_data.eq(gpios[bus.addr])

    Multidimensional array::

        mult = Array(Array(x * y for y in range(10)) for x in range(10))
        a = Signal.range(10)
        b = Signal.range(10)
        r = Signal(8)
        m.d.comb += r.eq(mult[a][b])

    Array of records::

        layout = [
            ("r_data", 16),
            ("r_en",   1),
        ]
        buses  = Array(Record(layout) for busno in range(4))
        master = Record(layout)
        m.d.comb += [
            buses[sel].r_en.eq(master.r_en),
            master.r_data.eq(buses[sel].r_data),
        ]
    """
    def __init__(self, iterable=()):
        self._inner    = list(iterable)
        self._proxy_at = None
        self._mutable  = True

    def __getitem__(self, index):
        if isinstance(index, Value):
            if self._mutable:
                self._proxy_at = tracer.get_src_loc()
                self._mutable  = False
            return ArrayProxy(self, index)
        else:
            return self._inner[index]

    def __len__(self):
        return len(self._inner)

    def _check_mutability(self):
        if not self._mutable:
            raise ValueError("Array can no longer be mutated after it was indexed with a value "
                             "at {}:{}".format(*self._proxy_at))

    def __setitem__(self, index, value):
        self._check_mutability()
        self._inner[index] = value

    def __delitem__(self, index):
        self._check_mutability()
        del self._inner[index]

    def insert(self, index, value):
        self._check_mutability()
        self._inner.insert(index, value)

    def __repr__(self):
        return "(array{} [{}])".format(" mutable" if self._mutable else "",
                                       ", ".join(map(repr, self._inner)))


@final
class ArrayProxy(Value):
    def __init__(self, elems, index, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)
        self.elems = elems
        self.index = Value.cast(index)

    def __getattr__(self, attr):
        return ArrayProxy([getattr(elem, attr) for elem in self.elems], self.index)

    def __getitem__(self, index):
        return ArrayProxy([        elem[index] for elem in self.elems], self.index)

    def _iter_as_values(self):
        return (Value.cast(elem) for elem in self.elems)

    def shape(self):
        unsigned_width = signed_width = 0
        has_unsigned = has_signed = False
        for elem_shape in (elem.shape() for elem in self._iter_as_values()):
            if elem_shape.signed:
                has_signed = True
                signed_width = max(signed_width, elem_shape.width)
            else:
                has_unsigned = True
                unsigned_width = max(unsigned_width, elem_shape.width)
        # The shape of the proxy must be such that it preserves the mathematical value of the array
        # elements. I.e., shape-wise, an array proxy must be identical to an equivalent mux tree.
        # To ensure this holds, if the array contains both signed and unsigned values, make sure
        # that every unsigned value is zero-extended by at least one bit.
        if has_signed and has_unsigned and unsigned_width >= signed_width:
            # Array contains both signed and unsigned values, and at least one of the unsigned
            # values won't be zero-extended otherwise.
            return signed(unsigned_width + 1)
        else:
            # Array contains values of the same signedness, or else all of the unsigned values
            # are zero-extended.
            return Shape(max(unsigned_width, signed_width), has_signed)

    def _lhs_signals(self):
        signals = union((elem._lhs_signals() for elem in self._iter_as_values()),
                        start=SignalSet())
        return signals

    def _rhs_signals(self):
        signals = union((elem._rhs_signals() for elem in self._iter_as_values()),
                        start=SignalSet())
        return self.index._rhs_signals() | signals

    def __repr__(self):
        return "(proxy (array [{}]) {!r})".format(", ".join(map(repr, self.elems)), self.index)


class ValueCastable:
    """Interface of user-defined objects that can be cast to :class:`Value` s.

    An object deriving from :class:`ValueCastable`` is automatically converted to a :class:`Value`
    when it is used in a context where a :class:`Value`` is expected. Such objects can implement
    different or richer semantics than what is supported by the core Amaranth language, yet still
    be transparently used with it as long as the final underlying representation is a single
    Amaranth :class:`Value`. These objects also need not commit to a specific representation until
    they are converted to a concrete Amaranth value.

    Note that it is necessary to ensure that Amaranth's view of representation of all values stays
    internally consistent. The class deriving from :class:`ValueCastable`` must decorate
    the :meth:`as_value` method with the :meth:`lowermethod` decorator, which ensures that all
    calls to :meth:`as_value` return the same :class:`Value` representation. If the class deriving
    from :class:`ValueCastable` is mutable, it is up to the user to ensure that it is not mutated
    in a way that changes its representation after the first call to :meth:`as_value`.
    """
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, "as_value"):
            raise TypeError(f"Class '{cls.__name__}' deriving from `ValueCastable` must override "
                            "the `as_value` method")
        if not hasattr(cls, "shape"):
            raise TypeError(f"Class '{cls.__name__}' deriving from `ValueCastable` must override "
                            "the `shape` method")
        if not hasattr(cls.as_value, "_ValueCastable__memoized"):
            raise TypeError(f"Class '{cls.__name__}' deriving from `ValueCastable` must decorate "
                            "the `as_value` method with the `ValueCastable.lowermethod` decorator")

    @staticmethod
    def lowermethod(func):
        """Decorator to memoize lowering methods.

        Ensures the decorated method is called only once, with subsequent method calls returning
        the object returned by the first first method call.

        This decorator is required to decorate the ``as_value`` method of ``ValueCastable``
        subclasses. This is to ensure that Amaranth's view of representation of all values stays
        internally consistent.
        """
        @functools.wraps(func)
        def wrapper_memoized(self, *args, **kwargs):
            # Use `in self.__dict__` instead of `hasattr` to avoid interfering with custom
            # `__getattr__` implementations.
            if not "_ValueCastable__lowered_to" in self.__dict__:
                self.__lowered_to = func(self, *args, **kwargs)
            return self.__lowered_to
        wrapper_memoized.__memoized = True
        return wrapper_memoized


class _ValueLikeMeta(type):
    """An abstract class representing all objects that can be cast to a :class:`Value`.

    ``issubclass(cls, ValueLike)`` returns ``True`` for:

    - :class:`Value`
    - :class:`ValueCastable` and its subclasses
    - ``int`` and its subclasses
    - :class:`enum.Enum` subclasses where all values are :ref:`value-like <lang-valuelike>`
    - :class:`ValueLike` itself

    ``isinstance(obj, ValueLike)`` returns the same value as ``issubclass(type(obj), ValueLike)``.

    This class is only usable for the above checks — no instances and no (non-virtual)
    subclasses can be created.
    """

    def __subclasscheck__(cls, subclass):
        if issubclass(subclass, (Value, ValueCastable, int)) or subclass is ValueLike:
            return True
        if issubclass(subclass, Enum):
            return isinstance(subclass, ShapeLike)
        return False

    def __instancecheck__(cls, instance):
        return issubclass(type(instance), cls)


@final
class ValueLike(metaclass=_ValueLikeMeta):
    def __new__(cls, *args, **kwargs):
        raise TypeError("ValueLike is an abstract class and cannot be constructed")


# TODO(amaranth-0.5): remove
@final
class Sample(Value):
    """Value from the past.

    A ``Sample`` of an expression is equal to the value of the expression ``clocks`` clock edges
    of the ``domain`` clock back. If that moment is before the beginning of time, it is equal
    to the value of the expression calculated as if each signal had its reset value.
    """
    @deprecated("instead of using `Sample`, create a register explicitly")
    def __init__(self, expr, clocks, domain, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)
        self.value  = Value.cast(expr)
        self.clocks = int(clocks)
        self.domain = domain
        if not isinstance(self.value, (Const, Signal, ClockSignal, ResetSignal, Initial)):
            raise TypeError("Sampled value must be a signal or a constant, not {!r}"
                            .format(self.value))
        if self.clocks < 0:
            raise ValueError("Cannot sample a value {} cycles in the future"
                             .format(-self.clocks))
        if not (self.domain is None or isinstance(self.domain, str)):
            raise TypeError("Domain name must be a string or None, not {!r}"
                            .format(self.domain))

    def shape(self):
        return self.value.shape()

    def _rhs_signals(self):
        return SignalSet((self,))

    def __repr__(self):
        return "(sample {!r} @ {}[{}])".format(
            self.value, "<default>" if self.domain is None else self.domain, self.clocks)


# TODO(amaranth-0.5): remove
@deprecated("instead of using `Past`, create a register explicitly")
def Past(expr, clocks=1, domain=None):
    with _ignore_deprecated():
        return Sample(expr, clocks, domain)


# TODO(amaranth-0.5): remove
@deprecated("instead of using `Stable`, create registers and comparisons explicitly")
def Stable(expr, clocks=0, domain=None):
    with _ignore_deprecated():
        return Sample(expr, clocks + 1, domain) == Sample(expr, clocks, domain)


# TODO(amaranth-0.5): remove
@deprecated("instead of using `Rose`, create registers and comparisons explicitly")
def Rose(expr, clocks=0, domain=None):
    with _ignore_deprecated():
        return ~Sample(expr, clocks + 1, domain) & Sample(expr, clocks, domain)


# TODO(amaranth-0.5): remove
@deprecated("instead of using `Fell`, create registers and comparisons explicitly")
def Fell(expr, clocks=0, domain=None):
    with _ignore_deprecated():
        return Sample(expr, clocks + 1, domain) & ~Sample(expr, clocks, domain)


@final
class Initial(Value):
    """Start indicator, for model checking.

    An ``Initial`` signal is ``1`` at the first cycle of model checking, and ``0`` at any other.
    """
    def __init__(self, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)

    def shape(self):
        return Shape(1)

    def _rhs_signals(self):
        return SignalSet((self,))

    def __repr__(self):
        return "(initial)"


class _StatementList(list):
    def __repr__(self):
        return "({})".format(" ".join(map(repr, self)))


class Statement:
    def __init__(self, *, src_loc_at=0):
        self.src_loc = tracer.get_src_loc(1 + src_loc_at)

    @staticmethod
    def cast(obj):
        if isinstance(obj, Iterable):
            return _StatementList(list(chain.from_iterable(map(Statement.cast, obj))))
        else:
            if isinstance(obj, Statement):
                return _StatementList([obj])
            else:
                raise TypeError(f"Object {obj!r} is not an Amaranth statement")


@final
class Assign(Statement):
    def __init__(self, lhs, rhs, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.lhs = Value.cast(lhs)
        self.rhs = Value.cast(rhs)

    def _lhs_signals(self):
        return self.lhs._lhs_signals()

    def _rhs_signals(self):
        return self.lhs._rhs_signals() | self.rhs._rhs_signals()

    def __repr__(self):
        return f"(eq {self.lhs!r} {self.rhs!r})"


class UnusedProperty(UnusedMustUse):
    pass


class Property(Statement, MustUse):
    _MustUse__warning = UnusedProperty

    def __init__(self, test, *, _check=None, _en=None, name=None, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.test   = Value.cast(test)
        self._check = _check
        self._en    = _en
        self.name   = name
        if not isinstance(self.name, str) and self.name is not None:
            raise TypeError("Property name must be a string or None, not {!r}"
                            .format(self.name))
        if self._check is None:
            self._check = Signal(reset_less=True, name=f"${self._kind}$check")
            self._check.src_loc = self.src_loc
        if _en is None:
            self._en = Signal(reset_less=True, name=f"${self._kind}$en")
            self._en.src_loc = self.src_loc

    def _lhs_signals(self):
        return SignalSet((self._en, self._check))

    def _rhs_signals(self):
        return self.test._rhs_signals()

    def __repr__(self):
        if self.name is not None:
            return f"({self.name}: {self._kind} {self.test!r})"
        return f"({self._kind} {self.test!r})"


@final
class Assert(Property):
    _kind = "assert"


@final
class Assume(Property):
    _kind = "assume"


@final
class Cover(Property):
    _kind = "cover"


# @final
class Switch(Statement):
    def __init__(self, test, cases, *, src_loc=None, src_loc_at=0, case_src_locs={}):
        if src_loc is None:
            super().__init__(src_loc_at=src_loc_at)
        else:
            # Switch is a bit special in terms of location tracking because it is usually created
            # long after the control has left the statement that directly caused its creation.
            self.src_loc = src_loc
        # Switch is also a bit special in that its parts also have location information. It can't
        # be automatically traced, so whatever constructs a Switch may optionally provide it.
        self.case_src_locs = {}

        self.test  = Value.cast(test)
        self.cases = OrderedDict()
        for orig_keys, stmts in cases.items():
            # Map: None -> (); key -> (key,); (key...) -> (key...)
            keys = orig_keys
            if keys is None:
                keys = ()
            if not isinstance(keys, tuple):
                keys = (keys,)
            # Map: 2 -> "0010"; "0010" -> "0010"
            new_keys = ()
            key_mask = (1 << len(self.test)) - 1
            for key in keys:
                if isinstance(key, str):
                    key = "".join(key.split()) # remove whitespace
                elif isinstance(key, int):
                    key = format(key & key_mask, "b").rjust(len(self.test), "0")
                elif isinstance(key, Enum):
                    key = format(key.value & key_mask, "b").rjust(len(self.test), "0")
                else:
                    raise TypeError("Object {!r} cannot be used as a switch key"
                                    .format(key))
                assert len(key) == len(self.test)
                new_keys = (*new_keys, key)
            if not isinstance(stmts, Iterable):
                stmts = [stmts]
            self.cases[new_keys] = Statement.cast(stmts)
            if orig_keys in case_src_locs:
                self.case_src_locs[new_keys] = case_src_locs[orig_keys]

    def _lhs_signals(self):
        signals = union((s._lhs_signals() for ss in self.cases.values() for s in ss),
                        start=SignalSet())
        return signals

    def _rhs_signals(self):
        signals = union((s._rhs_signals() for ss in self.cases.values() for s in ss),
                        start=SignalSet())
        return self.test._rhs_signals() | signals

    def __repr__(self):
        def case_repr(keys, stmts):
            stmts_repr = " ".join(map(repr, stmts))
            if keys == ():
                return f"(default {stmts_repr})"
            elif len(keys) == 1:
                return f"(case {keys[0]} {stmts_repr})"
            else:
                return "(case ({}) {})".format(" ".join(keys), stmts_repr)
        case_reprs = [case_repr(keys, stmts) for keys, stmts in self.cases.items()]
        return "(switch {!r} {})".format(self.test, " ".join(case_reprs))


class _MappedKeyCollection(metaclass=ABCMeta):
    @abstractmethod
    def _map_key(self, key):
        pass # :nocov:

    @abstractmethod
    def _unmap_key(self, key):
        pass # :nocov:


class _MappedKeyDict(MutableMapping, _MappedKeyCollection):
    def __init__(self, pairs=()):
        self._storage = OrderedDict()
        for key, value in pairs:
            self[key] = value

    def __getitem__(self, key):
        key = None if key is None else self._map_key(key)
        return self._storage[key]

    def __setitem__(self, key, value):
        key = None if key is None else self._map_key(key)
        self._storage[key] = value

    def __delitem__(self, key):
        key = None if key is None else self._map_key(key)
        del self._storage[key]

    def __iter__(self):
        for key in self._storage:
            if key is None:
                yield None
            else:
                yield self._unmap_key(key)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        if len(self) != len(other):
            return False
        for ak, bk in zip(sorted(self._storage), sorted(other._storage)):
            if ak != bk:
                return False
            if self._storage[ak] != other._storage[bk]:
                return False
        return True

    def __len__(self):
        return len(self._storage)

    def __repr__(self):
        pairs = [f"({k!r}, {v!r})" for k, v in self.items()]
        return "{}.{}([{}])".format(type(self).__module__, type(self).__name__,
                                    ", ".join(pairs))


class _MappedKeySet(MutableSet, _MappedKeyCollection):
    def __init__(self, elements=()):
        self._storage = OrderedDict()
        for elem in elements:
            self.add(elem)

    def add(self, value):
        self._storage[self._map_key(value)] = None

    def update(self, values):
        for value in values:
            self.add(value)

    def discard(self, value):
        if value in self:
            del self._storage[self._map_key(value)]

    def __contains__(self, value):
        return self._map_key(value) in self._storage

    def __iter__(self):
        for key in [k for k in self._storage]:
            yield self._unmap_key(key)

    def __len__(self):
        return len(self._storage)

    def __repr__(self):
        return "{}.{}({})".format(type(self).__module__, type(self).__name__,
                                  ", ".join(repr(x) for x in self))


class ValueKey:
    def __init__(self, value):
        self.value = Value.cast(value)
        if isinstance(self.value, Const):
            self._hash = hash(self.value.value)
        elif isinstance(self.value, (Signal, AnyValue)):
            self._hash = hash(self.value.duid)
        elif isinstance(self.value, (ClockSignal, ResetSignal)):
            self._hash = hash(self.value.domain)
        elif isinstance(self.value, Operator):
            self._hash = hash((self.value.operator,
                               tuple(ValueKey(o) for o in self.value.operands)))
        elif isinstance(self.value, Slice):
            self._hash = hash((ValueKey(self.value.value), self.value.start, self.value.stop))
        elif isinstance(self.value, Part):
            self._hash = hash((ValueKey(self.value.value), ValueKey(self.value.offset),
                              self.value.width, self.value.stride))
        elif isinstance(self.value, Cat):
            self._hash = hash(tuple(ValueKey(o) for o in self.value.parts))
        elif isinstance(self.value, ArrayProxy):
            self._hash = hash((ValueKey(self.value.index),
                              tuple(ValueKey(e) for e in self.value._iter_as_values())))
        elif isinstance(self.value, Sample):
            self._hash = hash((ValueKey(self.value.value), self.value.clocks, self.value.domain))
        elif isinstance(self.value, Initial):
            self._hash = 0
        else: # :nocov:
            raise TypeError("Object {!r} cannot be used as a key in value collections"
                            .format(self.value))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if type(other) is not ValueKey:
            return False
        if type(self.value) is not type(other.value):
            return False

        if isinstance(self.value, Const):
            return self.value.value == other.value.value and self.value.width == other.value.width
        elif isinstance(self.value, (Signal, AnyValue)):
            return self.value is other.value
        elif isinstance(self.value, (ClockSignal, ResetSignal)):
            return self.value.domain == other.value.domain
        elif isinstance(self.value, Operator):
            return (self.value.operator == other.value.operator and
                    len(self.value.operands) == len(other.value.operands) and
                    all(ValueKey(a) == ValueKey(b)
                        for a, b in zip(self.value.operands, other.value.operands)))
        elif isinstance(self.value, Slice):
            return (ValueKey(self.value.value) == ValueKey(other.value.value) and
                    self.value.start == other.value.start and
                    self.value.stop == other.value.stop)
        elif isinstance(self.value, Part):
            return (ValueKey(self.value.value) == ValueKey(other.value.value) and
                    ValueKey(self.value.offset) == ValueKey(other.value.offset) and
                    self.value.width == other.value.width and
                    self.value.stride == other.value.stride)
        elif isinstance(self.value, Cat):
            return (len(self.value.parts) == len(other.value.parts) and
                    all(ValueKey(a) == ValueKey(b)
                        for a, b in zip(self.value.parts, other.value.parts)))
        elif isinstance(self.value, ArrayProxy):
            return (ValueKey(self.value.index) == ValueKey(other.value.index) and
                    len(self.value.elems) == len(other.value.elems) and
                    all(ValueKey(a) == ValueKey(b)
                        for a, b in zip(self.value._iter_as_values(),
                                        other.value._iter_as_values())))
        elif isinstance(self.value, Sample):
            return (ValueKey(self.value.value) == ValueKey(other.value.value) and
                    self.value.clocks == other.value.clocks and
                    self.value.domain == self.value.domain)
        elif isinstance(self.value, Initial):
            return True
        else: # :nocov:
            raise TypeError("Object {!r} cannot be used as a key in value collections"
                            .format(self.value))

    def __lt__(self, other):
        if not isinstance(other, ValueKey):
            return False
        if type(self.value) != type(other.value):
            return False

        if isinstance(self.value, Const):
            return self.value < other.value
        elif isinstance(self.value, (Signal, AnyValue)):
            return self.value.duid < other.value.duid
        elif isinstance(self.value, Slice):
            return (ValueKey(self.value.value) < ValueKey(other.value.value) and
                    self.value.start < other.value.start and
                    self.value.end < other.value.end)
        else: # :nocov:
            raise TypeError("Object {!r} cannot be used as a key in value collections")

    def __repr__(self):
        return f"<{__name__}.ValueKey {self.value!r}>"


class ValueDict(_MappedKeyDict):
    _map_key   = ValueKey
    _unmap_key = lambda self, key: key.value


class ValueSet(_MappedKeySet):
    _map_key   = ValueKey
    _unmap_key = lambda self, key: key.value


class SignalKey:
    def __init__(self, signal):
        self.signal = signal
        if isinstance(signal, Signal):
            self._intern = (0, signal.duid)
        elif type(signal) is ClockSignal:
            self._intern = (1, signal.domain)
        elif type(signal) is ResetSignal:
            self._intern = (2, signal.domain)
        else:
            raise TypeError(f"Object {signal!r} is not an Amaranth signal")

    def __hash__(self):
        return hash(self._intern)

    def __eq__(self, other):
        if type(other) is not SignalKey:
            return False
        return self._intern == other._intern

    def __lt__(self, other):
        if type(other) is not SignalKey:
            raise TypeError(f"Object {other!r} cannot be compared to a SignalKey")
        return self._intern < other._intern

    def __repr__(self):
        return f"<{__name__}.SignalKey {self.signal!r}>"


class SignalDict(_MappedKeyDict):
    _map_key   = SignalKey
    _unmap_key = lambda self, key: key.signal


class SignalSet(_MappedKeySet):
    _map_key   = SignalKey
    _unmap_key = lambda self, key: key.signal


from ._repr import *
