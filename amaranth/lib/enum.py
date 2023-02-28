import enum as py_enum
import warnings

from ..hdl.ast import Shape, ShapeCastable, Const
from .._utils import bits_for


__all__ = py_enum.__all__


for member in py_enum.__all__:
    globals()[member] = getattr(py_enum, member)
del member


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
        cls = py_enum.EnumMeta.__new__(metacls, name, bases, namespace, **kwargs)
        if shape is not None:
            # Shape is provided explicitly. Set the `_amaranth_shape_` attribute, and check that
            # the values of every member can be cast to the provided shape without truncation.
            cls._amaranth_shape_ = shape = Shape.cast(shape)
            for member in cls:
                try:
                    Const.cast(member.value)
                except TypeError as e:
                    raise TypeError("Value of enumeration member {!r} must be "
                                    "a constant-castable expression"
                                    .format(member)) from e
                width = bits_for(member.value, shape.signed)
                if member.value < 0 and not shape.signed:
                    warnings.warn(
                        message="Value of enumeration member {!r} is signed, but enumeration "
                                "shape is {!r}" # the repr will be `unsigned(X)`
                                .format(member, shape),
                        category=RuntimeWarning,
                        stacklevel=2)
                elif width > shape.width:
                    warnings.warn(
                        message="Value of enumeration member {!r} will be truncated to "
                                "enumeration shape {!r}"
                                .format(member, shape),
                        category=RuntimeWarning,
                        stacklevel=2)
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
        elif cls.__members__:
            # Shape was not provided explicitly, but enumeration has members; treat it
            # the same way `Shape.cast` treats standard library enumerations, so that
            # `amaranth.lib.enum.Enum` can be a drop-in replacement for `enum.Enum`.
            return Shape._cast_plain_enum(cls)
        else:
            # Shape was not provided explicitly, and enumeration has no members.
            # This is a base or mixin class that cannot be instantiated directly.
            raise TypeError("Enumeration '{}.{}' does not have a defined shape"
                            .format(cls.__module__, cls.__qualname__))


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
