from abc import ABCMeta, abstractmethod
import builtins
import traceback
from collections import OrderedDict
from collections.abc import Iterable, MutableMapping, MutableSet, MutableSequence

from .. import tracer
from ..tools import *


__all__ = [
    "Value", "Const", "C", "AnyConst", "AnySeq", "Operator", "Mux", "Part", "Slice", "Cat", "Repl",
    "Array", "ArrayProxy",
    "Sample", "Past", "Stable", "Rose", "Fell",
    "Signal", "ClockSignal", "ResetSignal",
    "Statement", "Assign", "Assert", "Assume", "Switch", "Delay", "Tick",
    "Passive", "ValueKey", "ValueDict", "ValueSet", "SignalKey", "SignalDict",
    "SignalSet",
]


class DUID:
    """Deterministic Unique IDentifier"""
    __next_uid = 0
    def __init__(self):
        self.duid = DUID.__next_uid
        DUID.__next_uid += 1


class Value(metaclass=ABCMeta):
    @staticmethod
    def wrap(obj):
        """Ensures that the passed object is an nMigen value. Booleans and integers
        are automatically wrapped into ``Const``."""
        if isinstance(obj, Value):
            return obj
        elif isinstance(obj, (bool, int)):
            return Const(obj)
        else:
            raise TypeError("Object '{!r}' is not an nMigen value".format(obj))

    def __init__(self, src_loc_at=0):
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
    def __div__(self, other):
        return Operator("/", [self, other])
    def __rdiv__(self, other):
        return Operator("/", [other, self])
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
            Output ``Value``. If any bits are set, returns ``1``, else ``0``.
        """
        return Operator("b", [self])

    def implies(premise, conclusion):
        """Implication.

        Returns
        -------
        Value, out
            ``0`` if ``premise`` is true and ``conclusion`` is not, ``1`` otherwise.
        """
        return ~premise | conclusion

    def part(self, offset, width):
        """Indexed part-select.

        Selects a constant width but variable offset part of a ``Value``.

        Parameters
        ----------
        offset : Value, in
            start point of the selected bits
        width : int
            number of selected bits

        Returns
        -------
        Part, out
            Selected part of the ``Value``
        """
        return Part(self, offset, width)

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
        return Assign(self, value)

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


class Const(Value):
    """A constant, literal integer value.

    Parameters
    ----------
    value : int
    shape : int or tuple or None
        Either an integer `bits` or a tuple `(bits, signed)`
        specifying the number of bits in this `Const` and whether it is
        signed (can represent negative values). `shape` defaults
        to the minimum width and signedness of `value`.

    Attributes
    ----------
    nbits : int
    signed : bool
    """
    src_loc = None

    @staticmethod
    def normalize(value, shape):
        nbits, signed = shape
        mask = (1 << nbits) - 1
        value &= mask
        if signed and value >> (nbits - 1):
            value |= ~mask
        return value

    def __init__(self, value, shape=None):
        self.value = int(value)
        if shape is None:
            shape = bits_for(self.value), self.value < 0
        if isinstance(shape, int):
            shape = shape, self.value < 0
        self.nbits, self.signed = shape
        if not isinstance(self.nbits, int) or self.nbits < 0:
            raise TypeError("Width must be a non-negative integer, not '{!r}'", self.nbits)
        self.value = self.normalize(self.value, shape)

    def shape(self):
        return self.nbits, self.signed

    def _rhs_signals(self):
        return ValueSet()

    def _as_const(self):
        return self.value

    def __repr__(self):
        return "(const {}'{}d{})".format(self.nbits, "s" if self.signed else "", self.value)


C = Const  # shorthand


class AnyValue(Value, DUID):
    def __init__(self, shape):
        super().__init__(src_loc_at=0)
        if isinstance(shape, int):
            shape = shape, False
        self.nbits, self.signed = shape
        if not isinstance(self.nbits, int) or self.nbits < 0:
            raise TypeError("Width must be a non-negative integer, not '{!r}'", self.nbits)

    def shape(self):
        return self.nbits, self.signed

    def _rhs_signals(self):
        return ValueSet()


class AnyConst(AnyValue):
    def __repr__(self):
        return "(anyconst {}'{})".format(self.nbits, "s" if self.signed else "")


class AnySeq(AnyValue):
    def __repr__(self):
        return "(anyseq {}'{})".format(self.nbits, "s" if self.signed else "")


class Operator(Value):
    def __init__(self, op, operands, src_loc_at=0):
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
            (a_bits, a_sign), = op_shapes
            if self.op in ("+", "~"):
                return a_bits, a_sign
            if self.op == "-":
                if not a_sign:
                    return a_bits + 1, True
                else:
                    return a_bits, a_sign
            if self.op == "b":
                return 1, False
        elif len(op_shapes) == 2:
            (a_bits, a_sign), (b_bits, b_sign) = op_shapes
            if self.op == "+" or self.op == "-":
                bits, sign = self._bitwise_binary_shape(*op_shapes)
                return bits + 1, sign
            if self.op == "*":
                return a_bits + b_bits, a_sign or b_sign
            if self.op == "%":
                return a_bits, a_sign
            if self.op in ("<", "<=", "==", "!=", ">", ">=", "b"):
                return 1, False
            if self.op in ("&", "^", "|"):
                return self._bitwise_binary_shape(*op_shapes)
            if self.op == "<<":
                if b_sign:
                    extra = 2 ** (b_bits - 1) - 1
                else:
                    extra = 2 ** (b_bits)     - 1
                return a_bits + extra, a_sign
            if self.op == ">>":
                if b_sign:
                    extra = 2 ** (b_bits - 1)
                else:
                    extra = 0
                return a_bits + extra, a_sign
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
    return Operator("m", [sel, val1, val0], src_loc_at=1)


class Slice(Value):
    def __init__(self, value, start, end):
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

        super().__init__()
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


class Part(Value):
    def __init__(self, value, offset, width):
        if not isinstance(width, int) or width < 0:
            raise TypeError("Part width must be a non-negative integer, not '{!r}'".format(width))

        super().__init__()
        self.value  = value
        self.offset = Value.wrap(offset)
        self.width  = width

    def shape(self):
        return self.width, False

    def _lhs_signals(self):
        return self.value._lhs_signals()

    def _rhs_signals(self):
        return self.value._rhs_signals() | self.offset._rhs_signals()

    def __repr__(self):
        return "(part {} {} {})".format(repr(self.value), repr(self.offset), self.width)


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
    def __init__(self, *args):
        super().__init__()
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
    def __init__(self, value, count):
        if not isinstance(count, int) or count < 0:
            raise TypeError("Replication count must be a non-negative integer, not '{!r}'"
                            .format(count))

        super().__init__()
        self.value = Value.wrap(value)
        self.count = count

    def shape(self):
        return len(self.value) * self.count, False

    def _rhs_signals(self):
        return self.value._rhs_signals()

    def __repr__(self):
        return "(repl {!r} {})".format(self.value, self.count)


class Signal(Value, DUID):
    """A varying integer value.

    Parameters
    ----------
    shape : int or tuple or None
        Either an integer ``bits`` or a tuple ``(bits, signed)`` specifying the number of bits
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
    decoder : function
        A function converting integer signal values to human-readable strings (e.g. FSM state
        names).

    Attributes
    ----------
    nbits : int
    signed : bool
    name : str
    reset : int
    reset_less : bool
    attrs : dict
    """

    def __init__(self, shape=None, name=None, reset=0, reset_less=False, min=None, max=None,
                 attrs=None, decoder=None, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)

        if name is None:
            try:
                name = tracer.get_var_name(depth=2 + src_loc_at)
            except tracer.NameNotFound:
                name = "$signal"
        self.name = name

        if shape is None:
            if min is None:
                min = 0
            if max is None:
                max = 2
            max -= 1  # make both bounds inclusive
            if not min < max:
                raise ValueError("Lower bound {} should be less than higher bound {}"
                                 .format(min, max))
            self.signed = min < 0 or max < 0
            self.nbits  = builtins.max(bits_for(min, self.signed), bits_for(max, self.signed))

        else:
            if not (min is None and max is None):
                raise ValueError("Only one of bits/signedness or bounds may be specified")
            if isinstance(shape, int):
                self.nbits, self.signed = shape, False
            else:
                self.nbits, self.signed = shape

        if not isinstance(self.nbits, int) or self.nbits < 0:
            raise TypeError("Width must be a non-negative integer, not '{!r}'".format(self.nbits))
        self.reset = int(reset)
        self.reset_less = bool(reset_less)

        self.attrs = OrderedDict(() if attrs is None else attrs)
        self.decoder = decoder

    @classmethod
    def like(cls, other, name=None, src_loc_at=0, **kwargs):
        """Create Signal based on another.

        Parameters
        ----------
        other : Value
            Object to base this Signal on.
        """
        if name is None:
            try:
                name = tracer.get_var_name(depth=2 + src_loc_at)
            except tracer.NameNotFound:
                name = "$like"
        kw = dict(shape=cls.wrap(other).shape(), name=name)
        if isinstance(other, cls):
            kw.update(reset=other.reset, reset_less=other.reset_less,
                      attrs=other.attrs, decoder=other.decoder)
        kw.update(kwargs)
        return cls(**kw, src_loc_at=1 + src_loc_at)

    def shape(self):
        return self.nbits, self.signed

    def _lhs_signals(self):
        return ValueSet((self,))

    def _rhs_signals(self):
        return ValueSet((self,))

    def __repr__(self):
        return "(sig {})".format(self.name)


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
    def __init__(self, domain="sync"):
        super().__init__()
        if not isinstance(domain, str):
            raise TypeError("Clock domain name must be a string, not '{!r}'".format(domain))
        self.domain = domain

    def shape(self):
        return 1, False

    def _lhs_signals(self):
        return ValueSet((self,))

    def _rhs_signals(self):
        raise NotImplementedError("ClockSignal must be lowered to a concrete signal") # :nocov:

    def __repr__(self):
        return "(clk {})".format(self.domain)


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
    def __init__(self, domain="sync", allow_reset_less=False):
        super().__init__()
        if not isinstance(domain, str):
            raise TypeError("Clock domain name must be a string, not '{!r}'".format(domain))
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
            m.d.sync += gpios[bus.adr].eq(bus.dat_w)
        with m.Else():
            m.d.sync += bus.dat_r.eq(gpios[bus.adr])

    Multidimensional array::

        mult = Array(Array(x * y for y in range(10)) for x in range(10))
        a = Signal(max=10)
        b = Signal(max=10)
        r = Signal(8)
        m.d.comb += r.eq(mult[a][b])

    Array of records::

        layout = [
            ("re",     1),
            ("dat_r", 16),
        ]
        buses  = Array(Record(layout) for busno in range(4))
        master = Record(layout)
        m.d.comb += [
            buses[sel].re.eq(master.re),
            master.dat_r.eq(buses[sel].dat_r),
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


class ArrayProxy(Value):
    def __init__(self, elems, index):
        super().__init__(src_loc_at=1)
        self.elems = elems
        self.index = Value.wrap(index)

    def __getattr__(self, attr):
        return ArrayProxy([getattr(elem, attr) for elem in self.elems], self.index)

    def __getitem__(self, index):
        return ArrayProxy([        elem[index] for elem in self.elems], self.index)

    def _iter_as_values(self):
        return (Value.wrap(elem) for elem in self.elems)

    def shape(self):
        bits, sign = 0, False
        for elem_bits, elem_sign in (elem.shape() for elem in self._iter_as_values()):
            bits = max(bits, elem_bits + elem_sign)
            sign = max(sign, elem_sign)
        return bits, sign

    def _lhs_signals(self):
        signals = union((elem._lhs_signals() for elem in self._iter_as_values()), start=ValueSet())
        return signals

    def _rhs_signals(self):
        signals = union((elem._rhs_signals() for elem in self._iter_as_values()), start=ValueSet())
        return self.index._rhs_signals() | signals

    def __repr__(self):
        return "(proxy (array [{}]) {!r})".format(", ".join(map(repr, self.elems)), self.index)


class Sample(Value):
    """Value from the past.

    A ``Sample`` of an expression is equal to the value of the expression ``clocks`` clock edges
    of the ``domain`` clock back. If that moment is before the beginning of time, it is equal
    to the value of the expression calculated as if each signal had its reset value.
    """
    def __init__(self, expr, clocks, domain):
        super().__init__(src_loc_at=1)
        self.value  = Value.wrap(expr)
        self.clocks = int(clocks)
        self.domain = domain
        if not isinstance(self.value, (Const, Signal, ClockSignal, ResetSignal)):
            raise TypeError("Sampled value may only be a signal or a constant, not {!r}"
                            .format(self.value))
        if self.clocks < 0:
            raise ValueError("Cannot sample a value {} cycles in the future"
                             .format(-self.clocks))

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


class _StatementList(list):
    def __repr__(self):
        return "({})".format(" ".join(map(repr, self)))


class Statement:
    @staticmethod
    def wrap(obj):
        if isinstance(obj, Iterable):
            return _StatementList(sum((Statement.wrap(e) for e in obj), []))
        else:
            if isinstance(obj, Statement):
                return _StatementList([obj])
            else:
                raise TypeError("Object '{!r}' is not an nMigen statement".format(obj))


class Assign(Statement):
    def __init__(self, lhs, rhs):
        self.lhs = Value.wrap(lhs)
        self.rhs = Value.wrap(rhs)

    def _lhs_signals(self):
        return self.lhs._lhs_signals()

    def _rhs_signals(self):
        return self.lhs._rhs_signals() | self.rhs._rhs_signals()

    def __repr__(self):
        return "(eq {!r} {!r})".format(self.lhs, self.rhs)


class Property(Statement):
    def __init__(self, test, _check=None, _en=None):
        self.src_loc = tracer.get_src_loc()

        self.test = Value.wrap(test)

        self._check = _check
        if self._check is None:
            self._check = Signal(reset_less=True, name="${}$check".format(self._kind))
            self._check.src_loc = self.src_loc

        self._en = _en
        if _en is None:
            self._en = Signal(reset_less=True, name="${}$en".format(self._kind))
            self._en.src_loc = self.src_loc

    def _lhs_signals(self):
        return ValueSet((self._en, self._check))

    def _rhs_signals(self):
        return self.test._rhs_signals()

    def __repr__(self):
        return "({} {!r})".format(self._kind, self.test)


class Assert(Property):
    _kind = "assert"


class Assume(Property):
    _kind = "assume"


class Switch(Statement):
    def __init__(self, test, cases):
        self.test  = Value.wrap(test)
        self.cases = OrderedDict()
        for key, stmts in cases.items():
            if isinstance(key, (bool, int)):
                key = "{:0{}b}".format(key, len(self.test))
                assert len(key) <= len(self.test)
            elif isinstance(key, str):
                assert len(key) == len(self.test)
            else:
                raise TypeError("Object '{!r}' cannot be used as a switch key"
                                .format(key))
            if not isinstance(stmts, Iterable):
                stmts = [stmts]
            self.cases[key] = Statement.wrap(stmts)

    def _lhs_signals(self):
        signals = union((s._lhs_signals() for ss in self.cases.values() for s in ss),
                        start=ValueSet())
        return signals

    def _rhs_signals(self):
        signals = union((s._rhs_signals() for ss in self.cases.values() for s in ss),
                        start=ValueSet())
        return self.test._rhs_signals() | signals

    def __repr__(self):
        cases = ["(case {} {})".format(key, " ".join(map(repr, stmts)))
                 for key, stmts in self.cases.items()]
        return "(switch {!r} {})".format(self.test, " ".join(cases))


class Delay(Statement):
    def __init__(self, interval=None):
        self.interval = None if interval is None else float(interval)

    def _rhs_signals(self):
        return ValueSet()

    def __repr__(self):
        if self.interval is None:
            return "(delay ε)"
        else:
            return "(delay {:.3}us)".format(self.interval * 10e6)


class Tick(Statement):
    def __init__(self, domain="sync"):
        self.domain = str(domain)

    def _rhs_signals(self):
        return ValueSet()

    def __repr__(self):
        return "(tick {})".format(self.domain)


class Passive(Statement):
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

    def __hash__(self):
        if isinstance(self.value, Const):
            return hash(self.value.value)
        elif isinstance(self.value, (Signal, AnyValue)):
            return hash(self.value.duid)
        elif isinstance(self.value, (ClockSignal, ResetSignal)):
            return hash(self.value.domain)
        elif isinstance(self.value, Operator):
            return hash((self.value.op, tuple(ValueKey(o) for o in self.value.operands)))
        elif isinstance(self.value, Slice):
            return hash((ValueKey(self.value.value), self.value.start, self.value.end))
        elif isinstance(self.value, Part):
            return hash((ValueKey(self.value.value), ValueKey(self.value.offset),
                         self.value.width))
        elif isinstance(self.value, Cat):
            return hash(tuple(ValueKey(o) for o in self.value.parts))
        elif isinstance(self.value, ArrayProxy):
            return hash((ValueKey(self.value.index),
                         tuple(ValueKey(e) for e in self.value._iter_as_values())))
        elif isinstance(self.value, Sample):
            return hash((ValueKey(self.value.value), self.value.clocks, self.value.domain))
        else: # :nocov:
            raise TypeError("Object '{!r}' cannot be used as a key in value collections"
                            .format(self.value))

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
                    self.value.width == other.value.width)
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
        if type(signal) is Signal:
            self._intern = (0, signal.duid)
        elif type(signal) is ClockSignal:
            self._intern = (1, signal.domain)
        elif type(signal) is ResetSignal:
            self._intern = (2, signal.domain)
        else:
            raise TypeError("Object '{!r}' is not an nMigen signal".format(signal))
        self.signal = signal

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
