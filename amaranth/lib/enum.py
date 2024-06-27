import enum as py_enum
import warnings
import operator

from ..hdl import Value, ValueCastable, Shape, ShapeCastable, Const, SyntaxWarning, Format


__all__ = py_enum.__all__ + ["EnumView", "FlagView"]


for _member in py_enum.__all__:
    globals()[_member] = getattr(py_enum, _member)
del _member


class EnumType(ShapeCastable, py_enum.EnumMeta):
    """Subclass of the standard :class:`enum.EnumType` that implements the :class:`ShapeCastable`
    protocol.

    This metaclass provides the :meth:`as_shape` method, making its instances
    :ref:`shape-like <lang-shapelike>`, and accepts a ``shape=`` keyword argument
    to specify a shape explicitly. Other than this, it acts the same as the standard
    :class:`enum.EnumType` class; if the ``shape=`` argument is not specified and
    :meth:`as_shape` is never called, it places no restrictions on the enumeration class
    or the values of its members.

    When a :ref:`value-like <lang-valuelike>` is cast to an enum type that is an instance
    of this metaclass, it can be automatically wrapped in a view class. A custom view class
    can be specified by passing the ``view_class=`` keyword argument when creating the enum class.
    """

    # TODO: remove this shim once py3.8 support is dropped
    @classmethod
    def __prepare__(metacls, name, bases, shape=None, view_class=None, **kwargs):
        return super().__prepare__(name, bases, **kwargs)

    def __new__(metacls, name, bases, namespace, shape=None, view_class=None, **kwargs):
        if shape is not None:
            shape = Shape.cast(shape)
        # Prepare enumeration members for instantiation. This logic is unfortunately very
        # convoluted because it supports two very different code paths that need to share
        # the emitted warnings.
        # TODO(py3.13): can use `namespace.member_names` property.
        for member_name in namespace._member_names:
            member_value = namespace[member_name]
            # If a shape is specified ("Amaranth mode" of amaranth.lib.enum.Enum), then every
            # member value must be a constant-castable expression. Otherwise ("Python mode" of
            # amaranth.lib.enum.Enum) any value goes, since all enumerations accepted by
            # the built-in Enum class must be also accepted by amaranth.lib.enum.Enum.
            try:
                member_const = Const.cast(member_value)
            except TypeError as e:
                if shape is not None:
                    raise TypeError("Value {!r} of enumeration member {!r} must be "
                                    "a constant-castable expression"
                                    .format(member_value, member_name)) from e
                else:
                    continue
            if isinstance(member_value, Value):
                # The member value is an Amaranth value that is also constant-castable.
                # It cannot be used in an enumeration as-is (since it doesn't return a boolean
                # from comparison operators, and this is required by py_enum).
                # Replace the member value with the integer value of the constant, per RFC 4.
                # Note that we do this even if no shape is provided (and this class is emulating
                # a Python enumeration); this is OK because we only need to accept everything that
                # the built-in class accepts to be a drop-in replacement, but the built-in class
                # does not accept Amaranth values.
                # We use dict.__setitem__ since namespace is a py_enum._EnumDict that overrides
                # __setitem__ to check if the name has been already used.
                dict.__setitem__(namespace, member_name, member_const.value)
            # If a shape was specified, check whether the member value is compatible with it.
            if shape is not None:
                member_shape = member_const.shape()
                if member_shape.signed and not shape.signed:
                    warnings.warn(
                        message="Value {!r} of enumeration member {!r} is signed, but "
                                "the enumeration shape is {!r}" # the repr will be `unsigned(X)`
                                .format(member_value, member_name, shape),
                        category=SyntaxWarning,
                        stacklevel=2)
                elif (member_shape.width > shape.width or
                      member_shape.width == shape.width and
                        shape.signed and not member_shape.signed):
                    warnings.warn(
                        message="Value {!r} of enumeration member {!r} will be truncated to "
                                "the enumeration shape {!r}"
                                .format(member_value, member_name, shape),
                        category=SyntaxWarning,
                        stacklevel=2)
        # Actually instantiate the enumeration class.
        if shape is not None:
            cls = py_enum.EnumMeta.__new__(metacls, name, bases, namespace, **kwargs)
            # Shape is provided explicitly. Set the `_amaranth_shape_` attribute, and check that
            # the values of every member can be cast to the provided shape without truncation.
            cls._amaranth_shape_ = shape
            if view_class is not None:
                cls._amaranth_view_class_ = view_class
        else:
            # Shape is not provided explicitly. Behave the same as a standard enumeration;
            # the lack of `_amaranth_shape_` attribute is used to emit a warning when such
            # an enumeration is used in a concatenation.
            bases = tuple(
                py_enum.Enum if base is Enum else
                py_enum.IntEnum if base is IntEnum else
                py_enum.Flag if base is Flag else
                py_enum.IntFlag if base is IntFlag else base
                for base in bases
            )
            cls = py_enum.EnumMeta.__new__(py_enum.EnumMeta, name, bases, namespace, **kwargs)
        return cls

    def as_shape(cls):
        """Cast this enumeration to a shape.

        Returns
        -------
        :class:`Shape`
            Explicitly provided shape. If not provided, returns the result of shape-casting
            this class :ref:`as a standard Python enumeration <lang-shapeenum>`.

        Raises
        ------
        TypeError
            If the enumeration has neither an explicitly provided shape nor any members.
        """
        if hasattr(cls, "_amaranth_shape_"):
            # Shape was provided explicitly; return it.
            return cls._amaranth_shape_
        else:
            # Shape was not provided explicitly; treat it the same way `Shape.cast` treats
            # standard library enumerations, so that `amaranth.lib.enum.Enum` can be a drop-in
            # replacement for `enum.Enum`.
            return Shape._cast_plain_enum(cls)

    def __call__(cls, value, *args, **kwargs):
        """Cast the value to this enum type.

        When given an integer constant, it returns the corresponding enum value, like a standard
        Python enumeration.

        When given a :ref:`value-like <lang-valuelike>`, it is cast to a value, then wrapped
        in the ``view_class`` specified for this enum type (:class:`EnumView` for :class:`Enum`,
        :class:`FlagView` for :class:`Flag`, or a custom user-defined class). If the type has no
        ``view_class`` (like :class:`IntEnum` or :class:`IntFlag`), a plain
        :class:`Value` is returned.

        Returns
        -------
        instance of itself
            For integer values, or instances of itself.
        :class:`EnumView` or its subclass
            For value-castables, as defined by the ``view_class`` keyword argument.
        :class:`Value`
            For value-castables, when a view class is not specified for this enum.
        """
        if isinstance(value, (Value, ValueCastable)):
            value = Value.cast(value)
            if cls._amaranth_view_class_ is None:
                return value
            else:
                return cls._amaranth_view_class_(cls, value)
        return super().__call__(value, *args, **kwargs)

    def const(cls, init):
        # Same considerations apply as above.
        if init is None:
            # Signal with unspecified initial value passes ``None`` to :meth:`const`.
            # Before RFC 9 was implemented, the unspecified initial value was 0, so this keeps
            # the old behavior intact.
            member = cls(0)
        else:
            member = cls(init)
        return cls(Const(member.value, cls.as_shape()))

    def from_bits(cls, bits):
        return cls(bits)

    def format(cls, value, format_spec):
        if format_spec != "":
            raise ValueError(f"Format specifier {format_spec!r} is not supported for enums")
        return Format.Enum(value, cls, name=cls.__qualname__)


# In 3.11, Python renamed EnumMeta to EnumType. Like Python itself, we support both for
# compatibility.
EnumMeta = EnumType


class Enum(py_enum.Enum):
    """Subclass of the standard :class:`enum.Enum` that has :class:`EnumType` as
    its metaclass and :class:`EnumView` as its view class."""


class IntEnum(py_enum.IntEnum):
    """Subclass of the standard :class:`enum.IntEnum` that has :class:`EnumType` as
    its metaclass."""


class Flag(py_enum.Flag):
    """Subclass of the standard :class:`enum.Flag` that has :class:`EnumType` as
    its metaclass and :class:`FlagView` as its view class."""


class IntFlag(py_enum.IntFlag):
    """Subclass of the standard :class:`enum.IntFlag` that has :class:`EnumType` as
    its metaclass."""


# Fix up the metaclass after the fact: the metaclass __new__ requires these classes
# to already be present, and also would not install itself on them due to lack of shape.
Enum.__class__ = EnumType
IntEnum.__class__ = EnumType
Flag.__class__ = EnumType
IntFlag.__class__ = EnumType


class EnumView(ValueCastable):
    """The view class used for :class:`Enum`.

    Wraps a :class:`Value` and only allows type-safe operations. The only operators allowed are
    equality comparisons (``==`` and ``!=``) with another :class:`EnumView` of the same enum type.
    """

    def __init__(self, enum, target):
        """Constructs a view with the given enum type and target
        (a :ref:`value-like <lang-valuelike>`).
        """
        if not isinstance(enum, EnumType) or not hasattr(enum, "_amaranth_shape_"):
            raise TypeError(f"EnumView type must be an enum with shape, not {enum!r}")
        try:
            cast_target = Value.cast(target)
        except TypeError as e:
            raise TypeError("EnumView target must be a value-castable object, not {!r}"
                            .format(target)) from e
        if cast_target.shape() != enum.as_shape():
            raise TypeError("EnumView target must have the same shape as the enum")
        self.enum = enum
        self.target = cast_target

    def shape(self):
        """Returns the underlying enum type."""
        return self.enum

    def as_value(self):
        """Returns the underlying value."""
        return self.target

    def eq(self, other):
        """Assign to the underlying value.

        Returns
        -------
        :class:`Assign`
            ``self.as_value().eq(other)``
        """
        return self.as_value().eq(other)

    def __add__(self, other):
        raise TypeError("cannot perform arithmetic operations on non-IntEnum enum")

    __radd__ = __add__
    __sub__ = __add__
    __rsub__ = __add__
    __mul__ = __add__
    __rmul__ = __add__
    __floordiv__ = __add__
    __rfloordiv__ = __add__
    __mod__ = __add__
    __rmod__ = __add__
    __lshift__ = __add__
    __rlshift__ = __add__
    __rshift__ = __add__
    __rrshift__ = __add__
    __lt__ = __add__
    __le__ = __add__
    __gt__ = __add__
    __ge__ = __add__

    def __and__(self, other):
        raise TypeError("cannot perform bitwise operations on non-IntEnum non-Flag enum")

    __rand__ = __and__
    __or__ = __and__
    __ror__ = __and__
    __xor__ = __and__
    __rxor__ = __and__

    def __eq__(self, other):
        """Compares the underlying value for equality.

        The other operand has to be either another :class:`EnumView` with the same enum type, or
        a plain value of the underlying enum.

        Returns
        -------
        :class:`Value`
            The result of the equality comparison, as a single-bit value.
        """
        if isinstance(other, self.enum):
            other = self.enum(Value.cast(other))
        if not isinstance(other, EnumView) or other.enum is not self.enum:
            raise TypeError("an EnumView can only be compared to value or other EnumView of the same enum type")
        return self.target == other.target

    def __ne__(self, other):
        if isinstance(other, self.enum):
            other = self.enum(Value.cast(other))
        if not isinstance(other, EnumView) or other.enum is not self.enum:
            raise TypeError("an EnumView can only be compared to value or other EnumView of the same enum type")
        return self.target != other.target

    def __repr__(self):
        return f"{type(self).__qualname__}({self.enum.__qualname__}, {self.target!r})"


class FlagView(EnumView):
    """The view class used for :class:`Flag`.

    In addition to the operations allowed by :class:`EnumView`, it allows bitwise operations among
    values of the same enum type."""

    def __invert__(self):
        """Inverts all flags in this value and returns another :class:`FlagView`.

        Note that this is not equivalent to applying bitwise negation to the underlying value:
        just like the Python :class:`enum.Flag` class, only bits corresponding to flags actually
        defined in the enumeration are included in the result.

        Returns
        -------
        :class:`FlagView`
        """
        if hasattr(self.enum, "_boundary_") and self.enum._boundary_ in (EJECT, KEEP):
            return self.enum._amaranth_view_class_(self.enum, ~self.target)
        else:
            singles_mask = 0
            for flag in self.enum:
                if (flag.value & (flag.value - 1)) == 0:
                    singles_mask |= flag.value
            return self.enum._amaranth_view_class_(self.enum, ~self.target & singles_mask)

    def __bitop(self, other, op):
        if isinstance(other, self.enum):
            other = self.enum(Value.cast(other))
        if not isinstance(other, FlagView) or other.enum is not self.enum:
            raise TypeError("a FlagView can only perform bitwise operation with a value or other FlagView of the same enum type")
        return self.enum._amaranth_view_class_(self.enum, op(self.target, other.target))

    def __and__(self, other):
        """Performs a bitwise AND and returns another :class:`FlagView`.

        The other operand has to be either another :class:`FlagView` of the same enum type, or
        a plain value of the underlying enum type.

        Returns
        -------
        :class:`FlagView`
        """
        return self.__bitop(other, operator.__and__)

    def __or__(self, other):
        """Performs a bitwise OR and returns another :class:`FlagView`.

        The other operand has to be either another :class:`FlagView` of the same enum type, or
        a plain value of the underlying enum type.

        Returns
        -------
        :class:`FlagView`
        """
        return self.__bitop(other, operator.__or__)

    def __xor__(self, other):
        """Performs a bitwise XOR and returns another :class:`FlagView`.

        The other operand has to be either another :class:`FlagView` of the same enum type, or
        a plain value of the underlying enum type.

        Returns
        -------
        :class:`FlagView`
        """
        return self.__bitop(other, operator.__xor__)

    __rand__ = __and__
    __ror__ = __or__
    __rxor__ = __xor__


Enum._amaranth_view_class_ = EnumView
IntEnum._amaranth_view_class_ = None
Flag._amaranth_view_class_ = FlagView
IntFlag._amaranth_view_class_ = None
