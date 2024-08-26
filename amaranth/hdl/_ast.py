from abc import ABCMeta, abstractmethod
import warnings
import functools
import operator
import string
import re
from collections import OrderedDict
from collections.abc import Iterable, MutableMapping, MutableSet, MutableSequence
from enum import Enum, EnumMeta
from itertools import chain

from .. import tracer
from ..utils import *
from .._utils import *
from .._unused import *


__all__ = [
    "SyntaxError", "SyntaxWarning",
    "Shape", "signed", "unsigned", "ShapeCastable", "ShapeLike",
    "Value", "Const", "C", "AnyValue", "AnyConst", "AnySeq", "Operator", "Mux", "Part", "Slice", "Cat", "Concat", "SwitchValue",
    "Array", "ArrayProxy",
    "Signal", "ClockSignal", "ResetSignal",
    "ValueCastable", "ValueLike",
    "Initial",
    "Format",
    "Statement", "Switch",
    "Property", "Assign", "Print", "Assert", "Assume", "Cover",
    "IOValue", "IOPort", "IOConcat", "IOSlice",
    "SignalKey", "SignalDict", "SignalSet",
]


class SyntaxError(Exception):
    pass


class SyntaxWarning(Warning):
    pass


class DUID:
    """Deterministic Unique IDentifier."""
    __next_uid = 0
    def __init__(self):
        self.duid = DUID.__next_uid
        DUID.__next_uid += 1


class Shape:
    """Bit width and signedness of a :class:`Value`.

    A :class:`Shape` can be obtained by:

    * constructing with explicit bit width and signedness;
    * using the :func:`signed` and :func:`unsigned` aliases if the signedness is known upfront;
    * casting from a variety of objects using the :meth:`cast` method.

    Parameters
    ----------
    width : int
        The number of bits in the representation of a value. This includes the sign bit for signed
        values. Cannot be zero if the value is signed.
    signed : bool
        Whether the value is signed. Signed values use the
        `two's complement <https://en.wikipedia.org/wiki/Two's_complement>`_ representation.
    """
    def __init__(self, width=1, signed=False):
        if not isinstance(width, int):
            raise TypeError(f"Width must be an integer, not {width!r}")
        if not signed and width < 0:
            raise TypeError(f"Width of an unsigned value must be zero or a positive integer, "
                            f"not {width}")
        if signed and width <= 0:
            raise TypeError(f"Width of a signed value must be a positive integer, not {width}")
        self._width = width
        self._signed = bool(signed)

    @property
    def width(self):
        return self._width

    @property
    def signed(self):
        return self._signed

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
        """Cast :py:`obj` to a shape.

        Many :ref:`shape-like <lang-shapelike>` objects can be cast to a shape:

        * a :class:`Shape`, where the result is itself;
        * an :class:`int`, where the result is :func:`unsigned(obj) <unsigned>`;
        * a :class:`range`, where the result has minimal width required to represent all elements
          of the range, and is signed if any element of the range is signed;
        * an :class:`enum.Enum` whose members are all :ref:`constant-castable <lang-constcasting>`
          or :class:`enum.IntEnum`, where the result is wide enough to represent any member of
          the enumeration, and is signed if any member of the enumeration is signed;
        * a :class:`ShapeCastable` object, where the result is obtained by repeatedly calling
          :meth:`obj.as_shape() <ShapeCastable.as_shape>`.

        Raises
        ------
        TypeError
            If :py:`obj` cannot be converted to a :class:`Shape`.
        RecursionError
            If :py:`obj` is a :class:`ShapeCastable` object that casts to itself.
        """
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
                if obj[0] == obj[-1] == 0:
                    width = 0
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
        """Python code that creates this shape.

        Returns :py:`f"signed({self.width})"` or :py:`f"unsigned({self.width})"`.
        """
        if self.signed:
            return f"signed({self.width})"
        else:
            return f"unsigned({self.width})"

    def __hash__(self):
        return hash((self._width, self._signed))

    def __eq__(self, other):
        return (isinstance(other, Shape) and
                self.width == other.width and self.signed == other.signed)

    @staticmethod
    def _unify(shapes):
        """Returns the minimal shape that contains all shapes from the list.

        If no shapes passed in, returns unsigned(0).
        """
        unsigned_width = signed_width = 0
        has_signed = False
        for shape in shapes:
            assert isinstance(shape, Shape)
            if shape.signed:
                has_signed = True
                signed_width = max(signed_width, shape.width)
            else:
                unsigned_width = max(unsigned_width, shape.width)
        # If all shapes unsigned, simply take max.
        if not has_signed:
            return unsigned(unsigned_width)
        # Otherwise, result is signed. All unsigned inputs, if any,
        # need to be converted to signed by adding a zero bit.
        return signed(max(signed_width, unsigned_width + 1))


def unsigned(width):
    """Returns :py:`Shape(width, signed=False)`."""
    return Shape(width, signed=False)


def signed(width):
    """Returns :py:`Shape(width, signed=True)`."""
    return Shape(width, signed=True)


class ShapeCastable:
    """Interface class for objects that can be cast to a :class:`Shape`.

    Shapes of values in the Amaranth language are specified using :ref:`shape-like objects
    <lang-shapelike>`. Inheriting a class from :class:`ShapeCastable` and implementing all of
    the methods described below adds instances of that class to the list of shape-like objects
    recognized by the :meth:`Shape.cast` method. This is a part of the mechanism for seamlessly
    extending the Amaranth language in third-party code.

    To illustrate their purpose, consider constructing a signal from a shape-castable object
    :py:`shape_castable`:

    .. code::

        value_like = Signal(shape_castable, init=initializer)

    The code above is equivalent to:

    .. code::

        value_like = shape_castable(Signal(
            shape_castable.as_shape(),
            init=shape_castable.const(initializer)
        ))

    Note that the :py:`shape_castable(x)` syntax performs :py:`shape_castable.__call__(x)`.

    .. tip::

        The source code of the :mod:`amaranth.lib.data` module can be used as a reference for
        implementing a fully featured shape-castable object.
    """

    def __init__(self, *args, **kwargs):
        if type(self) is ShapeCastable:
            raise TypeError("Can't instantiate abstract class ShapeCastable")
        super().__init__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs):
        if cls.as_shape is ShapeCastable.as_shape:
            raise TypeError(f"Class '{cls.__qualname__}' deriving from 'ShapeCastable' must override "
                            f"the 'as_shape' method")
        if cls.const is ShapeCastable.const:
            raise TypeError(f"Class '{cls.__qualname__}' deriving from 'ShapeCastable' must override "
                            f"the 'const' method")
        if cls.__call__ is ShapeCastable.__call__:
            raise TypeError(f"Class '{cls.__qualname__}' deriving from 'ShapeCastable' must override "
                            f"the '__call__' method")
        if cls.from_bits is ShapeCastable.from_bits:
            warnings.warn(f"Class '{cls.__qualname__}' deriving from 'ShapeCastable' does not override "
                          f"the 'from_bits' method, which will be required in Amaranth 0.6",
                          DeprecationWarning, stacklevel=2)

    # The signatures and definitions of these methods are weird because they are present here for
    # documentation (and error checking above) purpose only and should not affect control flow.
    # This especially applies to `__call__`, where subclasses may call `super().__call__()` in
    # creative ways.

    def as_shape(self, *args, **kwargs):
        """as_shape()

        Convert :py:`self` to a :ref:`shape-like object <lang-shapelike>`.

        This method is called by the Amaranth language to convert :py:`self` to a concrete
        :class:`Shape`. It will usually return a :class:`Shape` object, but it may also return
        another shape-like object to delegate its functionality.

        This method must be idempotent: when called twice on the same object, the result must be
        exactly the same.

        This method may also be called by code that is not a part of the Amaranth language.

        Returns
        -------
        Any other object recognized by :meth:`Shape.cast`.

        Raises
        ------
        Exception
            When the conversion cannot be done. This exception must be propagated by callers
            (except when checking whether an object is shape-castable or not), either directly
            or as a cause of another exception.
        """
        return super().as_shape(*args, **kwargs) # :nocov:

    def const(self, *args, **kwargs):
        """const(obj)

        Convert a constant initializer :py:`obj` to its value representation.

        This method is called by the Amaranth language to convert :py:`obj`, which may be an
        arbitrary Python object, to a concrete :ref:`value-like object <lang-valuelike>`.
        The object :py:`obj` will usually be a Python literal that can conveniently represent
        a constant value whose shape is described by :py:`self`. While not constrained here,
        the result will usually be an instance of the return type of :meth:`__call__`.

        For any :py:`obj`, the following condition must hold:

        .. code::

            Shape.cast(self) == Const.cast(self.const(obj)).shape()

        This method may also be called by code that is not a part of the Amaranth language.

        Returns
        -------
        A :ref:`value-like object <lang-valuelike>` that is :ref:`constant-castable <lang-constcasting>`.

        Raises
        ------
        Exception
            When the conversion cannot be done. This exception must be propagated by callers,
            either directly or as a cause of another exception. While not constrained here,
            usually the exception class will be :exc:`TypeError` or :exc:`ValueError`.
        """
        return super().const(*args, **kwargs) # :nocov:

    def from_bits(self, raw):
        """Lift a bit pattern to a higher-level representation.

        This method is called by the Amaranth language to lift :py:`raw`, which is an :class:`int`,
        to a higher-level representation, which may be any object accepted by :meth:`const`.
        Most importantly, the simulator calls this method when the value of a shape-castable
        object is retrieved.

        For any valid bit pattern :py:`raw`, the following condition must hold:

        .. code::

            Const.cast(self.const(self.from_bits(raw))).value == raw

        While :meth:`const` will usually return an Amaranth value or a custom value-castable
        object that is convenient to use while constructing the design, this method will usually
        return a Python object that is convenient to use while simulating the design. While not
        constrained here, these objects should have the same type whenever feasible.

        This method may also be called by code that is not a part of the Amaranth language.

        Returns
        -------
        unspecified type

        Raises
        ------
        Exception
            When the bit pattern isn't valid. This exception must be propagated by callers,
            either directly or as a cause of another exception. While not constrained here,
            usually the exception class will be :exc:`ValueError`.
        """
        return raw

    def __call__(self, *args, **kwargs):
        """__call__(obj)

        Lift a :ref:`value-like object <lang-valuelike>` to a higher-level representation.

        This method is called by the Amaranth language to lift :py:`obj`, which may be any
        :ref:`value-like object <lang-valuelike>` whose shape equals :py:`Shape.cast(self)`,
        to a higher-level representation, which may be any value-like object with the same
        shape. While not constrained here, usually a :class:`ShapeCastable` implementation will
        be paired with a :class:`ValueCastable` implementation, and this method will return
        an instance of the latter.

        If :py:`obj` is not as described above, this interface does not constrain the behavior
        of this method. This may be used to implement another call-based protocol at the same
        time.

        For any compliant :py:`obj`, the following condition must hold:

        .. code::

            Value.cast(self(obj)) == Value.cast(obj)

        This method may also be called by code that is not a part of the Amaranth language.

        Returns
        -------
        A :ref:`value-like object <lang-valuelike>`.
        """
        return super().__call__(*args, **kwargs) # :nocov:

    def format(self, obj, spec):
        """Format a value.

        This method is called by the Amaranth language to implement formatting for custom
        shapes. Whenever :py:`"{obj:spec}"` is encountered by :class:`Format`, and :py:`obj`
        has a custom shape that has a :meth:`format` method, :py:`obj.shape().format(obj, "spec")`
        is called, and the format specifier is replaced with the result.

        The default :meth:`format` implementation is:

        .. code::

            def format(self, obj, spec):
                return Format(f"{{:{spec}}}", Value.cast(obj))

        Returns
        -------
        :class:`Format`
        """
        return Format(f"{{:{spec}}}", Value.cast(obj))


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
    """Abstract class representing all objects that can be cast to a :class:`Shape`.

    :py:`issubclass(cls, ShapeLike)` returns :py:`True` for:

    * :class:`Shape`;
    * :class:`ShapeCastable` and its subclasses;
    * :class:`int` and its subclasses;
    * :class:`range` and its subclasses;
    * :class:`enum.EnumMeta` and its subclasses;
    * :class:`ShapeLike` itself.

    :py:`isinstance(obj, ShapeLike)` returns :py:`True` for:

    * :class:`Shape` instances;
    * :class:`ShapeCastable` instances;
    * non-negative :class:`int` values;
    * :class:`range` instances;
    * :class:`enum.Enum` subclasses where all values are :ref:`value-like objects <lang-valuelike>`.

    This class cannot be instantiated or subclassed. It can only be used for checking types of
    objects.
    """
    def __new__(cls, *args, **kwargs):
        raise TypeError("ShapeLike is an abstract class and cannot be instantiated")


def _normalize_patterns(patterns, shape, *, src_loc_at=1):
    new_patterns = []
    for pattern in patterns:
        orig_pattern = pattern
        if isinstance(pattern, str):
            if any(bit not in "01- \t" for bit in pattern):
                raise SyntaxError(f"Pattern '{pattern}' must consist of 0, 1, and - (don't "
                                  f"care) bits, and may include whitespace")
            pattern = "".join(pattern.split()) # remove whitespace
            if len(pattern) != shape.width:
                raise SyntaxError(f"Pattern '{orig_pattern}' must have the same width as "
                                  f"match value (which is {shape.width})")
        else:
            try:
                pattern = Const.cast(pattern)
            except TypeError as e:
                raise SyntaxError(f"Pattern must be a string or a constant-castable "
                                  f"expression, not {pattern!r}") from e
            cast_pattern = Const(pattern.value, shape)
            if cast_pattern.value != pattern.value:
                warnings.warn(f"Pattern '{orig_pattern!r}' "
                              f"({pattern.shape().width}'{pattern.value:b}) is not "
                              f"representable in match value shape "
                              f"({shape!r}); comparison will never be true",
                              SyntaxWarning, stacklevel=2 + src_loc_at)
                continue
            pattern = pattern.value
        new_patterns.append(pattern)
    return tuple(new_patterns)


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
    """Abstract representation of a bit pattern computed in a circuit.

    The Amaranth language gives Python code the ability to create a circuit netlist by manipulating
    objects representing the computations within that circuit. The :class:`Value` class represents
    the bit pattern of a constant, or of a circuit input or output, or within a storage element; or
    the result of an arithmetic, logical, or bit container operation.

    Operations on this class interpret this bit pattern either as an integer, which can be signed
    or unsigned depending on the value's :meth:`shape`, or as a bit container. In either case,
    the semantics of operations that implement Python's syntax, like :py:`+` (also known as
    :meth:`__add__`), are identical to the corresponding operation on a Python :class:`int` (or on
    a Python sequence container). The bitwise inversion :py:`~` (also known as :meth:`__invert__`)
    is the sole exception to this rule.

    Data that is not conveniently representable by a single integer or a bit container can be
    represented by wrapping a :class:`Value` in a :class:`ValueCastable` subclass that provides
    domain-specific operations. It is possible to extend Amaranth in third-party code using
    value-castable objects, and the Amaranth standard library provides several built-in ones:

    * :mod:`amaranth.lib.enum` classes are a drop-in replacement for the standard Python
      :mod:`enum` classes that can be defined with an Amaranth shape;
    * :mod:`amaranth.lib.data` classes allow defining complex data structures such as structures
      and unions.

    Operations on :class:`Value` instances return another :class:`Value` instance. Unless the exact
    type and value of the result is explicitly specified below, it should be considered opaque, and
    may change without notice between Amaranth releases as long as the semantics remains the same.

    .. note::

        In each of the descriptions below, you will see a line similar to:

        **Return type:** :class:`Value`, :py:`unsigned(1)`, :ref:`assignable <lang-assignable>`

        The first part (:class:`Value`) indicates that the returned object's type is a subclass
        of :class:`Value`. The second part (:py:`unsigned(1)`) describes the shape of that value.
        The third part, if present, indicates that the value is assignable if :py:`self` is
        assignable.
    """

    @staticmethod
    def cast(obj):
        """Cast :py:`obj` to an Amaranth value.

        Many :ref:`value-like <lang-valuelike>` objects can be cast to a value:

        * a :class:`Value` instance, where the result is itself;
        * a :class:`bool` or :class:`int` instance, where the result is :py:`Const(obj)`;
        * an :class:`enum.IntEnum` instance, or a :class:`enum.Enum` instance whose members are
          all integers, where the result is a :class:`Const(obj, enum_shape)` where :py:`enum_shape`
          is a shape that can represent every member of the enumeration;
        * a :class:`ValueCastable` instance, where the result is obtained by repeatedly calling
          :meth:`obj.as_value() <ValueCastable.as_value>`.

        Raises
        ------
        TypeError
            If :py:`obj` cannot be converted to a :class:`Value`.
        RecursionError
            If :py:`obj` is a :class:`ValueCastable` object that casts to itself.
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

    @abstractmethod
    def shape(self):
        """Shape of :py:`self`.

        Returns
        -------
        :ref:`shape-like object <lang-shapelike>`
        """
        # TODO: while this is documented as returning a shape-like object, in practice we
        # guarantee that this is a concrete Shape. it's unclear whether we will ever want to
        # return a shape-catable object here, but there is not much harm in stating a relaxed
        # contract, as it can always be tightened later, but not vice-versa
        pass # :nocov:

    def as_unsigned(self):
        """Reinterpretation as an unsigned value.

        Returns
        -------
        :class:`Value`, :py:`unsigned(len(self))`, :ref:`assignable <lang-assignable>`
        """
        return Operator("u", [self])

    def as_signed(self):
        """Reinterpretation as a signed value.

        Returns
        -------
        :class:`Value`, :py:`signed(len(self))`, :ref:`assignable <lang-assignable>`

        Raises
        ------
        ValueError
            If :py:`len(self) == 0`.
        """
        if len(self) == 0:
            raise ValueError("Cannot create a 0-width signed value")
        return Operator("s", [self])

    def __bool__(self):
        """Forbidden conversion to boolean.

        Python uses this operator for its built-in semantics, e.g. :py:`if`, and requires it to
        return a :class:`bool`. Since this is not possible for Amaranth values, this operator
        always raises an exception.

        Raises
        ------
        :exc:`TypeError`
            Always.
        """
        raise TypeError("Attempted to convert Amaranth value to Python boolean")

    def bool(self):
        """Conversion to boolean.

        Returns the same value as :meth:`any`, but should be used where :py:`self` is semantically
        a number.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator("b", [self])

    def __pos__(self):
        """Unary position, :py:`+self`.

        Returns
        -------
        :class:`Value`, :py:`self.shape()`
            :py:`self`
        """
        return self

    def __neg__(self):
        """Unary negation, :py:`-self`.

        ..
            >>> C(-1).value, C(-1).shape()
            -1, signed(1)
            >>> C(-(-1), signed(1)).value # overflows
            -1

        Returns
        -------
        :class:`Value`, :py:`signed(len(self) + 1)`
        """
        return Operator("-", [self])

    @_overridable_by_reflected("__radd__")
    def __add__(self, other):
        """Addition, :py:`self + other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(max(self.width(), other.width()) + 1)`
            If both :py:`self` and :py:`other` are unsigned.
        :class:`Value`, :py:`signed(max(self.width() + 1, other.width()) + 1)`
            If :py:`self` is unsigned and :py:`other` is signed.
        :class:`Value`, :py:`signed(max(self.width(), other.width() + 1) + 1)`
            If :py:`self` is signed and :py:`other` is unsigned.
        :class:`Value`, :py:`signed(max(self.width(), other.width()) + 1)`
            If both :py:`self` and :py:`other` are unsigned.
        """
        return Operator("+", [self, other], src_loc_at=1)

    def __radd__(self, other):
        """Addition, :py:`other + self` (reflected).

        Like :meth:`__add__`, with operands swapped.
        """
        return Operator("+", [other, self])

    @_overridable_by_reflected("__rsub__")
    def __sub__(self, other):
        """Subtraction, :py:`self - other`.

        Returns
        -------
        :class:`Value`, :py:`signed(max(self.width(), other.width()) + 1)`
            If both :py:`self` and :py:`other` are unsigned.
        :class:`Value`, :py:`signed(max(self.width() + 1, other.width()) + 1)`
            If :py:`self` is unsigned and :py:`other` is signed.
        :class:`Value`, :py:`signed(max(self.width(), other.width() + 1) + 1)`
            If :py:`self` is signed and :py:`other` is unsigned.
        :class:`Value`, :py:`signed(max(self.width(), other.width()) + 1)`
            If both :py:`self` and :py:`other` are unsigned.

        Returns
        -------
        :class:`Value`
        """
        return Operator("-", [self, other], src_loc_at=1)

    def __rsub__(self, other):
        """Subtraction, :py:`other - self` (reflected).

        Like :meth:`__sub__`, with operands swapped.
        """
        return Operator("-", [other, self])

    @_overridable_by_reflected("__rmul__")
    def __mul__(self, other):
        """Multiplication, :py:`self * other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(len(self) + len(other))`
            If both :py:`self` and :py:`other` are unsigned.
        :class:`Value`, :py:`signed(len(self) + len(other))`
            If either :py:`self` or :py:`other` are signed.
        """
        return Operator("*", [self, other], src_loc_at=1)

    def __rmul__(self, other):
        """Multiplication, :py:`other * self` (reflected).

        Like :meth:`__mul__`, with operands swapped.
        """
        return Operator("*", [other, self])

    @_overridable_by_reflected("__rfloordiv__")
    def __floordiv__(self, other):
        """Flooring division, :py:`self // other`.

        If :py:`other` is zero, the result of this operation is zero.

        Returns
        -------
        :class:`Value`, :py:`unsigned(len(self))`
            If both :py:`self` and :py:`other` are unsigned.
        :class:`Value`, :py:`signed(len(self) + 1)`
            If :py:`self` is unsigned and :py:`other` is signed.
        :class:`Value`, :py:`signed(len(self))`
            If :py:`self` is signed and :py:`other` is unsigned.
        :class:`Value`, :py:`signed(len(self) + 1)`
            If both :py:`self` and :py:`other` are signed.
        """
        return Operator("//", [self, other], src_loc_at=1)

    def __rfloordiv__(self, other):
        """Flooring division, :py:`other // self` (reflected).

        If :py:`self` is zero, the result of this operation is zero.

        Like :meth:`__floordiv__`, with operands swapped.
        """
        return Operator("//", [other, self])

    @_overridable_by_reflected("__rmod__")
    def __mod__(self, other):
        """Flooring modulo or remainder, :py:`self % other`.

        If :py:`other` is zero, the result of this operation is zero.

        Returns
        -------
        :class:`Value`, :py:`other.shape()`
        """
        return Operator("%", [self, other], src_loc_at=1)

    def __rmod__(self, other):
        """Flooring modulo or remainder, :py:`other % self` (reflected).

        Like :meth:`__mod__`, with operands swapped.
        """
        return Operator("%", [other, self])

    @_overridable_by_reflected("__eq__")
    def __eq__(self, other):
        """Equality comparison, :py:`self == other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator("==", [self, other], src_loc_at=1)

    @_overridable_by_reflected("__ne__")
    def __ne__(self, other):
        """Inequality comparison, :py:`self != other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator("!=", [self, other], src_loc_at=1)

    @_overridable_by_reflected("__gt__")
    def __lt__(self, other):
        """Less than comparison, :py:`self < other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator("<", [self, other], src_loc_at=1)

    @_overridable_by_reflected("__ge__")
    def __le__(self, other):
        """Less than or equals comparison, :py:`self <= other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator("<=", [self, other], src_loc_at=1)

    @_overridable_by_reflected("__lt__")
    def __gt__(self, other):
        """Greater than comparison, :py:`self > other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator(">", [self, other], src_loc_at=1)

    @_overridable_by_reflected("__le__")
    def __ge__(self, other):
        """Greater than or equals comparison, :py:`self >= other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator(">=", [self, other], src_loc_at=1)

    def __abs__(self):
        """Absolute value, :py:`abs(self)`.

        ..
            >>> abs(C(-1)).shape()
            unsigned(1)
            >>> C(1).shape()
            unsigned(1)

        Return
        ------
        :class:`Value`, :py:`unsigned(len(self))`
        """
        if self.shape().signed:
            return Mux(self >= 0, self, -self)[:len(self)]
        else:
            return self

    def __invert__(self):
        """Bitwise NOT, :py:`~self`.

        The shape of the result is the same as the shape of :py:`self`, even for unsigned values.

        .. warning::

            In Python, :py:`~0` equals :py:`-1`. In Amaranth, :py:`~C(0)` equals :py:`C(1)`.
            This is the only case where an Amaranth operator deviates from the Python operator
            with the same name.

            This deviation is necessary because Python does not allow overriding the logical
            :py:`and`, :py:`or`, and :py:`not` operators. Amaranth uses :py:`&`, :py:`|`, and
            :py:`~` instead; if it wasn't the case that :py:`~C(0) == C(1)`, that would have
            been impossible.

        Returns
        -------
        :class:`Value`, :py:`self.shape()`
        """
        return Operator("~", [self])

    @_overridable_by_reflected("__rand__")
    def __and__(self, other):
        """Bitwise AND, :py:`self & other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(max(self.width(), other.width()))`
            If both :py:`self` and :py:`other` are unsigned.
        :class:`Value`, :py:`signed(max(self.width() + 1, other.width()))`
            If :py:`self` is unsigned and :py:`other` is signed.
        :class:`Value`, :py:`signed(max(self.width(), other.width() + 1))`
            If :py:`self` is signed and :py:`other` is unsigned.
        :class:`Value`, :py:`signed(max(self.width(), other.width()))`
            If both :py:`self` and :py:`other` are unsigned.
        """
        return Operator("&", [self, other], src_loc_at=1)

    def __rand__(self, other):
        """Bitwise AND, :py:`other & self`.

        Like :meth:`__and__`, with operands swapped.
        """
        return Operator("&", [other, self])

    def all(self):
        """Reduction AND; are all bits :py:`1`?

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator("r&", [self])

    @_overridable_by_reflected("__ror__")
    def __or__(self, other):
        """Bitwise OR, :py:`self | other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(max(self.width(), other.width()))`
            If both :py:`self` and :py:`other` are unsigned.
        :class:`Value`, :py:`signed(max(self.width() + 1, other.width()))`
            If :py:`self` is unsigned and :py:`other` is signed.
        :class:`Value`, :py:`signed(max(self.width(), other.width() + 1))`
            If :py:`self` is signed and :py:`other` is unsigned.
        :class:`Value`, :py:`signed(max(self.width(), other.width()))`
            If both :py:`self` and :py:`other` are unsigned.
        """
        return Operator("|", [self, other], src_loc_at=1)

    def __ror__(self, other):
        """Bitwise OR, :py:`other | self`.

        Like :meth:`__or__`, with operands swapped.
        """
        return Operator("|", [other, self])

    def any(self):
        """Reduction OR; is any bit :py:`1`?

        Performs the same operation as :meth:`bool`, but should be used where :py:`self` is
        semantically a bit sequence.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator("r|", [self])

    @_overridable_by_reflected("__rxor__")
    def __xor__(self, other):
        """Bitwise XOR, :py:`self ^ other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(max(self.width(), other.width()))`
            If both :py:`self` and :py:`other` are unsigned.
        :class:`Value`, :py:`signed(max(self.width() + 1, other.width()))`
            If :py:`self` is unsigned and :py:`other` is signed.
        :class:`Value`, :py:`signed(max(self.width(), other.width() + 1))`
            If :py:`self` is signed and :py:`other` is unsigned.
        :class:`Value`, :py:`signed(max(self.width(), other.width()))`
            If both :py:`self` and :py:`other` are unsigned.
        """
        return Operator("^", [self, other], src_loc_at=1)

    def __rxor__(self, other):
        """Bitwise XOR, :py:`other ^ self`.

        Like :meth:`__xor__`, with operands swapped.
        """
        return Operator("^", [other, self])

    def xor(self):
        """Reduction XOR; are an odd amount of bits :py:`1`?

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
        """
        return Operator("r^", [self])

    # TODO(amaranth-0.6): remove
    @deprecated("`a.implies(b)` is deprecated, use `~a | b` instead")
    def implies(self, conclusion):
        return ~self | conclusion

    def __check_shamt(self):
        if self.shape().signed:
            # Neither Python nor HDLs implement shifts by negative values; prohibit any shifts
            # by a signed value to make sure the shift amount can always be interpreted as
            # an unsigned value.
            raise TypeError("Shift amount must be unsigned")

    @_overridable_by_reflected("__rlshift__")
    def __lshift__(self, other):
        """Left shift by variable amount, :py:`self << other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(len(self) + 2 ** len(other) - 1)`
            If :py:`self` is unsigned.
        :class:`Value`, :py:`signed(len(self) + 2 ** len(other) - 1)`
            If :py:`self` is signed.

        Raises
        ------
        :exc:`TypeError`
            If :py:`other` is signed.
        """
        other = Value.cast(other)
        other.__check_shamt()
        return Operator("<<", [self, other], src_loc_at=1)

    def __rlshift__(self, other):
        """Left shift by variable amount, :py:`other << self`.

        Like :meth:`__lshift__`, with operands swapped.
        """
        self.__check_shamt()
        return Operator("<<", [other, self])

    def shift_left(self, amount):
        """Left shift by constant amount.

        If :py:`amount < 0`, performs the same operation as :py:`self.shift_right(-amount)`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(max(len(self) + amount, 0))`
            If :py:`self` is unsigned.
        :class:`Value`, :py:`signed(max(len(self) + amount, 1))`
            If :py:`self` is signed.
        """
        if not isinstance(amount, int):
            raise TypeError(f"Shift amount must be an integer, not {amount!r}")
        if amount < 0:
            return self.shift_right(-amount)
        if self.shape().signed:
            return Cat(Const(0, amount), self).as_signed()
        else:
            return Cat(Const(0, amount), self) # unsigned

    def rotate_left(self, amount):
        """Left rotate by constant amount.

        If :py:`amount < 0`, performs the same operation as :py:`self.rotate_right(-amount)`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(len(self))`, :ref:`assignable <lang-assignable>`
        """
        if not isinstance(amount, int):
            raise TypeError(f"Rotate amount must be an integer, not {amount!r}")
        if len(self) != 0:
            amount %= len(self)
        return Cat(self[-amount:], self[:-amount]) # meow :3

    @_overridable_by_reflected("__rrshift__")
    def __rshift__(self, other):
        """Right shift by variable amount, :py:`self >> other`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(len(self))`
            If :py:`self` is unsigned.
        :class:`Value`, :py:`signed(len(self))`
            If :py:`self` is signed.

        Raises
        ------
        :exc:`TypeError`
            If :py:`other` is signed.
        """
        other = Value.cast(other)
        other.__check_shamt()
        return Operator(">>", [self, other], src_loc_at=1)

    def __rrshift__(self, other):
        """Right shift by variable amount, :py:`other >> self`.

        Like :meth:`__rshift__`, with operands swapped.
        """
        self.__check_shamt()
        return Operator(">>", [other, self])

    def shift_right(self, amount):
        """Right shift by constant amount.

        If :py:`amount < 0`, performs the same operation as :py:`self.shift_left(-amount)`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(max(len(self) - amount, 0))`
            If :py:`self` is unsigned.
        :class:`Value`, :py:`signed(max(len(self) - amount, 1))`
            If :py:`self` is signed.
        """
        if not isinstance(amount, int):
            raise TypeError(f"Shift amount must be an integer, not {amount!r}")
        if amount < 0:
            return self.shift_left(-amount)
        if self.shape().signed:
            if amount >= len(self):
                amount = len(self) - 1
            return self[amount:].as_signed()
        else:
            return self[amount:] # unsigned

    def rotate_right(self, amount):
        """Right rotate by constant amount.

        If :py:`amount < 0`, performs the same operation as :py:`self.rotate_left(-amount)`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(len(self))`, :ref:`assignable <lang-assignable>`
        """
        if not isinstance(amount, int):
            raise TypeError(f"Rotate amount must be an integer, not {amount!r}")
        if len(self) != 0:
            amount %= len(self)
        return Cat(self[amount:], self[:amount])

    def __len__(self):
        """Bit width of :py:`self`.

        Returns
        -------
        :class:`int`
            :py:`self.shape().width`
        """
        return self.shape().width

    def __getitem__(self, key):
        """Bit slicing.

        Selects a constant-width, constant-offset part of :py:`self`. All three slicing syntaxes
        (:py:`self[i]`, :py:`self[i:j]`, and :py:`self[i:j:k]`) as well as negative indices are
        supported. Like with other Python containers, out-of-bounds indices are trimmed to
        the bounds of :py:`self`.

        To select a variable-offset part of :py:`self`, use :meth:`bit_select` or
        :meth:`word_select` instead.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`, :ref:`assignable <lang-assignable>`
            If :py:`key` is an :class:`int`.
        :class:`Value`, :py:`unsigned(j - i)`, :ref:`assignable <lang-assignable>`
            If :py:`key` is a slice :py:`i:j` where :py:`i` and :py:`j` are :class:`int`\\ s.
        :class:`Value`, :py:`unsigned(len(range(*slice(i, j, k).indices(len(self)))))`, :ref:`assignable <lang-assignable>`
            If :py:`key` is a slice :py:`i:j:k` where :py:`i`, :py:`j`, and :py:`k` are :class:`int`\\ s.
        """
        length = len(self)
        if isinstance(key, int):
            if key not in range(-length, length):
                raise IndexError(f"Index {key} is out of bounds for a {length}-bit value")
            if key < 0:
                key += length
            return Slice(self, key, key + 1, src_loc_at=1)
        elif isinstance(key, slice):
            if isinstance(key.start, Value) or isinstance(key.stop, Value):
                raise TypeError(f"Cannot slice value with a value; use Value.bit_select() or "
                                f"Value.word_select() instead")
            start, stop, step = key.indices(length)
            if step != 1:
                return Cat(self[i] for i in range(start, stop, step))
            return Slice(self, start, stop, src_loc_at=1)
        elif isinstance(key, Value):
            raise TypeError(f"Cannot index value with a value; use Value.bit_select() instead")
        else:
            raise TypeError(f"Cannot index value with {key!r}")

    def __contains__(self, other):
        """Forbidden membership test operator.

        Python requires this operator to return a :class:`bool`. Since this is not possible
        for Amaranth values, this operator always raises an exception.

        To check membership in a set of constant integer values, use :meth:`matches` instead.

        Raises
        ------
        :exc:`TypeError`
            Always.
        """
        raise TypeError("Cannot use 'in' with an Amaranth value")

    def bit_select(self, offset, width):
        """Part-select with bit granularity.

        Selects a constant width, variable offset part of :py:`self`, where parts with successive
        offsets overlap by :py:`width - 1` bits. Bits above the most significant bit of :py:`self`
        may be selected; they are equal to zero if :py:`self` is unsigned, to :py:`self[-1]` if
        :py:`self` is signed, and assigning to them does nothing.

        When :py:`offset` is a constant integer and :py:`offset + width <= len(self)`,
        this operation is equivalent to :py:`self[offset:offset + width]`.

        Parameters
        ----------
        offset: :ref:`value-like <lang-valuelike>`
            Index of the first selected bit.
        width: :class:`int`
            Amount of bits to select.

        Returns
        -------
        :class:`Value`, :py:`unsigned(width)`, :ref:`assignable <lang-assignable>`

        Raises
        ------
        :exc:`TypeError`
            If :py:`offset` is signed.
        :exc:`TypeError`
            If :py:`width` is negative.
        """
        offset = Value.cast(offset)
        if type(offset) is Const and isinstance(width, int):
            return self[offset.value:offset.value + width]
        return Part(self, offset, width, stride=1, src_loc_at=1)

    def word_select(self, offset, width):
        """Part-select with word granularity.

        Selects a constant width, variable offset part of :py:`self`, where parts with successive
        offsets are adjacent but do not overlap. Bits above the most significant bit of :py:`self`
        may be selected; they are equal to zero if :py:`self` is unsigned, to :py:`self[-1]` if
        :py:`self` is signed, and assigning to them does nothing.

        When :py:`offset` is a constant integer and :py:`width:(offset + 1) * width <= len(self)`,
        this operation is equivalent to :py:`self[offset * width:(offset + 1) * width]`.

        Parameters
        ----------
        offset: :ref:`value-like <lang-valuelike>`
            Index of the first selected word.
        width: :class:`int`
            Amount of bits to select.

        Returns
        -------
        :class:`Value`, :py:`unsigned(width)`, :ref:`assignable <lang-assignable>`

        Raises
        ------
        :exc:`TypeError`
            If :py:`offset` is signed.
        :exc:`TypeError`
            If :py:`width` is negative.
        """
        offset = Value.cast(offset)
        if type(offset) is Const and isinstance(width, int):
            return self[offset.value * width:(offset.value + 1) * width]
        return Part(self, offset, width, stride=width, src_loc_at=1)

    def replicate(self, count):
        """Replication.

        Equivalent to :py:`Cat(self for _ in range(count))`, but not assignable.

        ..
            Technically assignable right now, but we don't want to commit to that.

        Returns
        -------
        :class:`Value`, :py:`unsigned(len(self) * count)`

        Raises
        ------
        :exc:`TypeError`
            If :py:`count` is negative.
        """
        if not isinstance(count, int) or count < 0:
            raise TypeError("Replication count must be a non-negative integer, not {!r}"
                            .format(count))
        return Cat(self for _ in range(count))

    def matches(self, *patterns):
        """Pattern matching.

        Matches against a set of patterns, recognizing the same grammar as :py:`with m.Case()`.
        The pattern syntax is described in the :ref:`language guide <lang-matchop>`.

        Each of the :py:`patterns` may be a :class:`str` or a :ref:`constant-castable object
        <lang-constcasting>`.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`

        Raises
        ------
        :exc:`SyntaxError`
            If a pattern has invalid syntax.
        """
        matches = []
        for pattern in _normalize_patterns(patterns, self.shape()):
            if isinstance(pattern, str):
                mask    = int("0" + pattern.replace("0", "1").replace("-", "0"), 2)
                pattern = int("0" + pattern.replace("-", "0"), 2)
                matches.append((self & mask) == pattern)
            else:
                matches.append(self == pattern)
        if not matches:
            return Const(0)
        elif len(matches) == 1:
            return matches[0]
        else:
            return Cat(*matches).any()

    def eq(self, value, *, src_loc_at=0):
        """:ref:`Assignment <lang-assigns>`.

        Once it is placed in a domain, an assignment changes the bit pattern of :py:`self` to
        equal :py:`value`. If the bit width of :py:`value` is less than that of :py:`self`,
        it is zero-extended (for unsigned :py:`value`\\ s) or sign-extended (for signed
        :py:`value`\\ s). If the bit width of :py:`value` is greater than that of :py:`self`,
        it is truncated.

        Returns
        -------
        :class:`Statement`
        """
        return Assign(self, value, src_loc_at=src_loc_at + 1)

    #: Forbidden hashing.
    #:
    #: Python objects are :term:`python:hashable` if they provide a :py:`__hash__` method
    #: that returns an :class:`int` and an :py:`__eq__` method that returns a :class:`bool`.
    #: Amaranth values define :meth:`__eq__` to return a :class:`Value`, which precludes them
    #: from being hashable.
    #:
    #: To use a :class:`Value` as a key in a :class:`dict`, use the following pattern:
    #:
    #: .. testcode::
    #:
    #:      value = Signal()
    #:      assoc = {}
    #:      assoc[id(value)] = value, "a signal"
    #:      _, info = assoc[id(value)]
    #:      assert info == "a signal"
    __hash__ = None # type: ignore

    def __format__(self, format_desc):
        """Forbidden formatting.

        Since normal Python formatting (f-strings and ``str.format``) must immediately return
        a string, it is unsuitable for formatting Amaranth values. To format a value at simulation
        time, use :class:`Format` instead. If you really want to dump the AST at elaboration time,
        use ``repr`` instead (for instance, via ``f"{value!r}"``).
        """
        raise TypeError(f"Value {self!r} cannot be converted to string. Use `Format` for "
                        f"simulation-time formatting, or use `repr` to print the AST.")

    def _lhs_signals(self):
        raise TypeError(f"Value {self!r} cannot be used in assignments")

    @abstractmethod
    def _rhs_signals(self):
        raise NotImplementedError # :nocov:


class ValueCastable:
    """Interface class for objects that can be cast to a :class:`Value`.

    Computations in the Amaranth language are described by combining :ref:`value-like objects
    <lang-valuelike>`. Inheriting a class from :class:`ValueCastable` and implementing
    all of the methods described below adds instances of that class to the list of
    value-like objects recognized by the :meth:`Value.cast` method. This is a part of the mechanism
    for seamlessly extending the Amaranth language in third-party code.

    .. note::

        All methods and operators defined by the :class:`Value` class will implicitly cast
        a :class:`ValueCastable` object to a :class:`Value`, with the exception of arithmetic
        operators, which will prefer calling a reflected arithmetic operation on
        the :class:`ValueCastable` argument if it defines one.

        For example, if :py:`value_castable` implements :py:`__radd__`, then
        :py:`C(1) + value_castable` will perform :py:`value_castable.__radd__(C(1))`, and otherwise
        it will perform :py:`C(1).__add__(value_castable.as_value())`.
    """

    def __init__(self, *args, **kwargs):
        if type(self) is ValueCastable:
            raise TypeError("Can't instantiate abstract class ValueCastable")
        super().__init__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs):
        if cls.as_value is ValueCastable.as_value:
            raise TypeError(f"Class '{cls.__qualname__}' deriving from 'ValueCastable' must override "
                            "the 'as_value' method")
        if cls.shape is ValueCastable.shape:
            raise TypeError(f"Class '{cls.__qualname__}' deriving from 'ValueCastable' must override "
                            "the 'shape' method")

    # The signatures and definitions of these methods are weird because they are present here for
    # documentation (and error checking above) purpose only and should not affect control flow.

    def as_value(self, *args, **kwargs):
        """as_value()

        Convert :py:`self` to a :ref:`value-like object <lang-valuelike>`.

        This method is called by the Amaranth language to convert :py:`self` to a concrete
        :class:`Value`. It will usually return a :class:`Value` object, but it may also return
        another value-like object to delegate its functionality.

        This method must be idempotent: when called twice on the same object, the result must be
        exactly the same.

        This method may also be called by code that is not a part of the Amaranth language.

        Returns
        -------
        Any other object recognized by :meth:`Value.cast`.

        Raises
        ------
        Exception
            When the conversion cannot be done. This exception must be propagated by callers,
            either directly or as a cause of another exception.

            It is recommended that, in cases where this method raises an exception,
            the :meth:`shape` method also raises an exception.
        """
        return super().as_value(*args, **kwargs) # :nocov:

    def shape(self, *args, **kwargs):
        """shape()

        Compute the shape of :py:`self`.

        This method is not called by the Amaranth language itself; whenever it needs to discover
        the shape of a value-castable object, it calls :class:`self.as_value().shape()`. However,
        that method must return a :class:`Shape`, and :class:`ValueCastable` subclasses may have
        a richer representation of their shape provided by an instance of a :class:`ShapeCastable`
        subclass. This method may return such a representation.

        This method must be idempotent: when called twice on the same object, the result must be
        exactly the same.

        The following condition must hold:

        .. code::

            Shape.cast(self.shape()) == Value.cast(self).shape()

        Returns
        -------
        A :ref:`shape-like <lang-shapelike>` object.

        Raises
        ------
        Exception
            When the conversion cannot be done. This exception must be propagated by callers,
            either directly or as a cause of another exception.

            It is recommended that, in cases where this method raises an exception,
            the :meth:`as_value` method also raises an exception.
        """
        return super().shape(*args, **kwargs) # :nocov:

    # TODO(amaranth-0.6): remove
    @staticmethod
    @deprecated("`ValueCastable.lowermethod` is no longer required and will be removed in Amaranth 0.6")
    def lowermethod(func):
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
    """Abstract class representing all objects that can be cast to a :class:`Value`.

    :py:`issubclass(cls, ValueLike)` returns :py:`True` for:

    * :class:`Value`;
    * :class:`ValueCastable` and its subclasses;
    * :class:`int` and its subclasses (including :class:`bool`);
    * :class:`enum.Enum` subclasses where all values are :ref:`value-like <lang-valuelike>`;
    * :class:`ValueLike` itself.

    :py:`isinstance(obj, ValueLike)` returns the same value as
    :py:`issubclass(type(obj), ValueLike)`.

    This class cannot be instantiated or subclassed. It can only be used for checking types of
    objects.

    .. note::

        It is possible to define an enumeration with a member that is
        :ref:`value-like <lang-valuelike>` but not :ref:`constant-castable <lang-constcasting>`,
        meaning that :py:`issubclass(BadEnum, ValueLike)` returns :py:`True`, but
        :py:`Value.cast(BadEnum.MEMBER)` raises an exception.

        The :mod:`amaranth.lib.enum` module prevents such enumerations from being defined when
        the shape is specified explicitly. Using :mod:`amaranth.lib.enum` and specifying the shape
        ensures that all of your enumeration members are constant-castable and fit in the provided
        shape.
    """
    def __new__(cls, *args, **kwargs):
        raise TypeError("ValueLike is an abstract class and cannot be constructed")


class _ConstMeta(ABCMeta):
    def __call__(cls, value, shape=None, src_loc_at=0, **kwargs):
        if isinstance(shape, ShapeCastable):
            value = shape.const(value)
            cast_shape = Shape.cast(shape)
            cast_value = Const.cast(value)
            if cast_value.shape() != cast_shape:
                raise ValueError(f"Constant returned by {shape!r}.const() must have the shape that "
                                 f"it casts to, {cast_shape!r}, and not {cast_value.shape()!r}")
            return value
        return super().__call__(value, shape, **kwargs, src_loc_at=src_loc_at + 1)


@final
class Const(Value, metaclass=_ConstMeta):
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
    def cast(obj):
        """Converts ``obj`` to an Amaranth constant.

        First, ``obj`` is converted to a value using :meth:`Value.cast`. If it is a constant, it
        is returned. If it is a constant-castable expression, it is evaluated and returned.
        Otherwise, :exn:`TypeError` is raised.
        """
        obj = Value.cast(obj)
        if type(obj) is Const:
            return obj
        elif type(obj) is Concat:
            value = 0
            width = 0
            for part in obj.parts:
                const  = Const.cast(part)
                part_value = Const(const.value, unsigned(len(const))).value
                value |= part_value << width
                width += len(const)
            return Const(value, width)
        elif type(obj) is Slice:
            value = Const.cast(obj.value)
            return Const(value.value >> obj.start, unsigned(obj.stop - obj.start))
        else:
            raise TypeError(f"Value {obj!r} cannot be converted to an Amaranth constant")

    def __init__(self, value, shape=None, *, src_loc_at=0):
        # We deliberately do not call Value.__init__ here.
        if isinstance(value, Enum):
            if shape is None:
                shape = Shape.cast(type(value))
            value = value.value
        value = int(operator.index(value))
        if shape is None:
            shape = Shape(bits_for(value), signed=value < 0)
        elif isinstance(shape, int):
            shape = Shape(shape, signed=value < 0)
        else:
            if isinstance(shape, range) and value == shape.stop:
                warnings.warn(
                    message=f"Value {value!r} equals the non-inclusive end of the constant "
                            f"shape {shape!r}; this is likely an off-by-one error",
                    category=SyntaxWarning,
                    stacklevel=3)
            shape = Shape.cast(shape, src_loc_at=1 + src_loc_at)
        if shape.signed and value >> (shape.width - 1) & 1:
            value |= -(1 << shape.width)
        else:
            value &= (1 << shape.width) - 1
        self._shape = shape
        self._value = value

    def shape(self):
        return self._shape

    @property
    def value(self):
        return self._value

    # TODO(amaranth-0.6): remove
    @property
    @deprecated("`const.width` is deprecated and will be removed in Amaranth 0.6; use `len(const)` instead")
    def width(self):
        return self.shape().width

    # TODO(amaranth-0.6): remove
    @property
    @deprecated("`const.signed` is deprecated and will be removed in Amaranth 0.6; use `const.shape().signed` instead")
    def signed(self):
        return self.shape().signed

    def _rhs_signals(self):
        return SignalSet()

    def __repr__(self):
        if self._shape.signed:
            return f"(const {self._shape.width}'sd{self._value})"
        else:
            return f"(const {self._shape.width}'d{self._value})"


C = Const  # shorthand


@final
class Operator(Value):
    def __init__(self, operator, operands, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)
        self._operator = operator
        self._operands = tuple(Value.cast(op) for op in operands)

    @property
    def operator(self):
        return self._operator

    @property
    def operands(self):
        return self._operands

    def shape(self):
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
                o_shape = Shape._unify(op_shapes)
                return Shape(o_shape.width + 1, o_shape.signed)
            if self.operator == "-":
                o_shape = Shape._unify(op_shapes)
                return Shape(o_shape.width + 1, True)
            if self.operator == "*":
                return Shape(a_shape.width + b_shape.width, a_shape.signed or b_shape.signed)
            if self.operator == "//":
                return Shape(a_shape.width + b_shape.signed, a_shape.signed or b_shape.signed)
            if self.operator == "%":
                return Shape(b_shape.width, b_shape.signed)
            if self.operator in ("<", "<=", "==", "!=", ">", ">="):
                return Shape(1, False)
            if self.operator in ("&", "|", "^"):
                return Shape._unify(op_shapes)
            if self.operator == "<<":
                assert not b_shape.signed
                return Shape(a_shape.width + 2 ** b_shape.width - 1, a_shape.signed)
            if self.operator == ">>":
                assert not b_shape.signed
                return Shape(a_shape.width, a_shape.signed)
        raise NotImplementedError # :nocov:

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
    return SwitchValue(sel, ((0, val0), (None, val1)), src_loc_at=1)


@final
class Slice(Value):
    def __init__(self, value, start, stop, *, src_loc_at=0):
        try:
            start = int(operator.index(start))
        except TypeError:
            raise TypeError(f"Slice start must be an integer, not {start!r}")
        try:
            stop = int(operator.index(stop))
        except TypeError:
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
        self._value = value
        self._start = start
        self._stop  = stop

    @property
    def value(self):
        return self._value

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

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
        self._value  = value
        self._offset = offset
        self._width  = width
        self._stride = stride

    @property
    def value(self):
        return self._value

    @property
    def offset(self):
        return self._offset

    @property
    def width(self):
        return self._width

    @property
    def stride(self):
        return self._stride

    def shape(self):
        return Shape(self.width)

    def _lhs_signals(self):
        return self.value._lhs_signals()

    def _rhs_signals(self):
        return self.value._rhs_signals() | self.offset._rhs_signals()

    def __repr__(self):
        return "(part {} {} {} {})".format(repr(self.value), repr(self.offset),
                                           self.width, self.stride)


def Cat(*parts, src_loc_at=0):
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
    parts = list(flatten(parts))
    if any(isinstance(part, IOValue) for part in parts):
        return IOConcat(parts, src_loc_at=src_loc_at + 1)
    else:
        return Concat(parts, src_loc_at=src_loc_at + 1)


@final
class Concat(Value):
    def __init__(self, args, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        parts = []
        for index, arg in enumerate(args):
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
            parts.append(Value.cast(arg))
        self._parts = tuple(parts)

    @property
    def parts(self):
        return self._parts

    def shape(self):
        return Shape(sum(len(part) for part in self.parts))

    def _lhs_signals(self):
        return union((part._lhs_signals() for part in self.parts), start=SignalSet())

    def _rhs_signals(self):
        return union((part._rhs_signals() for part in self.parts), start=SignalSet())

    def __repr__(self):
        return "(cat {})".format(" ".join(map(repr, self.parts)))


@final
class SwitchValue(Value):
    def __init__(self, test, cases, *, src_loc=None, src_loc_at=0):
        if src_loc is None:
            super().__init__(src_loc_at=src_loc_at)
        else:
            self.src_loc = src_loc
        self._test = Value.cast(test)
        new_cases = []
        for patterns, value in cases:
            if patterns is not None:
                if not isinstance(patterns, tuple):
                    patterns = (patterns,)
                new_patterns = ()
                key_mask = (1 << len(self.test)) - 1
                for key in _normalize_patterns(patterns, self._test.shape()):
                    if isinstance(key, int):
                        key = to_binary(key & key_mask, len(self.test))
                    new_patterns = (*new_patterns, key)
            else:
                new_patterns = None
            new_cases.append((new_patterns, Value.cast(value)))
        self._cases = tuple(new_cases)

    @property
    def test(self):
        return self._test

    @property
    def cases(self):
        return self._cases

    def shape(self):
        return Shape._unify(value.shape() for _patterns, value in self._cases)

    def _lhs_signals(self):
        return union((value._lhs_signals() for _patterns, value in self.cases), start=SignalSet())

    def _rhs_signals(self):
        signals = union((value._rhs_signals() for _patterns, value in self.cases), start=SignalSet())
        return self.test._rhs_signals() | signals

    def __repr__(self):
        def case_repr(patterns, value):
            if patterns is None:
                return f"(default {value!r})"
            elif len(patterns) == 1:
                return f"(case {patterns[0]} {value!r})"
            else:
                return "(case ({}) {!r})".format(" ".join(patterns), value)
        case_reprs = (case_repr(patterns, value) for patterns, value in self.cases)
        return "(switch-value {!r} {})".format(self.test, " ".join(case_reprs))


class _SignalMeta(ABCMeta):
    def __call__(cls, shape=None, src_loc_at=0, **kwargs):
        signal = super().__call__(shape, **kwargs, src_loc_at=src_loc_at + 1)
        if isinstance(shape, ShapeCastable):
            return shape(signal)
        return signal


# also used for MemoryData.Init
def _get_init_value(init, shape, what="signal"):
    orig_init = init
    orig_shape = shape
    shape = Shape.cast(shape)
    if isinstance(orig_shape, ShapeCastable):
        try:
            init = Const.cast(orig_shape.const(init))
        except Exception:
            raise TypeError(f"Initial value must be a constant initializer of {orig_shape!r}")
        if init.shape() != Shape.cast(shape):
            raise ValueError(f"Constant returned by {orig_shape!r}.const() must have the shape "
                             f"that it casts to, {shape!r}, and not {init.shape()!r}")
        return init.value
    else:
        if init is None:
            init = 0
        try:
            init = Const.cast(init)
        except TypeError:
            raise TypeError("Initial value must be a constant-castable expression, not {!r}"
                            .format(orig_init))
        # Avoid false positives for all-zeroes and all-ones
        if orig_init is not None and not (isinstance(orig_init, int) and orig_init in (0, -1)):
            if init.shape().signed and not shape.signed:
                warnings.warn(
                    message=f"Initial value {orig_init!r} is signed, "
                            f"but the {what} shape is {shape!r}",
                    category=SyntaxWarning,
                    stacklevel=2)
            elif (init.shape().width > shape.width or
                  init.shape().width == shape.width and
                    shape.signed and not init.shape().signed):
                warnings.warn(
                    message=f"Initial value {orig_init!r} will be truncated to "
                            f"the {what} shape {shape!r}",
                    category=SyntaxWarning,
                    stacklevel=2)

        if isinstance(orig_shape, range) and orig_init is not None and orig_init not in orig_shape:
            if orig_init == orig_shape.stop:
                raise SyntaxError(
                    f"Initial value {orig_init!r} equals the non-inclusive end of the {what} "
                    f"shape {orig_shape!r}; this is likely an off-by-one error")
            else:
                raise SyntaxError(
                    f"Initial value {orig_init!r} is not within the {what} shape {orig_shape!r}")

        return Const(init.value, shape).value


@final
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
        name this ``Signal`` is assigned to. If the empty string, then this ``Signal`` is treated
        as private and is generally hidden from view.
    init : int or integral Enum
        Reset (synchronous) or default (combinational) value.
        When this ``Signal`` is assigned to in synchronous context and the corresponding clock
        domain is reset, the ``Signal`` assumes the given value. When this ``Signal`` is unassigned
        in combinational context (due to conditional assignments not being taken), the ``Signal``
        assumes its ``init`` value. Defaults to 0.
    reset_less : bool
        If ``True``, do not generate reset logic for this ``Signal`` in synchronous statements.
        The ``init`` value is only used as a combinational default or as the initial value.
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
    init : int
    reset_less : bool
    attrs : dict
    decoder : function
    """

    def __init__(self, shape=None, *, name=None, init=None, reset=None, reset_less=False,
                 attrs=None, decoder=None, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)

        if name is not None and not isinstance(name, str):
            raise TypeError(f"Name must be a string, not {name!r}")
        if name is None:
            self.name = tracer.get_var_name(depth=2 + src_loc_at, default="$signal")
        else:
            self.name = name

        orig_shape = shape
        if shape is None:
            shape = unsigned(1)
        else:
            shape = Shape.cast(shape, src_loc_at=1 + src_loc_at)
        self._width  = shape.width
        self._signed = shape.signed

        # TODO(amaranth-0.7): remove
        if reset is not None:
            if init is not None:
                raise ValueError("Cannot specify both `reset` and `init`")
            warnings.warn("`reset=` is deprecated, use `init=` instead",
                          DeprecationWarning, stacklevel=2)
            init = reset

        self._init = _get_init_value(init, unsigned(1) if orig_shape is None else orig_shape)
        self._reset_less = bool(reset_less)

        self._attrs = OrderedDict(() if attrs is None else attrs)

        if isinstance(orig_shape, ShapeCastable):
            self._format = orig_shape.format(orig_shape(self), "")
        elif isinstance(orig_shape, type) and issubclass(orig_shape, Enum):
            self._format = Format.Enum(self, orig_shape, name=orig_shape.__qualname__)
        else:
            self._format = Format("{}", self)

        if isinstance(decoder, type) and issubclass(decoder, Enum):
            self._format = Format.Enum(self, decoder, name=decoder.__qualname__)

        self._decoder = decoder

    def shape(self):
        return Shape(self._width, self._signed)

    # TODO(amaranth-0.6): remove
    @property
    @deprecated("`signal.width` is deprecated and will be removed in Amaranth 0.6; use `len(signal)` instead")
    def width(self):
        return self.shape().width

    # TODO(amaranth-0.6): remove
    @property
    @deprecated("`signal.signed` is deprecated and will be removed in Amaranth 0.6; use `signal.shape().signed` instead")
    def signed(self):
        return self.shape().signed

    @property
    def init(self):
        return self._init

    @property
    def reset(self):
        warnings.warn("`Signal.reset` is deprecated, use `Signal.init` instead",
                      DeprecationWarning, stacklevel=2)
        return self._init

    @property
    def reset_less(self):
        return self._reset_less

    @property
    def attrs(self):
        # Would ideally be frozendict...
        return self._attrs

    @property
    def decoder(self):
        return self._decoder

    @classmethod
    def like(cls, other, *, name=None, name_suffix=None, init=None, reset=None, src_loc_at=0, **kwargs):
        """Create Signal based on another.

        Parameters
        ----------
        other : ValueLike
            Object to base this Signal on.
        """
        cast_other = Value.cast(other)
        if name is not None:
            new_name = str(name)
        elif name_suffix is not None:
            new_name = cast_other.name + str(name_suffix)
        else:
            new_name = tracer.get_var_name(depth=2 + src_loc_at, default="$like")
        # TODO(amaranth-0.7): remove
        if reset is not None:
            if init is not None:
                raise ValueError("Cannot specify both `reset` and `init`")
            warnings.warn("`reset=` is deprecated, use `init=` instead",
                          DeprecationWarning, stacklevel=2)
            init = reset
        if isinstance(other, ValueCastable):
            shape = other.shape()
        else:
            shape = cast_other.shape()
        kw = dict(shape=shape, name=new_name)
        if isinstance(cast_other, Signal):
            if isinstance(shape, ShapeCastable):
                other_init = shape.from_bits(cast_other.init)
            else:
                other_init = cast_other.init
            kw.update(init=other_init, reset_less=cast_other.reset_less,
                      attrs=cast_other.attrs, decoder=cast_other.decoder)
        kw.update(kwargs)
        if init is not None:
            kw["init"] = init
        return cls(**kw, src_loc_at=1 + src_loc_at)

    def _lhs_signals(self):
        return SignalSet((self,))

    def _rhs_signals(self):
        return SignalSet((self,))

    def __repr__(self):
        if self.name != "":
            return f"(sig {self.name})"
        else:
            return "(sig)"


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
        self._domain = domain

    @property
    def domain(self):
        return self._domain

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
        self._domain = domain
        self._allow_reset_less = allow_reset_less

    @property
    def domain(self):
        return self._domain

    @property
    def allow_reset_less(self):
        return self._allow_reset_less

    def shape(self):
        return Shape(1)

    def _lhs_signals(self):
        return SignalSet((self,))

    def _rhs_signals(self):
        raise NotImplementedError("ResetSignal must be lowered to a concrete signal") # :nocov:

    def __repr__(self):
        return f"(rst {self.domain})"


@final
class AnyValue(Value, DUID):
    class Kind(Enum):
        AnyConst = "anyconst"
        AnySeq   = "anyseq"

    def __init__(self, kind, shape, *, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self.kind  = self.Kind(kind)
        shape = Shape.cast(shape, src_loc_at=1 + src_loc_at)
        self._width  = shape.width
        self._signed = shape.signed

    @property
    def width(self):
        return self._width

    @property
    def signed(self):
        return self._signed

    def shape(self):
        return Shape(self.width, self.signed)

    def _rhs_signals(self):
        return SignalSet()

    def __repr__(self):
        return "({} {}'{})".format(self.kind.value, self.width, "s" if self.signed else "")


def AnyConst(shape, *, src_loc_at=0):
    return AnyValue("anyconst", shape, src_loc_at=src_loc_at+1)


def AnySeq(shape, *, src_loc_at=0):
    return AnyValue("anyseq", shape, src_loc_at=src_loc_at+1)


class Array(MutableSequence):
    """Addressable multiplexer.

    An array is similar to a ``list`` that can also be indexed by ``Value``s; indexing by an integer
    or a slice works the same as for Python lists, but indexing by a ``Value`` results in a proxy.

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
        if isinstance(index, ValueCastable):
            index = Value.cast(index)
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


def _proxy_value(name):
    @functools.wraps(getattr(Value, name))
    def inner(self, *args, **kwargs):
        return getattr(Value.cast(self), name)(*args, **kwargs)
    return inner


@final
class ArrayProxy(ValueCastable):
    def __init__(self, elems, index, *, src_loc_at=0):
        self.src_loc = tracer.get_src_loc(1 + src_loc_at)
        self._elems = elems
        self._index = Value.cast(index)

    @property
    def elems(self):
        return self._elems

    @property
    def index(self):
        return self._index

    def __getattr__(self, attr):
        return ArrayProxy([getattr(elem, attr) for elem in self.elems], self.index)

    def __getitem__(self, index):
        return ArrayProxy([        elem[index] for elem in self.elems], self.index)

    def _iter_as_values(self):
        return (Value.cast(elem) for elem in self.elems)

    def shape(self):
        # The shape of the proxy must be such that it preserves the mathematical value of the array
        # elements. I.e., shape-wise, an array proxy must be identical to an equivalent mux tree.
        return Shape._unify(elem.shape() for elem in self._iter_as_values())

    def as_value(self):
        return SwitchValue(
            self._index,
            (
                (index, value)
                for index, value in enumerate(self._elems)
                if index in range(1 << len(self._index))
            ),
            src_loc=self.src_loc,
        )

    def eq(self, value, *, src_loc_at=0):
        return self.as_value().eq(value, src_loc_at=1 + src_loc_at)

    def __repr__(self):
        return "(proxy (array [{}]) {!r})".format(", ".join(map(repr, self.elems)), self.index)

    as_signed = _proxy_value("as_signed")
    as_unsigned = _proxy_value("as_unsigned")
    __len__ = _proxy_value("__len__")
    __bool__ = _proxy_value("__bool__")
    bool = _proxy_value("bool")
    __pos__ = _proxy_value("__pos__")
    __neg__ = _proxy_value("__neg__")
    __add__ = _proxy_value("__add__")
    __radd__ = _proxy_value("__radd__")
    __sub__ = _proxy_value("__sub__")
    __rsub__ = _proxy_value("__rsub__")
    __mul__ = _proxy_value("__mul__")
    __rmul__ = _proxy_value("__rmul__")
    __floordiv__ = _proxy_value("__floordiv__")
    __rfloordiv__ = _proxy_value("__rfloordiv__")
    __mod__ = _proxy_value("__mod__")
    __rmod__ = _proxy_value("__rmod__")
    __eq__ = _proxy_value("__eq__")
    __ne__ = _proxy_value("__ne__")
    __lt__ = _proxy_value("__lt__")
    __le__ = _proxy_value("__le__")
    __gt__ = _proxy_value("__gt__")
    __ge__ = _proxy_value("__ge__")
    __abs__ = _proxy_value("__abs__")
    __invert__ = _proxy_value("__invert__")
    __and__ = _proxy_value("__and__")
    __rand__ = _proxy_value("__rand__")
    __or__ = _proxy_value("__or__")
    __ror__ = _proxy_value("__ror__")
    __xor__ = _proxy_value("__xor__")
    __rxor__ = _proxy_value("__rxor__")
    any = _proxy_value("any")
    all = _proxy_value("all")
    xor = _proxy_value("xor")
    implies = _proxy_value("implies")
    __lshift__ = _proxy_value("__lshift__")
    __rlshift__ = _proxy_value("__rlshift__")
    __rshift__ = _proxy_value("__rshift__")
    __rrshift__ = _proxy_value("__rrshift__")
    shift_left = _proxy_value("shift_left")
    shift_right = _proxy_value("shift_right")
    rotate_left = _proxy_value("rotate_left")
    rotate_right = _proxy_value("rotate_right")
    __contains__ = _proxy_value("__contains__")
    bit_select = _proxy_value("bit_select")
    word_select = _proxy_value("word_select")
    replicate = _proxy_value("replicate")
    matches = _proxy_value("matches")
    __format__ = _proxy_value("__format__")


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
        return SignalSet()

    def __repr__(self):
        return "(initial)"


class _FormatLike:
    def _as_format(self) -> "Format":
        raise NotImplementedError # :nocov:

    def __add__(self, other):
        if not isinstance(other, _FormatLike):
            return NotImplemented
        return Format._from_chunks(self._as_format()._chunks + other._as_format()._chunks)

    def __format__(self, format_desc):
        """Forbidden formatting.

        ``Format`` objects cannot be directly formatted for the same reason as the ``Value``s
        they contain.
        """
        raise TypeError(f"Format object {self!r} cannot be converted to string. Use `repr` "
                        f"to print the AST, or pass it to the `Print` statement.")


@final
class Format(_FormatLike):
    def __init__(self, format, *args, **kwargs):
        fmtter = string.Formatter()
        chunks = []
        used_args = set()
        auto_arg_index = 0

        def get_field(field_name):
            nonlocal auto_arg_index
            if field_name == "":
                if auto_arg_index is None:
                    raise ValueError("cannot switch from manual field "
                                        "specification to automatic field "
                                        "numbering")
                field_name = str(auto_arg_index)
                auto_arg_index += 1
            elif field_name.isdigit():
                if auto_arg_index is not None and auto_arg_index > 0:
                    raise ValueError("cannot switch from automatic field "
                                        "numbering to manual field "
                                        "specification")
                auto_arg_index = None

            obj, arg_used = fmtter.get_field(field_name, args, kwargs)
            used_args.add(arg_used)
            return obj

        def subformat(sub_string):
            result = []
            for literal, field_name, format_spec, conversion in fmtter.parse(sub_string):
                result.append(literal)
                if field_name is not None:
                    obj = get_field(field_name)
                    obj = fmtter.convert_field(obj, conversion)
                    format_spec = subformat(format_spec)
                    result.append(fmtter.format_field(obj, format_spec))
            return "".join(result)

        for literal, field_name, format_spec, conversion in fmtter.parse(format):
            chunks.append(literal)
            if field_name is not None:
                obj = get_field(field_name)
                if conversion == "v":
                    obj = Value.cast(obj)
                else:
                    obj = fmtter.convert_field(obj, conversion)
                format_spec = subformat(format_spec)
                if isinstance(obj, Value):
                    # Perform validation.
                    self._parse_format_spec(format_spec, obj.shape())
                    chunks.append((obj, format_spec))
                elif isinstance(obj, ValueCastable):
                    shape = obj.shape()
                    if isinstance(shape, ShapeCastable):
                        fmt = shape.format(obj, format_spec)
                        if not isinstance(fmt, _FormatLike):
                            raise TypeError(f"`ShapeCastable.format` must return a 'Format' instance, not {fmt!r}")
                        chunks += fmt._as_format()._chunks
                    else:
                        obj = Value.cast(obj)
                        self._parse_format_spec(format_spec, obj.shape())
                        chunks.append((obj, format_spec))
                elif isinstance(obj, _FormatLike):
                    if format_spec != "":
                        raise ValueError(f"Format specifiers ({format_spec!r}) cannot be used for 'Format' objects")
                    chunks += obj._as_format()._chunks
                else:
                    chunks.append(fmtter.format_field(obj, format_spec))

        for i in range(len(args)):
            if i not in used_args:
                raise ValueError(f"format positional argument {i} was not used")
        for name in kwargs:
            if name not in used_args:
                raise ValueError(f"format keyword argument {name!r} was not used")

        self._chunks = self._clean_chunks(chunks)

    def _as_format(self):
        return self

    @classmethod
    def _from_chunks(cls, chunks):
        res = object.__new__(cls)
        res._chunks = cls._clean_chunks(chunks)
        return res

    @classmethod
    def _clean_chunks(cls, chunks):
        res = []
        for chunk in chunks:
            if isinstance(chunk, str) and chunk == "":
                continue
            if isinstance(chunk, str) and res and isinstance(res[-1], str):
                res[-1] += chunk
            else:
                res.append(chunk)
        return tuple(res)

    def _to_format_string(self):
        format_string = []
        args = []
        for chunk in self._chunks:
            if isinstance(chunk, str):
                format_string.append(chunk.replace("{", "{{").replace("}", "}}"))
            else:
                arg, format_spec = chunk
                args.append(arg)
                if format_spec:
                    format_string.append(f"{{:{format_spec}}}")
                else:
                    format_string.append("{}")
        return ("".join(format_string), tuple(args))

    def __repr__(self):
        format_string, args = self._to_format_string()
        args = "".join(f" {arg!r}" for arg in args)
        return f"(format {format_string!r}{args})"

    _FORMAT_SPEC_PATTERN = re.compile(r"""
        (?:
            (?P<fill>.)?
            (?P<align>[<>=^])
        )?
        (?P<sign>[-+ ])?
        (?P<show_base>[#]?)
        (?P<width_zero>[0]?)
        (?P<width>[1-9][0-9]*)?
        (?P<grouping>[_,])?
        (?P<type>[bodxXcsn])?
    """, re.VERBOSE)

    @staticmethod
    def _parse_format_spec(spec: str, shape: Shape):
        match = Format._FORMAT_SPEC_PATTERN.fullmatch(spec)
        if not match:
            raise ValueError(f"Invalid format specifier {spec!r}")
        if match["align"] == "^":
            raise ValueError(f"Alignment {match['align']!r} is not supported")
        if match["grouping"] == ",":
            raise ValueError(f"Grouping option {match['grouping']!r} is not supported")
        if match["type"] == "n":
            raise ValueError(f"Presentation type {match['type']!r} is not supported")
        if match["type"] in ("c", "s"):
            if shape.signed:
                raise ValueError(f"Cannot print signed value with format specifier {match['type']!r}")
            if match["align"] == "=":
                raise ValueError(f"Alignment {match['align']!r} is not allowed with format specifier {match['type']!r}")
            if match["show_base"]:
                raise ValueError(f"Alternate form is not allowed with format specifier {match['type']!r}")
            if match["width_zero"] != "":
                raise ValueError(f"Zero fill is not allowed with format specifier {match['type']!r}")
            if match["sign"] is not None:
                raise ValueError(f"Sign is not allowed with format specifier {match['type']!r}")
            if match["grouping"] is not None:
                raise ValueError(f"Cannot specify {match['grouping']!r} with format specifier {match['type']!r}")
        if match["type"] == "s" and shape.width % 8 != 0:
            raise ValueError(f"Value width must be divisible by 8 with format specifier {match['type']!r}")
        fill = match["fill"]
        align = match["align"]
        if match["width_zero"] and align is None:
            fill = "0"
            align = "="
        return {
            # Single character or None.
            "fill": fill,
            # '<', '>', '=', or None. Cannot be '=' for types 'c' and 's'.
            "align": align,
            # '-', '+', ' ', or None. Always None for types 'c' and 's'.
            "sign": match["sign"],
            # A bool. Always False for types 'c' and 's'.
            "show_base": match["show_base"] == "#",
            # An int.
            "width": int(match["width"]) if match["width"] is not None else 0,
            # '_' or None. Always None for types 'c' and 's'.
            "grouping": match["grouping"],
            # 'b', 'o', 'd', 'x', 'X', 'c', 's', or None.
            "type": match["type"],
        }

    def _rhs_signals(self):
        res = SignalSet()
        for chunk in self._chunks:
            if not isinstance(chunk, str):
                obj, format_spec = chunk
                res |= obj._rhs_signals()
        return res


    class Enum(_FormatLike):
        def __init__(self, value, /, variants, *, name=None):
            self._value = Value.cast(value)
            if name is not None and not isinstance(name, str):
                raise TypeError(f"Enum name must be a string or None, not {name!r}")
            self._name = name
            if isinstance(variants, EnumMeta):
                self._variants = {Const.cast(member.value).value: member.name for member in variants}
            else:
                self._variants = dict(variants)
            for val, name in self._variants.items():
                if not isinstance(val, int):
                    raise TypeError(f"Variant values must be integers, not {val!r}")
                if not isinstance(name, str):
                    raise TypeError(f"Variant names must be strings, not {name!r}")

        def _as_format(self):
            def str_val(name):
                name = name.encode()
                return Const(int.from_bytes(name, "little"), len(name) * 8)
            value = SwitchValue(self._value, [
                (val, str_val(name))
                for val, name in self._variants.items()
            ] + [(None, str_val("[unknown]"))])
            return Format("{:s}", value)

        def __repr__(self):
            variants = "".join(
                f" ({val!r} {name!r})"
                for val, name in self._variants.items()
            )
            name = "-" if self._name is None else repr(self._name)
            return f"(format-enum {self._value!r} {name}{variants})"


    class Struct(_FormatLike):
        def __init__(self, value, /, fields):
            self._value = Value.cast(value)
            self._fields: dict[str, _FormatLike] = dict(fields)
            for name, format in self._fields.items():
                if not isinstance(name, str):
                    raise TypeError(f"Field names must be strings, not {name!r}")
                if not isinstance(format, _FormatLike):
                    raise TypeError(f"Field format must be a 'Format', not {format!r}")

        def _as_format(self):
            chunks = ["{"]
            for idx, (name, field) in enumerate(self._fields.items()):
                if idx != 0:
                    chunks.append(", ")
                chunks.append(f"{name}=")
                chunks += field._as_format()._chunks
            chunks.append("}")
            return Format._from_chunks(chunks)

        def __repr__(self):
            fields = "".join(
                f" ({name!r} {field!r})"
                for name, field in self._fields.items()
            )
            return f"(format-struct {self._value!r}{fields})"


    class Array(_FormatLike):
        def __init__(self, value, /, fields):
            self._value = Value.cast(value)
            self._fields = list(fields)
            for format in self._fields:
                if not isinstance(format, (Format, Format.Enum, Format.Struct, Format.Array)):
                    raise TypeError(f"Field format must be a 'Format', not {format!r}")

        def _as_format(self):
            chunks = ["["]
            for idx, field in enumerate(self._fields):
                if idx != 0:
                    chunks.append(", ")
                chunks += field._as_format()._chunks
            chunks.append("]")
            return Format._from_chunks(chunks)

        def __repr__(self):
            fields = "".join(
                f" {field!r}"
                for field in self._fields
            )
            return f"(format-array {self._value!r}{fields})"


class _StatementList(list):
    def __repr__(self):
        return "({})".format(" ".join(map(repr, self)))

    def _lhs_signals(self):
        return union((s._lhs_signals() for s in self), start=SignalSet())

    def _rhs_signals(self):
        return union((s._rhs_signals() for s in self), start=SignalSet())


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
        self._lhs = Value.cast(lhs)
        self._rhs = Value.cast(rhs)

    @property
    def lhs(self):
        return self._lhs

    @property
    def rhs(self):
        return self._rhs

    def _lhs_signals(self):
        return self.lhs._lhs_signals()

    def _rhs_signals(self):
        return self.lhs._rhs_signals() | self.rhs._rhs_signals()

    def __repr__(self):
        return f"(eq {self.lhs!r} {self.rhs!r})"


class UnusedPrint(UnusedMustUse):
    pass


@final
class Print(Statement, MustUse):
    _MustUse__warning = UnusedPrint

    def __init__(self, *args, sep=" ", end="\n", src_loc_at=0):
        self._MustUse__silence = True
        super().__init__(src_loc_at=src_loc_at)
        if not isinstance(sep, str):
            raise TypeError(f"'sep' must be a string, not {sep!r}")
        if not isinstance(end, str):
            raise TypeError(f"'end' must be a string, not {end!r}")
        chunks = []
        first = True
        for arg in args:
            if not first and sep != "":
                chunks.append(sep)
            first = False
            chunks += Format("{}", arg)._chunks
        if end != "":
            chunks.append(end)
        self._message = Format._from_chunks(chunks)
        del self._MustUse__silence

    @property
    def message(self):
        return self._message

    def _lhs_signals(self):
        return set()

    def _rhs_signals(self):
        return self.message._rhs_signals()

    def __repr__(self):
        return f"(print {self.message!r})"


class UnusedProperty(UnusedMustUse):
    pass


@final
class Property(Statement, MustUse):
    _MustUse__warning = UnusedProperty

    class Kind(Enum):
        Assert = "assert"
        Assume = "assume"
        Cover  = "cover"

    def __init__(self, kind, test, message=None, *, src_loc_at=0):
        self._MustUse__silence = True
        super().__init__(src_loc_at=src_loc_at)
        self._kind   = self.Kind(kind)
        self._test   = Value.cast(test)
        if isinstance(message, str):
            message = Format._from_chunks([message])
        if message is not None:
            if not isinstance(message, _FormatLike):
                raise TypeError(f"Property message must be None, str, or Format, not {message!r}")
            message = message._as_format()
        self._message = message
        del self._MustUse__silence

    @property
    def kind(self):
        return self._kind

    @property
    def test(self):
        return self._test

    @property
    def message(self):
        return self._message

    def _lhs_signals(self):
        return set()

    def _rhs_signals(self):
        if self.message is not None:
            return self.message._rhs_signals() | self.test._rhs_signals()
        return self.test._rhs_signals()

    def __repr__(self):
        if self.message is not None:
            return f"({self.kind.value} {self.test!r} {self.message!r})"
        return f"({self.kind.value} {self.test!r})"


def Assert(test, message=None, *, src_loc_at=0):
    return Property("assert", test, message, src_loc_at=src_loc_at+1)


def Assume(test, message=None, *, src_loc_at=0):
    return Property("assume", test, message, src_loc_at=src_loc_at+1)


def Cover(test, message=None, *, src_loc_at=0):
    return Property("cover", test, message, src_loc_at=src_loc_at+1)


class _LateBoundStatement(Statement):
    def resolve(self):
        raise NotImplementedError # :nocov:


@final
class Switch(Statement):
    def __init__(self, test, cases, *, src_loc=None, src_loc_at=0):
        if src_loc is None:
            super().__init__(src_loc_at=src_loc_at)
        else:
            # Switch is a bit special in terms of location tracking because it is usually created
            # long after the control has left the statement that directly caused its creation.
            self.src_loc = src_loc

        self._test  = Value.cast(test)
        new_cases = []
        for patterns, stmts, case_src_loc in cases:
            if patterns is not None:
                # Map: key -> (key,); (key...) -> (key...)
                if not isinstance(patterns, tuple):
                    patterns = (patterns,)
                # Map: 2 -> "0010"; "0010" -> "0010"
                new_patterns = ()
                key_mask = (1 << len(self.test)) - 1
                for key in _normalize_patterns(patterns, self._test.shape()):
                    if isinstance(key, int):
                        key = to_binary(key & key_mask, len(self.test))
                    new_patterns = (*new_patterns, key)
            else:
                new_patterns = None
            new_cases.append((new_patterns, Statement.cast(stmts), case_src_loc))
        self._cases = tuple(new_cases)

    @property
    def test(self):
        return self._test

    @property
    def cases(self):
        return self._cases

    def _lhs_signals(self):
        return union((stmts._lhs_signals() for _patterns, stmts, _src_loc in self.cases), start=SignalSet())

    def _rhs_signals(self):
        signals = union((stmts._rhs_signals() for _patterns, stmts, _src_loc in self.cases), start=SignalSet())
        return self.test._rhs_signals() | signals

    def __repr__(self):
        def case_repr(patterns, stmts):
            stmts_repr = " ".join(map(repr, stmts))
            if patterns is None:
                return f"(default {stmts_repr})"
            elif len(patterns) == 1:
                return f"(case {patterns[0]} {stmts_repr})"
            else:
                return "(case ({}) {})".format(" ".join(patterns), stmts_repr)
        case_reprs = (case_repr(patterns, stmts) for patterns, stmts, _src_loc in self.cases)
        return "(switch {!r} {})".format(self.test, " ".join(case_reprs))


class IOValue(metaclass=ABCMeta):
    @staticmethod
    def cast(obj):
        if isinstance(obj, IOValue):
            return obj
        elif isinstance(obj, Value) and len(obj) == 0:
            return IOConcat(())
        else:
            raise TypeError(f"Object {obj!r} cannot be converted to an IO value")

    def __init__(self, *, src_loc_at=0):
        self.src_loc = tracer.get_src_loc(1 + src_loc_at)

    @property
    @abstractmethod
    def metadata(self):
        raise NotImplementedError # :nocov:

    def __getitem__(self, key):
        n = len(self)
        if isinstance(key, int):
            if key not in range(-n, n):
                raise IndexError(f"Index {key} is out of bounds for a {n}-bit IO value")
            if key < 0:
                key += n
            return IOSlice(self, key, key + 1, src_loc_at=1)
        elif isinstance(key, slice):
            start, stop, step = key.indices(n)
            if step != 1:
                return IOConcat((self[i] for i in range(start, stop, step)), src_loc_at=1)
            return IOSlice(self, start, stop, src_loc_at=1)
        else:
            raise TypeError(f"Cannot index IO value with {key!r}")


@final
class IOPort(IOValue):
    def __init__(self, width, *, name=None, attrs=None, metadata=None, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)

        if name is not None and not isinstance(name, str):
            raise TypeError(f"Name must be a string, not {name!r}")
        self.name = name or tracer.get_var_name(depth=2 + src_loc_at)

        self._width = operator.index(width)
        self._attrs = dict(() if attrs is None else attrs)
        self._metadata = (None,) * self._width if metadata is None else tuple(metadata)
        if len(self._metadata) != self._width:
            raise ValueError(f"Metadata length ({len(self._metadata)}) doesn't match port width ({self._width})")

    def __len__(self):
        return self._width

    @property
    def width(self):
        return self._width

    @property
    def attrs(self):
        return self._attrs

    @property
    def metadata(self):
        return self._metadata

    def __repr__(self):
        return f"(io-port {self.name})"


@final
class IOConcat(IOValue):
    def __init__(self, parts, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self._parts = tuple(IOValue.cast(part) for part in parts)

    @property
    def parts(self):
        return self._parts

    def __len__(self):
        return sum(len(part) for part in self.parts)

    @property
    def metadata(self):
        return tuple(obj for part in self._parts for obj in part.metadata)

    def __repr__(self):
        return "(io-cat {})".format(" ".join(map(repr, self.parts)))


@final
class IOSlice(IOValue):
    def __init__(self, value, start, stop, *, src_loc_at=0):
        try:
            start = int(operator.index(start))
        except TypeError:
            raise TypeError(f"Slice start must be an integer, not {start!r}")
        try:
            stop = int(operator.index(stop))
        except TypeError:
            raise TypeError(f"Slice stop must be an integer, not {stop!r}")

        value = IOValue.cast(value)
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
        self._value = value
        self._start = start
        self._stop  = stop

    @property
    def value(self):
        return self._value

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    def __len__(self):
        return self.stop - self.start

    @property
    def metadata(self):
        return self._value.metadata[self.start:self.stop]

    def __repr__(self):
        return f"(io-slice {self.value!r} {self.start}:{self.stop})"


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
        return "{}.{}([{}])".format(type(self).__module__, type(self).__qualname__,
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
        return "{}.{}({})".format(type(self).__module__, type(self).__qualname__,
                                  ", ".join(repr(x) for x in self))


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
        return f"<{type(self).__qualname__} {self.signal!r}>"


class SignalDict(_MappedKeyDict):
    _map_key   = SignalKey
    _unmap_key = lambda self, key: key.signal


class SignalSet(_MappedKeySet):
    _map_key   = SignalKey
    _unmap_key = lambda self, key: key.signal
