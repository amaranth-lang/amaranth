from abc import ABCMeta, abstractmethod
import builtins
import traceback
import warnings
from collections import OrderedDict
from collections.abc import Iterable, MutableMapping, MutableSet, MutableSequence
from enum import Enum

from .. import tracer
from ..tools import *


__all__ = [
    "Value", "Const", "C", "AnyConst", "AnySeq", "Operator", "Mux", "Part", "Slice", "Cat", "Repl",
    "Array", "ArrayProxy",
    "Signal", "ClockSignal", "ResetSignal",
    "UserValue",
    "Sample", "Past", "Stable", "Rose", "Fell", "Initial",
    "Statement", "Assign", "Assert", "Assume", "Cover", "Switch", "Delay", "Tick",
    "Passive", "ValueKey", "ValueDict", "ValueSet", "SignalKey", "SignalDict",
    "SignalSet",
]


class DUID:
    """Deterministic Unique IDentifier"""
    __next_uid = 0
    def __init__(self):
        self.duid = DUID.__next_uid
        DUID.__next_uid += 1


def _enum_shape(enum_type):
    min_value = min(member.value for member in enum_type)
    max_value = max(member.value for member in enum_type)
    if not isinstance(min_value, int) or not isinstance(max_value, int):
        raise TypeError("Only enumerations with integer values can be converted to nMigen values")
    signed = min_value < 0 or max_value < 0
    width  = max(bits_for(min_value, signed), bits_for(max_value, signed))
    return (width, signed)


def _enum_to_bits(enum_value):
    width, signed = _enum_shape(type(enum_value))
    return format(enum_value.value & ((1 << width) - 1), "b").rjust(width, "0")


class Value(metaclass=ABCMeta):
    @staticmethod
    def wrap(obj):
        """Ensures that the passed object is an nMigen value. Booleans and integers
        are automatically wrapped into ``Const``."""
        if isinstance(obj, Value):
            return obj
        elif isinstance(obj, (bool, int)):
            return Const(obj)
        elif isinstance(obj, Enum):
            return Const(obj.value, _enum_shape(type(obj)))
        else:
            raise TypeError("Object '{!r}' is not an nMigen value".format(obj))

    def __init__(self, *, src_loc_at=0):
        super().__init__()
        self.src_loc = tracer.get_src_loc(1 + src_loc_at)

    def __bool__(self):
        raise TypeError("Attempted to convert nMigen value to boolean")

    def __invert__(self):
        return Operator("~", [self])
    def __neg__(self):
        return Operator("-", [self])

    def __add__(self, other):
        return Operator("+", [self, other])
    def __radd__(self, other):
        return Operator("+", [other, self])
    def __sub__(self, other):
        return Operator("-", [self, other])
    def __rsub__(self, other):
        return Operator("-", [other, self])
    def __mul__(self, other):
        return Operator("*", [self, other])
    def __rmul__(self, other):
        return Operator("*", [other, self])
    def __mod__(self, other):
        return Operator("%", [self, other])
    def __rmod__(self, other):
        return Operator("%", [other, self])
    def __floordiv__(self, other):
        return Operator("//", [self, other])
    def __rfloordiv__(self, other):
        return Operator("//", [other, self])
    def __lshift__(self, other):
        return Operator("<<", [self, other])
    def __rlshift__(self, other):
        return Operator("<<", [other, self])
    def __rshift__(self, other):
        return Operator(">>", [self, other])
    def __rrshift__(self, other):
        return Operator(">>", [other, self])
    def __and__(self, other):
        return Operator("&", [self, other])
    def __rand__(self, other):
        return Operator("&", [other, self])
    def __xor__(self, other):
        return Operator("^", [self, other])
    def __rxor__(self, other):
        return Operator("^", [other, self])
    def __or__(self, other):
        return Operator("|", [self, other])
    def __ror__(self, other):
        return Operator("|", [other, self])

    def __eq__(self, other):
        return Operator("==", [self, other])
    def __ne__(self, other):
        return Operator("!=", [self, other])
    def __lt__(self, other):
        return Operator("<", [self, other])
    def __le__(self, other):
        return Operator("<=", [self, other])
    def __gt__(self, other):
        return Operator(">", [self, other])
    def __ge__(self, other):
        return Operator(">=", [self, other])

    def __len__(self):
        return self.shape()[0]

    def __getitem__(self, key):
        n = len(self)
        if isinstance(key, int):
            if key not in range(-n, n):
                raise IndexError("Cannot index {} bits into {}-bit value".format(key, n))
            if key < 0:
                key += n
            return Slice(self, key, key + 1)
        elif isinstance(key, slice):
            start, stop, step = key.indices(n)
            if step != 1:
                return Cat(self[i] for i in range(start, stop, step))
            return Slice(self, start, stop)
        else:
            raise TypeError("Cannot index value with {}".format(repr(key)))

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

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @deprecated("instead of `.part`, use `.bit_select`")
    def part(self, offset, width):
        return Part(self, offset, width, src_loc_at=1)

    def bit_select(self, offset, width):
        """Part-select with bit granularity.

        Selects a constant width but variable offset part of a ``Value``, such that successive
        parts overlap by all but 1 bit.

        Parameters
        ----------
        offset : Value, in
            Index of first selected bit.
        width : int
            Number of selected bits.

        Returns
        -------
        Part, out
            Selected part of the ``Value``
        """
        return Part(self, offset, width, stride=1, src_loc_at=1)

    def word_select(self, offset, width):
        """Part-select with word granularity.

        Selects a constant width but variable offset part of a ``Value``, such that successive
        parts do not overlap.

        Parameters
        ----------
        offset : Value, in
            Index of first selected word.
        width : int
            Number of selected bits.

        Returns
        -------
        Part, out
            Selected part of the ``Value``
        """
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
        for pattern in patterns:
            if not isinstance(pattern, (int, str, Enum)):
                raise SyntaxError("Match pattern must be an integer, a string, or an enumeration, "
                                  "not {!r}"
                                  .format(pattern))
            if isinstance(pattern, str) and any(bit not in "01-" for bit in pattern):
                raise SyntaxError("Match pattern '{}' must consist of 0, 1, and - (don't care) "
                                  "bits"
                                  .format(pattern))
            if isinstance(pattern, str) and len(pattern) != len(self):
                raise SyntaxError("Match pattern '{}' must have the same width as match value "
                                  "(which is {})"
                                  .format(pattern, len(self)))
            if isinstance(pattern, int) and bits_for(pattern) > len(self):
                warnings.warn("Match pattern '{:b}' is wider than match value "
                              "(which has width {}); comparison will never be true"
                              .format(pattern, len(self)),
                              SyntaxWarning, stacklevel=3)
                continue
            if isinstance(pattern, int):
                matches.append(self == pattern)
            elif isinstance(pattern, (str, Enum)):
                if isinstance(pattern, Enum):
                    pattern = _enum_to_bits(pattern)
                mask    = int(pattern.replace("0", "1").replace("-", "0"), 2)
                pattern = int(pattern.replace("-", "0"), 2)
                matches.append((self & mask) == pattern)
            else:
                assert False
        if not matches:
            return Const(0)
        elif len(matches) == 1:
            return matches[0]
        else:
            return Cat(*matches).any()

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
        """Bit length and signedness of a value.

        Returns
        -------
        int, bool
            Number of bits required to store `v` or available in `v`, followed by
            whether `v` has a sign bit (included in the bit count).

        Examples
        --------
        >>> Value.shape(Signal(8))
        8, False
        >>> Value.shape(C(0xaa))
        8, False
        """
        pass # :nocov:

    def _lhs_signals(self):
        raise TypeError("Value {!r} cannot be used in assignments".format(self))

    @abstractmethod
    def _rhs_signals(self):
        pass # :nocov:

    def _as_const(self):
        raise TypeError("Value {!r} cannot be evaluated as constant".format(self))

    __hash__ = None


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

    @staticmethod
    def normalize(value, shape):
        width, signed = shape
        mask = (1 << width) - 1
        value &= mask
        if signed and value >> (width - 1):
            value |= ~mask
        return value

    def __init__(self, value, shape=None):
        # We deliberately do not call Value.__init__ here.
        self.value = int(value)
        if shape is None:
            shape = bits_for(self.value), self.value < 0
        if isinstance(shape, int):
            shape = shape, self.value < 0
        self.width, self.signed = shape
        if not isinstance(self.width, int) or self.width < 0:
            raise TypeError("Width must be a non-negative integer, not '{!r}'"
                            .format(self.width))
        self.value = self.normalize(self.value, shape)

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @property
    @deprecated("instead of `const.nbits`, use `const.width`")
    def nbits(self):
        return self.width

    def shape(self):
        return self.width, self.signed

    def _rhs_signals(self):
        return ValueSet()

    def _as_const(self):
        return self.value

    def __repr__(self):
        return "(const {}'{}d{})".format(self.width, "s" if self.signed else "", self.value)


C = Const  # shorthand


class AnyValue(Value, DUID):
    def __init__(self, shape, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        if isinstance(shape, int):
            shape = shape, False
        self.width, self.signed = shape
        if not isinstance(self.width, int) or self.width < 0:
            raise TypeError("Width must be a non-negative integer, not '{!r}'"
                            .format(self.width))

    def shape(self):
        return self.width, self.signed

    def _rhs_signals(self):
        return ValueSet()


@final
class AnyConst(AnyValue):
    def __repr__(self):
        return "(anyconst {}'{})".format(self.nbits, "s" if self.signed else "")


@final
class AnySeq(AnyValue):
    def __repr__(self):
        return "(anyseq {}'{})".format(self.nbits, "s" if self.signed else "")


@final
class Operator(Value):
    def __init__(self, op, operands, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)
        self.op = op
        self.operands = [Value.wrap(o) for o in operands]

    @staticmethod
    def _bitwise_binary_shape(a_shape, b_shape):
        a_bits, a_sign = a_shape
        b_bits, b_sign = b_shape
        if not a_sign and not b_sign:
            # both operands unsigned
            return max(a_bits, b_bits), False
        elif a_sign and b_sign:
            # both operands signed
            return max(a_bits, b_bits), True
        elif not a_sign and b_sign:
            # first operand unsigned (add sign bit), second operand signed
            return max(a_bits + 1, b_bits), True
        else:
            # first signed, second operand unsigned (add sign bit)
            return max(a_bits, b_bits + 1), True

    def shape(self):
        op_shapes = list(map(lambda x: x.shape(), self.operands))
        if len(op_shapes) == 1:
            (a_width, a_signed), = op_shapes
            if self.op in ("+", "~"):
                return a_width, a_signed
            if self.op == "-":
                if not a_signed:
                    return a_width + 1, True
                else:
                    return a_width, a_signed
            if self.op in ("b", "r|", "r&", "r^"):
                return 1, False
        elif len(op_shapes) == 2:
            (a_width, a_signed), (b_width, b_signed) = op_shapes
            if self.op == "+" or self.op == "-":
                width, signed = self._bitwise_binary_shape(*op_shapes)
                return width + 1, signed
            if self.op == "*":
                return a_width + b_width, a_signed or b_signed
            if self.op == "//":
                # division by -1 can overflow
                return a_width + b_signed, a_signed or b_signed
            if self.op == "%":
                return a_width, a_signed
            if self.op in ("<", "<=", "==", "!=", ">", ">="):
                return 1, False
            if self.op in ("&", "^", "|"):
                return self._bitwise_binary_shape(*op_shapes)
            if self.op == "<<":
                if b_signed:
                    extra = 2 ** (b_width - 1) - 1
                else:
                    extra = 2 ** (b_width)     - 1
                return a_width + extra, a_signed
            if self.op == ">>":
                if b_signed:
                    extra = 2 ** (b_width - 1)
                else:
                    extra = 0
                return a_width + extra, a_signed
        elif len(op_shapes) == 3:
            if self.op == "m":
                s_shape, a_shape, b_shape = op_shapes
                return self._bitwise_binary_shape(a_shape, b_shape)
        raise NotImplementedError("Operator {}/{} not implemented"
                                  .format(self.op, len(op_shapes))) # :nocov:

    def _rhs_signals(self):
        return union(op._rhs_signals() for op in self.operands)

    def __repr__(self):
        return "({} {})".format(self.op, " ".join(map(repr, self.operands)))


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
    sel = Value.wrap(sel)
    if len(sel) != 1:
        sel = sel.bool()
    return Operator("m", [sel, val1, val0])


@final
class Slice(Value):
    def __init__(self, value, start, end, *, src_loc_at=0):
        if not isinstance(start, int):
            raise TypeError("Slice start must be an integer, not '{!r}'".format(start))
        if not isinstance(end, int):
            raise TypeError("Slice end must be an integer, not '{!r}'".format(end))

        n = len(value)
        if start not in range(-(n+1), n+1):
            raise IndexError("Cannot start slice {} bits into {}-bit value".format(start, n))
        if start < 0:
            start += n
        if end not in range(-(n+1), n+1):
            raise IndexError("Cannot end slice {} bits into {}-bit value".format(end, n))
        if end < 0:
            end += n
        if start > end:
            raise IndexError("Slice start {} must be less than slice end {}".format(start, end))

        super().__init__(src_loc_at=src_loc_at)
        self.value = Value.wrap(value)
        self.start = start
        self.end   = end

    def shape(self):
        return self.end - self.start, False

    def _lhs_signals(self):
        return self.value._lhs_signals()

    def _rhs_signals(self):
        return self.value._rhs_signals()

    def __repr__(self):
        return "(slice {} {}:{})".format(repr(self.value), self.start, self.end)


@final
class Part(Value):
    def __init__(self, value, offset, width, stride=1, *, src_loc_at=0):
        if not isinstance(width, int) or width < 0:
            raise TypeError("Part width must be a non-negative integer, not '{!r}'".format(width))
        if not isinstance(stride, int) or stride <= 0:
            raise TypeError("Part stride must be a positive integer, not '{!r}'".format(stride))

        super().__init__(src_loc_at=src_loc_at)
        self.value  = value
        self.offset = Value.wrap(offset)
        self.width  = width
        self.stride = stride

    def shape(self):
        return self.width, False

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
        Resulting ``Value`` obtained by concatentation.
    """
    def __init__(self, *args, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.parts = [Value.wrap(v) for v in flatten(args)]

    def shape(self):
        return sum(len(part) for part in self.parts), False

    def _lhs_signals(self):
        return union((part._lhs_signals() for part in self.parts), start=ValueSet())

    def _rhs_signals(self):
        return union((part._rhs_signals() for part in self.parts), start=ValueSet())

    def _as_const(self):
        value = 0
        for part in reversed(self.parts):
            value <<= len(part)
            value |= part._as_const()
        return value

    def __repr__(self):
        return "(cat {})".format(" ".join(map(repr, self.parts)))


@final
class Repl(Value):
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
    Repl, out
        Replicated value.
    """
    def __init__(self, value, count, *, src_loc_at=0):
        if not isinstance(count, int) or count < 0:
            raise TypeError("Replication count must be a non-negative integer, not '{!r}'"
                            .format(count))

        super().__init__(src_loc_at=src_loc_at)
        self.value = Value.wrap(value)
        self.count = count

    def shape(self):
        return len(self.value) * self.count, False

    def _rhs_signals(self):
        return self.value._rhs_signals()

    def __repr__(self):
        return "(repl {!r} {})".format(self.value, self.count)


@final
class Signal(Value, DUID):
    """A varying integer value.

    Parameters
    ----------
    shape : int or tuple or None
        Either an integer ``width`` or a tuple ``(width, signed)`` specifying the number of bits
        in this ``Signal`` and whether it is signed (can represent negative values).
        ``shape`` defaults to 1-bit and non-signed.
    name : str
        Name hint for this signal. If ``None`` (default) the name is inferred from the variable
        name this ``Signal`` is assigned to. Name collisions are automatically resolved by
        prepending names of objects that contain this ``Signal`` and by appending integer
        sequences.
    reset : int
        Reset (synchronous) or default (combinatorial) value.
        When this ``Signal`` is assigned to in synchronous context and the corresponding clock
        domain is reset, the ``Signal`` assumes the given value. When this ``Signal`` is unassigned
        in combinatorial context (due to conditional assignments not being taken), the ``Signal``
        assumes its ``reset`` value. Defaults to 0.
    reset_less : bool
        If ``True``, do not generate reset logic for this ``Signal`` in synchronous statements.
        The ``reset`` value is only used as a combinatorial default or as the initial value.
        Defaults to ``False``.
    min : int or None
    max : int or None
        If ``shape`` is ``None``, the signal bit width and signedness are
        determined by the integer range given by ``min`` (inclusive,
        defaults to 0) and ``max`` (exclusive, defaults to 2).
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
    """

    def __init__(self, shape=None, *, name=None, reset=0, reset_less=False, min=None, max=None,
                 attrs=None, decoder=None, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)

        # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
        if min is not None or max is not None:
            warnings.warn("instead of `Signal(min={min}, max={max})`, "
                          "use `Signal.range({min}, {max})`"
                          .format(min=min or 0, max=max or 2),
                          DeprecationWarning, stacklevel=2 + src_loc_at)

        if name is not None and not isinstance(name, str):
            raise TypeError("Name must be a string, not '{!r}'".format(name))
        self.name = name or tracer.get_var_name(depth=2 + src_loc_at, default="$signal")

        if shape is None:
            if min is None:
                min = 0
            if max is None:
                max = 2
            max -= 1  # make both bounds inclusive
            if min > max:
                raise ValueError("Lower bound {} should be less or equal to higher bound {}"
                                 .format(min, max + 1))
            self.signed = min < 0 or max < 0
            if min == max:
                self.width = 0
            else:
                self.width = builtins.max(bits_for(min, self.signed),
                                          bits_for(max, self.signed))

        else:
            if not (min is None and max is None):
                raise ValueError("Only one of bits/signedness or bounds may be specified")
            if isinstance(shape, int):
                self.width, self.signed = shape, False
            else:
                self.width, self.signed = shape

        if not isinstance(self.width, int) or self.width < 0:
            raise TypeError("Width must be a non-negative integer, not '{!r}'".format(self.width))

        reset_width = bits_for(reset, self.signed)
        if reset != 0 and reset_width > self.width:
            warnings.warn("Reset value {!r} requires {} bits to represent, but the signal "
                          "only has {} bits"
                          .format(reset, reset_width, self.width),
                          SyntaxWarning, stacklevel=2 + src_loc_at)

        self.reset = int(reset)
        self.reset_less = bool(reset_less)

        self.attrs = OrderedDict(() if attrs is None else attrs)
        if isinstance(decoder, type) and issubclass(decoder, Enum):
            def enum_decoder(value):
                try:
                    return "{0.name:}/{0.value:}".format(decoder(value))
                except ValueError:
                    return str(value)
            self.decoder = enum_decoder
        else:
            self.decoder = decoder

    @classmethod
    def range(cls, *args, src_loc_at=0, **kwargs):
        """Create Signal that can represent a given range.

        The parameters to ``Signal.range`` are the same as for the built-in ``range`` function.
        That is, for any given ``range(*args)``, ``Signal.range(*args)`` can represent any
        ``x for x in range(*args)``.
        """
        value_range = range(*args)
        if len(value_range) > 0:
            signed = value_range.start < 0 or (value_range.stop - value_range.step) < 0
        else:
            signed = value_range.start < 0
        width = max(bits_for(value_range.start, signed),
                    bits_for(value_range.stop - value_range.step, signed))
        return cls((width, signed), src_loc_at=1 + src_loc_at, **kwargs)

    @classmethod
    def enum(cls, enum_type, *, src_loc_at=0, **kwargs):
        """Create Signal that can represent a given enumeration.

        Parameters
        ----------
        enum : type (inheriting from :class:`enum.Enum`)
            Enumeration to base this Signal on.
        """
        if not issubclass(enum_type, Enum):
            raise TypeError("Type {!r} is not an enumeration")
        return cls(_enum_shape(enum_type), src_loc_at=1 + src_loc_at, decoder=enum_type, **kwargs)

    @classmethod
    def like(cls, other, *, name=None, name_suffix=None, src_loc_at=0, **kwargs):
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
        kw = dict(shape=cls.wrap(other).shape(), name=new_name)
        if isinstance(other, cls):
            kw.update(reset=other.reset, reset_less=other.reset_less,
                      attrs=other.attrs, decoder=other.decoder)
        kw.update(kwargs)
        return cls(**kw, src_loc_at=1 + src_loc_at)

    # TODO(nmigen-0.2): move this to nmigen.compat and make it a deprecated extension
    @property
    @deprecated("instead of `signal.nbits`, use `signal.width`")
    def nbits(self):
        return self.width

    @nbits.setter
    @deprecated("instead of `signal.nbits = x`, use `signal.width = x`")
    def nbits(self, value):
        self.width = value

    def shape(self):
        return self.width, self.signed

    def _lhs_signals(self):
        return ValueSet((self,))

    def _rhs_signals(self):
        return ValueSet((self,))

    def __repr__(self):
        return "(sig {})".format(self.name)


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
            raise TypeError("Clock domain name must be a string, not '{!r}'".format(domain))
        if domain == "comb":
            raise ValueError("Domain '{}' does not have a clock".format(domain))
        self.domain = domain

    def shape(self):
        return 1, False

    def _lhs_signals(self):
        return ValueSet((self,))

    def _rhs_signals(self):
        raise NotImplementedError("ClockSignal must be lowered to a concrete signal") # :nocov:

    def __repr__(self):
        return "(clk {})".format(self.domain)


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
            raise TypeError("Clock domain name must be a string, not '{!r}'".format(domain))
        if domain == "comb":
            raise ValueError("Domain '{}' does not have a reset".format(domain))
        self.domain = domain
        self.allow_reset_less = allow_reset_less

    def shape(self):
        return 1, False

    def _lhs_signals(self):
        return ValueSet((self,))

    def _rhs_signals(self):
        raise NotImplementedError("ResetSignal must be lowered to a concrete signal") # :nocov:

    def __repr__(self):
        return "(rst {})".format(self.domain)


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
        self.index = Value.wrap(index)

    def __getattr__(self, attr):
        return ArrayProxy([getattr(elem, attr) for elem in self.elems], self.index)

    def __getitem__(self, index):
        return ArrayProxy([        elem[index] for elem in self.elems], self.index)

    def _iter_as_values(self):
        return (Value.wrap(elem) for elem in self.elems)

    def shape(self):
        width, signed = 0, False
        for elem_width, elem_signed in (elem.shape() for elem in self._iter_as_values()):
            width  = max(width, elem_width + elem_signed)
            signed = max(signed, elem_signed)
        return width, signed

    def _lhs_signals(self):
        signals = union((elem._lhs_signals() for elem in self._iter_as_values()), start=ValueSet())
        return signals

    def _rhs_signals(self):
        signals = union((elem._rhs_signals() for elem in self._iter_as_values()), start=ValueSet())
        return self.index._rhs_signals() | signals

    def __repr__(self):
        return "(proxy (array [{}]) {!r})".format(", ".join(map(repr, self.elems)), self.index)


class UserValue(Value):
    """Value with custom lowering.

    A ``UserValue`` is a value whose precise representation does not have to be immediately known,
    which is useful in certain metaprogramming scenarios. Instead of providing fixed semantics
    upfront, it is kept abstract for as long as possible, only being lowered to a concrete nMigen
    value when required.

    Note that the ``lower`` method will only be called once; this is necessary to ensure that
    nMigen's view of representation of all values stays internally consistent. If the class
    deriving from  ``UserValue`` is mutable, then it must ensure that after ``lower`` is called,
    it is not mutated in a way that changes its representation.

    The following is an incomplete list of actions that, when applied to an ``UserValue`` directly
    or indirectly, will cause it to be lowered, provided as an illustrative reference:
        * Querying the shape using ``.shape()`` or ``len()``;
        * Creating a similarly shaped signal using ``Signal.like``;
        * Indexing or iterating through individual bits;
        * Adding an assignment to the value to a ``Module`` using ``m.d.<domain> +=``.
    """
    def __init__(self, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)
        self.__lowered = None

    @abstractmethod
    def lower(self):
        """Conversion to a concrete representation."""
        pass # :nocov:

    def _lazy_lower(self):
        if self.__lowered is None:
            self.__lowered = Value.wrap(self.lower())
        return self.__lowered

    def shape(self):
        return self._lazy_lower().shape()

    def _lhs_signals(self):
        return self._lazy_lower()._lhs_signals()

    def _rhs_signals(self):
        return self._lazy_lower()._rhs_signals()


@final
class Sample(Value):
    """Value from the past.

    A ``Sample`` of an expression is equal to the value of the expression ``clocks`` clock edges
    of the ``domain`` clock back. If that moment is before the beginning of time, it is equal
    to the value of the expression calculated as if each signal had its reset value.
    """
    def __init__(self, expr, clocks, domain, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)
        self.value  = Value.wrap(expr)
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
        return ValueSet((self,))

    def __repr__(self):
        return "(sample {!r} @ {}[{}])".format(
            self.value, "<default>" if self.domain is None else self.domain, self.clocks)


def Past(expr, clocks=1, domain=None):
    return Sample(expr, clocks, domain)


def Stable(expr, clocks=0, domain=None):
    return Sample(expr, clocks + 1, domain) == Sample(expr, clocks, domain)


def Rose(expr, clocks=0, domain=None):
    return ~Sample(expr, clocks + 1, domain) & Sample(expr, clocks, domain)


def Fell(expr, clocks=0, domain=None):
    return Sample(expr, clocks + 1, domain) & ~Sample(expr, clocks, domain)


@final
class Initial(Value):
    """Start indicator, for model checking.

    An ``Initial`` signal is ``1`` at the first cycle of model checking, and ``0`` at any other.
    """
    def __init__(self, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)

    def shape(self):
        return (1, False)

    def _rhs_signals(self):
        return ValueSet((self,))

    def __repr__(self):
        return "(initial)"


class _StatementList(list):
    def __repr__(self):
        return "({})".format(" ".join(map(repr, self)))


class Statement:
    def __init__(self, *, src_loc_at=0):
        self.src_loc = tracer.get_src_loc(1 + src_loc_at)

    @staticmethod
    def wrap(obj):
        if isinstance(obj, Iterable):
            return _StatementList(sum((Statement.wrap(e) for e in obj), []))
        else:
            if isinstance(obj, Statement):
                return _StatementList([obj])
            else:
                raise TypeError("Object '{!r}' is not an nMigen statement".format(obj))


@final
class Assign(Statement):
    def __init__(self, lhs, rhs, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.lhs = Value.wrap(lhs)
        self.rhs = Value.wrap(rhs)

    def _lhs_signals(self):
        return self.lhs._lhs_signals()

    def _rhs_signals(self):
        return self.lhs._rhs_signals() | self.rhs._rhs_signals()

    def __repr__(self):
        return "(eq {!r} {!r})".format(self.lhs, self.rhs)


class Property(Statement):
    def __init__(self, test, *, _check=None, _en=None, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.test   = Value.wrap(test)
        self._check = _check
        self._en    = _en
        if self._check is None:
            self._check = Signal(reset_less=True, name="${}$check".format(self._kind))
            self._check.src_loc = self.src_loc
        if _en is None:
            self._en = Signal(reset_less=True, name="${}$en".format(self._kind))
            self._en.src_loc = self.src_loc

    def _lhs_signals(self):
        return ValueSet((self._en, self._check))

    def _rhs_signals(self):
        return self.test._rhs_signals()

    def __repr__(self):
        return "({} {!r})".format(self._kind, self.test)


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

        self.test  = Value.wrap(test)
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
            for key in keys:
                if isinstance(key, (bool, int)):
                    key = "{:0{}b}".format(key, len(self.test))
                elif isinstance(key, str):
                    pass
                elif isinstance(key, Enum):
                    key = _enum_to_bits(key)
                else:
                    raise TypeError("Object '{!r}' cannot be used as a switch key"
                                    .format(key))
                assert len(key) == len(self.test)
                new_keys = (*new_keys, key)
            if not isinstance(stmts, Iterable):
                stmts = [stmts]
            self.cases[new_keys] = Statement.wrap(stmts)
            if orig_keys in case_src_locs:
                self.case_src_locs[new_keys] = case_src_locs[orig_keys]

    def _lhs_signals(self):
        signals = union((s._lhs_signals() for ss in self.cases.values() for s in ss),
                        start=ValueSet())
        return signals

    def _rhs_signals(self):
        signals = union((s._rhs_signals() for ss in self.cases.values() for s in ss),
                        start=ValueSet())
        return self.test._rhs_signals() | signals

    def __repr__(self):
        def case_repr(keys, stmts):
            stmts_repr = " ".join(map(repr, stmts))
            if keys == ():
                return "(default {})".format(stmts_repr)
            elif len(keys) == 1:
                return "(case {} {})".format(keys[0], stmts_repr)
            else:
                return "(case ({}) {})".format(" ".join(keys), stmts_repr)
        case_reprs = [case_repr(keys, stmts) for keys, stmts in self.cases.items()]
        return "(switch {!r} {})".format(self.test, " ".join(case_reprs))


@final
class Delay(Statement):
    def __init__(self, interval=None, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.interval = None if interval is None else float(interval)

    def _rhs_signals(self):
        return ValueSet()

    def __repr__(self):
        if self.interval is None:
            return "(delay ε)"
        else:
            return "(delay {:.3}us)".format(self.interval * 1e6)


@final
class Tick(Statement):
    def __init__(self, domain="sync", *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.domain = str(domain)

    def _rhs_signals(self):
        return ValueSet()

    def __repr__(self):
        return "(tick {})".format(self.domain)


@final
class Passive(Statement):
    def __init__(self, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)

    def _rhs_signals(self):
        return ValueSet()

    def __repr__(self):
        return "(passive)"


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
        pairs = ["({!r}, {!r})".format(k, v) for k, v in self.items()]
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
        self.value = Value.wrap(value)
        if isinstance(self.value, Const):
            self._hash = hash(self.value.value)
        elif isinstance(self.value, (Signal, AnyValue)):
            self._hash = hash(self.value.duid)
        elif isinstance(self.value, (ClockSignal, ResetSignal)):
            self._hash = hash(self.value.domain)
        elif isinstance(self.value, Operator):
            self._hash = hash((self.value.op, tuple(ValueKey(o) for o in self.value.operands)))
        elif isinstance(self.value, Slice):
            self._hash = hash((ValueKey(self.value.value), self.value.start, self.value.end))
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
            raise TypeError("Object '{!r}' cannot be used as a key in value collections"
                            .format(self.value))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if type(other) is not ValueKey:
            return False
        if type(self.value) is not type(other.value):
            return False

        if isinstance(self.value, Const):
            return self.value.value == other.value.value
        elif isinstance(self.value, (Signal, AnyValue)):
            return self.value is other.value
        elif isinstance(self.value, (ClockSignal, ResetSignal)):
            return self.value.domain == other.value.domain
        elif isinstance(self.value, Operator):
            return (self.value.op == other.value.op and
                    len(self.value.operands) == len(other.value.operands) and
                    all(ValueKey(a) == ValueKey(b)
                        for a, b in zip(self.value.operands, other.value.operands)))
        elif isinstance(self.value, Slice):
            return (ValueKey(self.value.value) == ValueKey(other.value.value) and
                    self.value.start == other.value.start and
                    self.value.end == other.value.end)
        elif isinstance(self.value, Part):
            return (ValueKey(self.value.value) == ValueKey(other.value.value) and
                    ValueKey(self.value.offset) == ValueKey(other.value.offset) and
                    self.value.width == other.value.width and
                    self.value.stride == other.value.stride)
        elif isinstance(self.value, Cat):
            return all(ValueKey(a) == ValueKey(b)
                        for a, b in zip(self.value.parts, other.value.parts))
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
            raise TypeError("Object '{!r}' cannot be used as a key in value collections"
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
            raise TypeError("Object '{!r}' cannot be used as a key in value collections")

    def __repr__(self):
        return "<{}.ValueKey {!r}>".format(__name__, self.value)


class ValueDict(_MappedKeyDict):
    _map_key   = ValueKey
    _unmap_key = lambda self, key: key.value


class ValueSet(_MappedKeySet):
    _map_key   = ValueKey
    _unmap_key = lambda self, key: key.value


class SignalKey:
    def __init__(self, signal):
        self.signal = signal
        if type(signal) is Signal:
            self._intern = (0, signal.duid)
        elif type(signal) is ClockSignal:
            self._intern = (1, signal.domain)
        elif type(signal) is ResetSignal:
            self._intern = (2, signal.domain)
        else:
            raise TypeError("Object '{!r}' is not an nMigen signal".format(signal))

    def __hash__(self):
        return hash(self._intern)

    def __eq__(self, other):
        if type(other) is not SignalKey:
            return False
        return self._intern == other._intern

    def __lt__(self, other):
        if type(other) is not SignalKey:
            raise TypeError("Object '{!r}' cannot be compared to a SignalKey".format(signal))
        return self._intern < other._intern

    def __repr__(self):
        return "<{}.SignalKey {!r}>".format(__name__, self.signal)


class SignalDict(_MappedKeyDict):
    _map_key   = SignalKey
    _unmap_key = lambda self, key: key.signal


class SignalSet(_MappedKeySet):
    _map_key   = SignalKey
    _unmap_key = lambda self, key: key.signal
