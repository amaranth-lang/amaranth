import enum as py_enum
import warnings

from ..hdl.ast import Value, Shape, ShapeCastable, Const


__all__ = py_enum.__all__


for _member in py_enum.__all__:
    globals()[_member] = getattr(py_enum, _member)
del _member


class EnumMeta(ShapeCastable, py_enum.EnumMeta):
    """Subclass of the standard :class:`enum.EnumMeta` that implements the :class:`ShapeCastable`
    protocol.

    This metaclass provides the :meth:`as_shape` method, making its instances
    :ref:`shape-castable <lang-shapecasting>`, and accepts a ``shape=`` keyword argument
    to specify a shape explicitly. Other than this, it acts the same as the standard
    :class:`enum.EnumMeta` class; if the ``shape=`` argument is not specified and
    :meth:`as_shape` is never called, it places no restrictions on the enumeration class
    or the values of its members.
    """

    # TODO: remove this shim once py3.8 support is dropped
    @classmethod
    def __prepare__(metacls, name, bases, shape=None, **kwargs):
        return super().__prepare__(name, bases, **kwargs)

    def __new__(metacls, name, bases, namespace, shape=None, **kwargs):
        if shape is not None:
            shape = Shape.cast(shape)
        # Prepare enumeration members for instantiation. This logic is unfortunately very
        # convoluted because it supports two very different code paths that need to share
        # the emitted warnings.
        for member_name, member_value in namespace.items():
            if py_enum._is_sunder(member_name) or py_enum._is_dunder(member_name):
                continue
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
        cls = py_enum.EnumMeta.__new__(metacls, name, bases, namespace, **kwargs)
        if shape is not None:
            # Shape is provided explicitly. Set the `_amaranth_shape_` attribute, and check that
            # the values of every member can be cast to the provided shape without truncation.
            cls._amaranth_shape_ = shape
        else:
            # Shape is not provided explicitly. Behave the same as a standard enumeration;
            # the lack of `_amaranth_shape_` attribute is used to emit a warning when such
            # an enumeration is used in a concatenation.
            pass
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

    def __call__(cls, value):
        # :class:`py_enum.Enum` uses ``__call__()`` for type casting: ``E(x)`` returns
        # the enumeration member whose value equals ``x``. In this case, ``x`` must be a concrete
        # value.
        # Amaranth extends this to indefinite values, but conceptually the operation is the same:
        # :class:`View` calls :meth:`Enum.__call__` to go from a :class:`Value` to something
        # representing this enumeration with that value.
        # At the moment however, for historical reasons, this is just the value itself. This works
        # and is backwards-compatible but is limiting in that it does not allow us to e.g. catch
        # comparisons with enum members of the wrong type.
        if isinstance(value, Value):
            return value
        return super().__call__(value)

    def const(cls, init):
        # Same considerations apply as above.
        if init is None:
            # Signal with unspecified reset value passes ``None`` to :meth:`const`.
            # Before RFC 9 was implemented, the unspecified reset value was 0, so this keeps
            # the old behavior intact.
            member = cls(0)
        else:
            member = cls(init)
        return Const(member.value, cls.as_shape())


class Enum(py_enum.Enum, metaclass=EnumMeta):
    """Subclass of the standard :class:`enum.Enum` that has :class:`EnumMeta` as
    its metaclass."""


class IntEnum(py_enum.IntEnum, metaclass=EnumMeta):
    """Subclass of the standard :class:`enum.IntEnum` that has :class:`EnumMeta` as
    its metaclass."""


class Flag(py_enum.Flag, metaclass=EnumMeta):
    """Subclass of the standard :class:`enum.Flag` that has :class:`EnumMeta` as
    its metaclass."""


class IntFlag(py_enum.IntFlag, metaclass=EnumMeta):
    """Subclass of the standard :class:`enum.IntFlag` that has :class:`EnumMeta` as
    its metaclass."""
