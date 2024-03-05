from abc import ABCMeta, abstractmethod
import warnings
import functools
import operator
from collections import OrderedDict
from collections.abc import Iterable, MutableMapping, MutableSet, MutableSequence
from enum import Enum, EnumMeta
from itertools import chain

from ._repr import *
from .. import tracer
from ..utils import *
from .._utils import *
from .._unused import *


__all__ = [
    "Shape", "signed", "unsigned", "ShapeCastable", "ShapeLike",
    "Value", "Const", "C", "AnyConst", "AnySeq", "Operator", "Mux", "Part", "Slice", "Cat",
    "Array", "ArrayProxy",
    "Signal", "ClockSignal", "ResetSignal",
    "ValueCastable", "ValueLike",
    "Initial",
    "Statement", "Switch",
    "Property", "Assign", "Assert", "Assume", "Cover",
    "SignalKey", "SignalDict", "SignalSet",
]


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
            raise TypeError(f"Class '{cls.__name__}' deriving from 'ShapeCastable' must override "
                            f"the 'as_shape' method")
        if cls.const is ShapeCastable.const:
            raise TypeError(f"Class '{cls.__name__}' deriving from 'ShapeCastable' must override "
                            f"the 'const' method")
        if cls.__call__ is ShapeCastable.__call__:
            raise TypeError(f"Class '{cls.__name__}' deriving from 'ShapeCastable' must override "
                            f"the '__call__' method")

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

    # TODO: write an RFC for turning this into a proper interface method
    def _value_repr(self, value):
        return (Repr(FormatInt(), value),)


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
      :class:`enum` classes that can be defined with an Amaranth shape;
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

        Performs the same operation as :meth:`any`.

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

        .. important::

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

    def implies(self, conclusion):
        # TODO: should we document or just deprecate this?
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

        If :py:`amount < 0`, performs the same operation as :py:`self.left_right(-amount)`.

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

        If :py:`amount < 0`, performs the same operation as :py:`self.rotate_right(-amount)`.

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

        .. todo::

            Describe this operation.
        """
        n = len(self)
        if isinstance(key, int):
            if key not in range(-n, n):
                raise IndexError(f"Index {key} is out of bounds for a {n}-bit value")
            if key < 0:
                key += n
            return Slice(self, key, key + 1, src_loc_at=1)
        elif isinstance(key, slice):
            if isinstance(key.start, Value) or isinstance(key.stop, Value):
                raise TypeError(f"Cannot slice value with a value; use Value.bit_select() or "
                                f"Value.word_select() instead")
            start, stop, step = key.indices(n)
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

        .. todo::

            Describe the pattern language in detail.

        Returns
        -------
        :class:`Value`, :py:`unsigned(1)`
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
            raise TypeError(f"Class '{cls.__name__}' deriving from 'ValueCastable' must override "
                            "the 'as_value' method")
        if cls.shape is ValueCastable.shape:
            raise TypeError(f"Class '{cls.__name__}' deriving from 'ValueCastable' must override "
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
            return shape.const(value)
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
        elif type(obj) is Cat:
            value = 0
            width = 0
            for part in obj.parts:
                const  = Const.cast(part)
                part_value = Const(const.value, unsigned(const.width)).value
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
        self._width  = shape.width
        self._signed = shape.signed
        if shape.signed and value >> (shape.width - 1) & 1:
            value |= -(1 << shape.width)
        else:
            value &= (1 << shape.width) - 1
        self._value = value

    @property
    def value(self):
        return self._value

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
        return "(const {}'{}d{})".format(self.width, "s" if self.signed else "", self.value)


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
        elif len(op_shapes) == 3:
            if self.operator == "m":
                s_shape, a_shape, b_shape = op_shapes
                return Shape._unify((a_shape, b_shape))
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
        self._value = value
        self._start = int(operator.index(start))
        self._stop  = int(operator.index(stop))

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
        parts = []
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


class _SignalMeta(ABCMeta):
    def __call__(cls, shape=None, src_loc_at=0, **kwargs):
        signal = super().__call__(shape, **kwargs, src_loc_at=src_loc_at + 1)
        if isinstance(shape, ShapeCastable):
            return shape(signal)
        return signal


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
        name this ``Signal`` is assigned to.
    init : int or integral Enum
        Reset (synchronous) or default (combinatorial) value.
        When this ``Signal`` is assigned to in synchronous context and the corresponding clock
        domain is reset, the ``Signal`` assumes the given value. When this ``Signal`` is unassigned
        in combinatorial context (due to conditional assignments not being taken), the ``Signal``
        assumes its ``init`` value. Defaults to 0.
    reset_less : bool
        If ``True``, do not generate reset logic for this ``Signal`` in synchronous statements.
        The ``init`` value is only used as a combinatorial default or as the initial value.
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
        self.name = name or tracer.get_var_name(depth=2 + src_loc_at, default="$signal")

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

        orig_init = init
        if isinstance(orig_shape, ShapeCastable):
            try:
                init = Const.cast(orig_shape.const(init))
            except Exception:
                raise TypeError("Initial value must be a constant initializer of {!r}"
                                .format(orig_shape))
            if init.shape() != Shape.cast(orig_shape):
                raise ValueError("Constant returned by {!r}.const() must have the shape that "
                                 "it casts to, {!r}, and not {!r}"
                                 .format(orig_shape, Shape.cast(orig_shape),
                                         init.shape()))
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
            if init.shape().signed and not self.signed:
                warnings.warn(
                    message="Initial value {!r} is signed, but the signal shape is {!r}"
                            .format(orig_init, shape),
                    category=SyntaxWarning,
                    stacklevel=2)
            elif (init.shape().width > self.width or
                  init.shape().width == self.width and
                    self.signed and not init.shape().signed):
                warnings.warn(
                    message="Initial value {!r} will be truncated to the signal shape {!r}"
                            .format(orig_init, shape),
                    category=SyntaxWarning,
                    stacklevel=2)
        self._init = init.value
        self._reset_less = bool(reset_less)

        if isinstance(orig_shape, range) and orig_init is not None and orig_init not in orig_shape:
            if orig_init == orig_shape.stop:
                raise SyntaxError(
                    f"Initial value {orig_init!r} equals the non-inclusive end of the signal "
                    f"shape {orig_shape!r}; this is likely an off-by-one error")
            else:
                raise SyntaxError(
                    f"Initial value {orig_init!r} is not within the signal shape {orig_shape!r}")

        self._attrs = OrderedDict(() if attrs is None else attrs)

        if decoder is not None:
            # The value representation is specified explicitly. Since we do not expose `hdl._repr`,
            # this is the only way to add a custom filter to the signal right now. The setter sets
            # `self._value_repr` as well as the compatibility `self.decoder`.
            pass
        else:
            # If it's an enum, expose it via `self.decoder` for compatibility, whether it's a Python
            # enum or an Amaranth enum. This also sets the value representation, even for custom
            # shape-castables that implement their own `_value_repr`.
            if isinstance(orig_shape, type) and issubclass(orig_shape, Enum):
                decoder = orig_shape
            else:
                decoder = None
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

    @property
    def width(self):
        return self._width

    @property
    def signed(self):
        return self._signed

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
        other : Value
            Object to base this Signal on.
        """
        if name is not None:
            new_name = str(name)
        elif name_suffix is not None:
            new_name = other.name + str(name_suffix)
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
            shape = Value.cast(other).shape()
        kw = dict(shape=shape, name=new_name)
        if isinstance(other, Signal):
            kw.update(init=other.init, reset_less=other.reset_less,
                      attrs=other.attrs, decoder=other.decoder)
        kw.update(kwargs)
        if init is not None:
            kw["init"] = init
        return cls(**kw, src_loc_at=1 + src_loc_at)

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


@final
class ArrayProxy(Value):
    def __init__(self, elems, index, *, src_loc_at=0):
        super().__init__(src_loc_at=1 + src_loc_at)
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


class UnusedProperty(UnusedMustUse):
    pass


@final
class Property(Statement, MustUse):
    _MustUse__warning = UnusedProperty

    class Kind(Enum):
        Assert = "assert"
        Assume = "assume"
        Cover  = "cover"

    def __init__(self, kind, test, *, name=None, src_loc_at=0):
        super().__init__(src_loc_at=src_loc_at)
        self._kind   = self.Kind(kind)
        self._test   = Value.cast(test)
        self._name   = name
        if not isinstance(self.name, str) and self.name is not None:
            raise TypeError("Property name must be a string or None, not {!r}"
                            .format(self.name))

    @property
    def kind(self):
        return self._kind

    @property
    def test(self):
        return self._test

    @property
    def name(self):
        return self._name

    def _lhs_signals(self):
        return set()

    def _rhs_signals(self):
        return self.test._rhs_signals()

    def __repr__(self):
        if self.name is not None:
            return f"({self.name}: {self.kind.value} {self.test!r})"
        return f"({self.kind.value} {self.test!r})"


def Assert(test, *, name=None, src_loc_at=0):
    return Property("assert", test, name=name, src_loc_at=src_loc_at+1)


def Assume(test, *, name=None, src_loc_at=0):
    return Property("assume", test, name=name, src_loc_at=src_loc_at+1)


def Cover(test, *, name=None, src_loc_at=0):
    return Property("cover", test, name=name, src_loc_at=src_loc_at+1)


class _LateBoundStatement(Statement):
    def resolve(self):
        raise NotImplementedError # :nocov:


@final
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

        self._test  = Value.cast(test)
        self._cases = OrderedDict()
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
                    # fixup for 0-width test
                    if key_mask == 0:
                        key = ""
                elif isinstance(key, Enum):
                    key = format(key.value & key_mask, "b").rjust(len(self.test), "0")
                    # fixup for 0-width test
                    if key_mask == 0:
                        key = ""
                else:
                    raise TypeError("Object {!r} cannot be used as a switch key"
                                    .format(key))
                assert len(key) == len(self.test)
                new_keys = (*new_keys, key)
            if not isinstance(stmts, Iterable):
                stmts = [stmts]
            self._cases[new_keys] = Statement.cast(stmts)
            if orig_keys in case_src_locs:
                self.case_src_locs[new_keys] = case_src_locs[orig_keys]

    @property
    def test(self):
        return self._test

    @property
    def cases(self):
        return self._cases

    def _lhs_signals(self):
        return union((s._lhs_signals() for s in self.cases.values()), start=SignalSet())

    def _rhs_signals(self):
        signals = union((s._rhs_signals() for s in self.cases.values()), start=SignalSet())
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
