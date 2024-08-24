from abc import ABCMeta, abstractmethod
from enum import Enum
from collections.abc import Mapping, Sequence
import warnings
import operator

from amaranth._utils import final
from amaranth.hdl import *
from amaranth import hdl


__all__ = [
    "Field", "Layout", "StructLayout", "UnionLayout", "ArrayLayout", "FlexibleLayout",
    "View", "Const", "Struct", "Union",
]


@final
class Field:
    """Description of a data field.

    The :class:`Field` class specifies the signedness and bit positions of a field in
    an Amaranth value.

    :class:`Field` objects are immutable.

    Attributes
    ----------
    shape : :class:`.ShapeLike`
        Shape of the field. When initialized or assigned, the object is stored as-is.
    offset : :class:`int`, >=0
        Index of the least significant bit of the field.
    """
    def __init__(self, shape, offset):
        try:
            Shape.cast(shape)
        except TypeError as e:
            raise TypeError("Field shape must be a shape-castable object, not {!r}"
                            .format(shape)) from e
        if not isinstance(offset, int) or offset < 0:
            raise TypeError("Field offset must be a non-negative integer, not {!r}"
                            .format(offset))
        self._shape  = shape
        self._offset = offset

    @property
    def shape(self):
        return self._shape

    @property
    def offset(self):
        return self._offset

    @property
    def width(self):
        """Width of the field.

        This property should be used over :py:`self.shape.width` because :py:`self.shape` can be
        an arbitrary :ref:`shape-like <lang-shapelike>` object, which may not have
        a :py:`width` property.

        Returns
        -------
        :class:`int`
            :py:`Shape.cast(self.shape).width`
        """
        return Shape.cast(self.shape).width

    def __eq__(self, other):
        """Compare fields.

        Two fields are equal if they have the same shape and offset.
        """
        return (isinstance(other, Field) and
                Shape.cast(self._shape) == Shape.cast(other.shape) and
                self._offset == other.offset)

    def __repr__(self):
        return f"Field({self._shape!r}, {self._offset})"


class Layout(ShapeCastable, metaclass=ABCMeta):
    """Description of a data layout.

    The :ref:`shape-like <lang-shapelike>` :class:`Layout` interface associates keys
    (string names or integer indexes) with fields, giving identifiers to spans of bits in
    an Amaranth value.

    It is an abstract base class; :class:`StructLayout`, :class:`UnionLayout`,
    :class:`ArrayLayout`, and :class:`FlexibleLayout` implement concrete layout rules.
    New layout rules can be defined by inheriting from this class.

    Like all other shape-castable objects, all layouts are immutable. New classes deriving from
    :class:`Layout` must preserve this invariant.
    """

    @staticmethod
    def cast(obj):
        """Cast a :ref:`shape-like <lang-shapelike>` object to a layout.

        This method performs a subset of the operations done by :meth:`.Shape.cast`; it will
        recursively call :py:`.as_shape()`, but only until a layout is returned.

        Raises
        ------
        TypeError
            If :py:`obj` cannot be converted to a :class:`Layout` instance.
        RecursionError
            If :py:`obj.as_shape()` returns :py:`obj`.
        """
        while isinstance(obj, ShapeCastable):
            if isinstance(obj, Layout):
                return obj
            new_obj = obj.as_shape()
            if new_obj is obj:
                break
            obj = new_obj
        Shape.cast(obj) # delegate non-layout-specific error handling to Shape
        raise TypeError("Object {!r} cannot be converted to a data layout"
                        .format(obj))

    @abstractmethod
    def __iter__(self):
        """Iterate fields in the layout.

        Yields
        ------
        :class:`str` or :class:`int`
            Key (either name or index) for accessing the field.
        :class:`Field`
            Description of the field.
        """

    @abstractmethod
    def __getitem__(self, key):
        """Retrieve a field from the layout.

        Returns
        -------
        :class:`Field`
            The field associated with :py:`key`.

        Raises
        ------
        KeyError
            If there is no field associated with :py:`key`.
        """

    @property
    @abstractmethod
    def size(self):
        """Size of the layout.

        Returns
        -------
        :class:`int`
            The amount of bits required to store every field in the layout.
        """

    def as_shape(self):
        """Shape of the layout.

        Returns
        -------
        :class:`.Shape`
            :py:`unsigned(self.size)`
        """
        return unsigned(self.size)

    def __eq__(self, other):
        """Compare layouts.

        Two layouts are equal if they have the same size and the same fields under the same names.
        The order of the fields is not considered.
        """
        while isinstance(other, ShapeCastable) and not isinstance(other, Layout):
            new_other = other.as_shape()
            if new_other is other:
                break
            other = new_other
        return (isinstance(other, Layout) and self.size == other.size and
                dict(iter(self)) == dict(iter(other)))

    def __call__(self, target):
        """Create a view into a target.

        When a :class:`Layout` is used as the shape of a :class:`Field` and accessed through
        a :class:`View`, this method is used to wrap the slice of the underlying value into
        another view with this layout.

        Returns
        -------
        :class:`View`
            :py:`View(self, target)`
        """
        return View(self, target)

    def const(self, init):
        """Convert a constant initializer to a constant.

        Converts :py:`init`, which may be a sequence or a mapping of field values, to a constant.

        Returns
        -------
        :class:`Const`
            A constant that has the same value as a view with this layout that was initialized with
            an all-zero value and had every field assigned to the corresponding value in the order
            in which they appear in :py:`init`.
        """
        if isinstance(init, Const):
            if Layout.cast(init.shape()) != self:
                raise ValueError(f"Const layout {init.shape()!r} differs from shape layout "
                                 f"{self!r}")
            return init
        if init is None:
            iterator = iter(())
        elif isinstance(init, Mapping):
            iterator = init.items()
        elif isinstance(init, Sequence):
            iterator = enumerate(init)
        else:
            raise TypeError(f"Layout constant initializer must be a mapping or a sequence, not "
                            f"{init!r}")

        int_value = 0
        for key, key_value in iterator:
            try:
                field = self[key]
            except KeyError:
                raise ValueError(f"Layout constant initializer refers to key {key!r}, which is not "
                                 f"a part of the layout")
            cast_field_shape = Shape.cast(field.shape)
            if isinstance(field.shape, ShapeCastable):
                key_value = hdl.Const.cast(hdl.Const(key_value, field.shape))
            elif not isinstance(key_value, hdl.Const):
                key_value = hdl.Const(key_value, cast_field_shape)
            mask = ((1 << cast_field_shape.width) - 1) << field.offset
            int_value &= ~mask
            int_value |= (key_value.value << field.offset) & mask
        return Const(self, int_value)

    def from_bits(self, raw):
        """Convert a bit pattern to a constant.

        Converts :py:`raw`, which is an :class:`int`, to a constant.

        Returns
        -------
        :class:`Const`
            :py:`Const(self, raw)`
        """
        return Const(self, raw)

    def format(self, value, format_spec):
        if format_spec != "":
            raise ValueError(f"Format specifier {format_spec!r} is not supported for layouts")
        value = Value.cast(value)
        fields = {}
        for key, field in self:
            shape = Shape.cast(field.shape)
            field_value = value[field.offset:field.offset+shape.width]
            if isinstance(field.shape, ShapeCastable):
                fields[str(key)] = field.shape.format(field.shape(field_value), "")
            else:
                if shape.signed:
                    field_value = field_value.as_signed()
                fields[str(key)] = Format("{}", field_value)
        return Format.Struct(value, fields)


class StructLayout(Layout):
    """Description of a structure layout.

    The fields of a structure layout follow one another without any gaps, and the size of
    a structure layout is the sum of the sizes of its members.

    For example, the following layout of a 16-bit value:

    .. wavedrom:: data/struct_layout

        {
            "reg": [
                {"name": ".first",  "bits": 3},
                {"name": ".second", "bits": 7},
                {"name": ".third",  "bits": 6}
            ],
            "config": {
                "lanes": 1,
                "compact": true,
                "vflip": true,
                "hspace": 650
            }
        }

    can be described with:

    .. testcode::

        data.StructLayout({
            "first":  3,
            "second": 7,
            "third":  6
        })

    .. note::

        Structures that have padding can be described with a :class:`FlexibleLayout`. Alternately,
        padding can be added to the layout as fields called ``_1``, ``_2``, and so on. These fields
        won't be accessible as attributes or by using indexing.

    Attributes
    ----------
    members : mapping of :class:`str` to :class:`.ShapeLike`
        Dictionary of structure members.
    """

    def __init__(self, members):
        offset = 0
        self._fields = {}
        if not isinstance(members, Mapping):
            raise TypeError("Struct layout members must be provided as a mapping, not {!r}"
                            .format(members))
        for key, shape in members.items():
            if not isinstance(key, str):
                raise TypeError("Struct layout member name must be a string, not {!r}"
                                .format(key))
            try:
                cast_shape = Shape.cast(shape)
            except TypeError as e:
                raise TypeError("Struct layout member shape must be a shape-castable object, "
                                "not {!r}"
                                .format(shape)) from e
            self._fields[key] = Field(shape, offset)
            offset += cast_shape.width

    @property
    def members(self):
        return {key: field.shape for key, field in self._fields.items()}

    def __iter__(self):
        return iter(self._fields.items())

    def __getitem__(self, key):
        return self._fields[key]

    @property
    def size(self):
        """Size of the structure layout.

        Returns
        -------
        :class:`int`
            Index of the most significant bit of the *last* field plus one; or zero if there are
            no fields.
        """
        return max((field.offset + field.width for field in self._fields.values()), default=0)

    def __repr__(self):
        return f"StructLayout({self.members!r})"


class UnionLayout(Layout):
    """Description of a union layout.

    The fields of a union layout all start from bit 0, and the size of a union layout is the size
    of the largest of its members.

    For example, the following layout of a 7-bit value:

    .. wavedrom:: data/union_layout

        {
            "reg": [
                {"name": ".third",  "bits": 6},
                {"name": "",        "bits": 1, "type": 1},
                {"name": ".second", "bits": 7},
                {"name": ".first",  "bits": 3},
                {"name": "",        "bits": 4, "type": 1}
            ],
            "config": {
                "lanes": 3,
                "compact": true,
                "vflip": true,
                "hspace": 289.4375
            }
        }

    can be described with:

    .. testcode::

        data.UnionLayout({
            "first":  3,
            "second": 7,
            "third":  6
        })

    Attributes
    ----------
    members : mapping of :class:`str` to :class:`.ShapeLike`
        Dictionary of union members.
    """
    def __init__(self, members):
        self._fields = {}
        if not isinstance(members, Mapping):
            raise TypeError("Union layout members must be provided as a mapping, not {!r}"
                            .format(members))
        for key, shape in members.items():
            if not isinstance(key, str):
                raise TypeError("Union layout member name must be a string, not {!r}"
                                .format(key))
            try:
                cast_shape = Shape.cast(shape)
            except TypeError as e:
                raise TypeError("Union layout member shape must be a shape-castable object, "
                                "not {!r}"
                                .format(shape)) from e
            self._fields[key] = Field(shape, 0)

    @property
    def members(self):
        return {key: field.shape for key, field in self._fields.items()}

    def __iter__(self):
        return iter(self._fields.items())

    def __getitem__(self, key):
        return self._fields[key]

    @property
    def size(self):
        """Size of the union layout.

        Returns
        -------
        :class:`int`
            Index of the most significant bit of the *largest* field plus one; or zero if there are
            no fields.
        """
        return max((field.width for field in self._fields.values()), default=0)

    def const(self, init):
        if init is not None and len(init) > 1:
            raise ValueError("Initializer for at most one field can be provided for "
                             "a union layout (specified: {})"
                             .format(", ".join(init.keys())))
        return super().const(init)

    def __repr__(self):
        return f"UnionLayout({self.members!r})"


class ArrayLayout(Layout):
    """Description of an array layout.

    The fields of an array layout follow one another without any gaps, and the size of an array
    layout is the size of its element multiplied by its length.

    For example, the following layout of a 16-bit value:

    .. wavedrom:: data/array_layout

        {
            "reg": [
                {"name": "[0]",  "bits": 4},
                {"name": "[1]",  "bits": 4},
                {"name": "[2]",  "bits": 4},
                {"name": "[3]",  "bits": 4}
            ],
            "config": {
                "lanes": 1,
                "compact": true,
                "vflip": true,
                "hspace": 650
            }
        }

    can be described with:

    .. testcode::

        data.ArrayLayout(unsigned(4), 4)

    .. note::

        Arrays that have padding can be described with a :class:`FlexibleLayout`.

    .. note::

        This class, :class:`amaranth.lib.data.ArrayLayout`, is distinct from and serves a different
        function than :class:`amaranth.hdl.Array`.

    Attributes
    ----------
    elem_shape : :class:`.ShapeLike`
        Shape of an individual element.
    length : :class:`int`
        Amount of elements.
    """
    def __init__(self, elem_shape, length):
        try:
            Shape.cast(elem_shape)
        except TypeError as e:
            raise TypeError("Array layout element shape must be a shape-castable object, "
                            "not {!r}"
                            .format(elem_shape)) from e
        if not isinstance(length, int) or length < 0:
            raise TypeError("Array layout length must be a non-negative integer, not {!r}"
                            .format(length))
        self._elem_shape = elem_shape
        self._length     = length

    @property
    def elem_shape(self):
        return self._elem_shape

    @property
    def length(self):
        return self._length

    def __iter__(self):
        offset = 0
        for index in range(self._length):
            yield index, Field(self._elem_shape, offset)
            offset += Shape.cast(self._elem_shape).width

    def __getitem__(self, key):
        if isinstance(key, int):
            if key not in range(-self._length, self._length):
                # Layout's interface requires us to raise KeyError, not IndexError
                raise KeyError(key)
            if key < 0:
                key += self._length
            return Field(self._elem_shape, key * Shape.cast(self._elem_shape).width)
        raise TypeError(f"Cannot index array layout with {key!r}")

    @property
    def size(self):
        """Size of the array layout.

        Returns
        -------
        :class:`int`
            Size of an individual element multiplied by their amount.
        """
        return Shape.cast(self._elem_shape).width * self.length

    def __repr__(self):
        return f"ArrayLayout({self._elem_shape!r}, {self.length})"

    def format(self, value, format_spec):
        if format_spec != "":
            raise ValueError(f"Format specifier {format_spec!r} is not supported for layouts")
        value = Value.cast(value)
        fields = []
        shape = Shape.cast(self._elem_shape)
        for index in range(self._length):
            field_value = value[shape.width * index:shape.width * (index + 1)]
            if isinstance(self._elem_shape, ShapeCastable):
                fields.append(self._elem_shape.format(self._elem_shape(field_value), ""))
            else:
                if shape.signed:
                    field_value = field_value.as_signed()
                fields.append(Format("{}", field_value))
        return Format.Array(value, fields)


class FlexibleLayout(Layout):
    """Description of a flexible layout.

    A flexible layout is similar to a structure layout; while fields in :class:`StructLayout` are
    defined contiguously, the fields in a flexible layout can overlap and have gaps between them.

    Because the size and field boundaries in a flexible layout can be defined arbitrarily, it
    may also be more convenient to use a flexible layout when the layout information is derived
    from an external data file rather than defined in Python code.

    For example, the following layout of a 16-bit value:

    .. wavedrom:: data/flexible_layout

        {
            "reg": [
                {"name": "",        "bits": 14, "type": 1},
                {"name": "[0]",     "bits":  1},
                {"name": "",        "bits":  1, "type": 1},
                {"name": "",        "bits": 10, "type": 1},
                {"name": ".third",  "bits":  6},
                {"name": ".second", "bits":  7},
                {"name": "",        "bits":  9, "type": 1},
                {"name": "",        "bits":  1, "type": 1},
                {"name": ".first",  "bits":  3},
                {"name": "",        "bits": 12, "type": 1}
            ],
            "config": {
                "lanes": 4,
                "compact": true,
                "vflip": true,
                "hspace": 650
            }
        }

    can be described with:

    .. testcode::

        data.FlexibleLayout(16, {
            "first":  data.Field(unsigned(3), 1),
            "second": data.Field(unsigned(7), 0),
            "third":  data.Field(unsigned(6), 10),
            0:        data.Field(unsigned(1), 14)
        })

    Both strings and integers can be used as names of flexible layout fields, so flexible layouts
    can be used to describe structures with arbitrary padding and arrays with arbitrary stride.

    If another data structure is used as the source of truth for creating flexible layouts,
    consider instead inheriting from the base :class:`Layout` class, which may be more convenient.

    Attributes
    ----------
    size : :class:`int`
        Size of the layout.
    fields : mapping of :class:`str` or :class:`int` to :class:`Field`
        Fields defined in the layout.
    """
    def __init__(self, size, fields):
        if not isinstance(size, int) or size < 0:
            raise TypeError("Flexible layout size must be a non-negative integer, not {!r}"
                            .format(size))
        if not isinstance(fields, Mapping):
            raise TypeError("Flexible layout fields must be provided as a mapping, not {!r}"
                            .format(fields))
        self._size = size
        self._fields = {}
        for key, field in fields.items():
            if not isinstance(key, (int, str)) or (isinstance(key, int) and key < 0):
                raise TypeError("Flexible layout field name must be a non-negative integer or "
                                "a string, not {!r}"
                                .format(key))
            if not isinstance(field, Field):
                raise TypeError("Flexible layout field value must be a Field instance, not {!r}"
                                .format(field))
            if field.offset + field.width > size:
                raise ValueError("Flexible layout field '{}' ends at bit {}, exceeding "
                                 "the size of {} bit(s)"
                                 .format(key, field.offset + field.width, size))
            self._fields[key] = field

    @property
    def size(self):
        """:meta private:""" # work around Sphinx bug
        return self._size

    @property
    def fields(self):
        return {**self._fields}

    def __iter__(self):
        return iter(self._fields.items())

    def __getitem__(self, key):
        if isinstance(key, (int, str)):
            return self._fields[key]
        raise TypeError(f"Cannot index flexible layout with {key!r}")

    def __repr__(self):
        return f"FlexibleLayout({self._size}, {self._fields!r})"


class View(ValueCastable):
    """A value viewed through the lens of a layout.

    The :ref:`value-like <lang-valuelike>` class :class:`View` provides access to the fields
    of an underlying Amaranth value via the names or indexes defined in the provided layout.

    Creating a view
    ###############

    A view must be created using an explicitly provided layout and target. To create a new
    :class:`Signal` that is wrapped in a :class:`View` with a given :py:`layout`, use
    :py:`Signal(layout, ...)`, which for a :class:`Layout` is equivalent to
    :py:`View(layout, Signal(...))`.

    Accessing a view
    ################

    Slicing a view or accessing its attributes returns a part of the underlying value
    corresponding to the field with that index or name, which is itself either a value or
    a value-castable object. If the shape of the field is a :class:`Layout`, it will be
    a :class:`View`; if it is a class deriving from :class:`Struct` or :class:`Union`, it
    will be an instance of that data class; if it is another :ref:`shape-like <lang-shapelike>`
    object implementing :meth:`~.ShapeCastable.__call__`, it will be the result of calling that
    method.

    Slicing a view whose layout is an :class:`ArrayLayout` can be done with an index that is
    an Amaranth value rather than a constant integer. The returned element is chosen dynamically
    in that case.

    A view can only be compared for equality with another view or constant with the same layout,
    returning a single-bit :class:`.Value`. No other operators are supported. A view can be
    lowered to a :class:`.Value` using :meth:`as_value`.

    Custom view classes
    ###################

    The :class:`View` class can be inherited from to define additional properties or methods on
    a view. The only three names that are reserved on instances of :class:`View` and :class:`Const`
    are :meth:`as_value`, :meth:`Const.as_bits`, and :meth:`eq`, leaving the rest to the developer.
    The :class:`Struct` and :class:`Union` classes provided in this module are subclasses of
    :class:`View` that also provide a concise way to define a layout.
    """
    def __init__(self, layout, target):
        try:
            cast_layout = Layout.cast(layout)
        except TypeError as e:
            raise TypeError("Layout of a view must be a Layout, not {!r}"
                            .format(layout)) from e
        try:
            cast_target = Value.cast(target)
        except TypeError as e:
            raise TypeError("Target of a view must be a value-castable object, not {!r}"
                            .format(target)) from e
        if len(cast_target) != cast_layout.size:
            raise ValueError("Target of a view is {} bit(s) wide, which is not compatible with "
                             "its {} bit(s) wide layout"
                             .format(len(cast_target), cast_layout.size))
        for name, field in cast_layout:
            if isinstance(name, str) and name[0] != "_" and hasattr(type(self), name):
                warnings.warn("Layout of a view includes a field {!r} that will be shadowed by "
                              "the attribute '{}.{}.{}'"
                              .format(name, type(self).__module__, type(self).__qualname__, name),
                              SyntaxWarning, stacklevel=2)
        self.__orig_layout = layout
        self.__layout = cast_layout
        self.__target = cast_target

    def shape(self):
        """Get layout of this view.

        Returns
        -------
        :class:`Layout`
            The :py:`layout` provided when constructing the view.
        """
        return self.__orig_layout

    def as_value(self):
        """Get underlying value.

        Returns
        -------
        :class:`.Value`
            The :py:`target` provided when constructing the view, or the :class:`Signal` that
            was created.
        """
        return self.__target

    def eq(self, other):
        """Assign to the underlying value.

        Returns
        -------
        :class:`.Assign`
            :py:`self.as_value().eq(other)`
        """
        return self.as_value().eq(other)

    def __getitem__(self, key):
        """Slice the underlying value.

        A field corresponding to :py:`key` is looked up in the layout. If the field's shape is
        a shape-castable object that has a :meth:`~.ShapeCastable.__call__` method, it is called and
        the result is returned. Otherwise, :meth:`~.ShapeCastable.as_shape` is called repeatedly on
        the shape until either an object with a :meth:`~.ShapeCastable.__call__` method is reached,
        or a :class:`.Shape` is returned. In the latter case, returns an unspecified Amaranth
        expression with the right shape.

        Arguments
        ---------
        key : :class:`str` or :class:`int` or :class:`.ValueCastable`
            Name or index of a field.

        Returns
        -------
        :class:`.Value` or :class:`.ValueCastable`, :ref:`assignable <lang-assignable>`
            A slice of the underlying value defined by the field.

        Raises
        ------
        :exc:`KeyError`
            If the layout does not define a field corresponding to :py:`key`.
        :exc:`TypeError`
            If :py:`key` is a value-castable object, but the layout of the view is not
            an :class:`ArrayLayout`.
        :exc:`TypeError`
            If :meth:`.ShapeCastable.__call__` does not return a value or a value-castable object.
        """
        if isinstance(self.__layout, ArrayLayout):
            elem_width = Shape.cast(self.__layout.elem_shape).width
            if isinstance(key, slice):
                start, stop, stride = key.indices(self.__layout.length)
                shape = ArrayLayout(self.__layout.elem_shape, len(range(start, stop, stride)))
                if stride == 1:
                    value = self.__target[start * elem_width:stop * elem_width]
                else:
                    value = Cat(self.__target[index * elem_width:(index + 1) * elem_width]
                                for index in range(start, stop, stride))
            elif isinstance(key, int):
                if key not in range(-self.__layout.length, self.__layout.length):
                    raise IndexError(f"Index {key} is out of range for array layout of length "
                                     f"{self.__layout.length}")
                if key < 0:
                    key += self.__layout.length
                shape = self.__layout.elem_shape
                value = self.__target[key * elem_width:(key + 1) * elem_width]
            elif isinstance(key, (Value, ValueCastable)):
                shape = self.__layout.elem_shape
                value = self.__target.word_select(key, elem_width)
            else:
                raise TypeError(
                    f"View with array layout may only be indexed with an integer or a value, "
                    f"not {key!r}")
        else:
            if isinstance(key, slice):
                raise TypeError(
                    "Non-array view cannot be indexed with a slice; did you mean to call "
                    "`.as_value()` first?")
            if isinstance(key, (Value, ValueCastable)):
                raise TypeError(
                    f"Only views with array layout, not {self.__layout!r}, may be indexed with "
                    f"a value")
            field = self.__layout[key]
            shape = field.shape
            value = self.__target[field.offset:field.offset + field.width]
        # Field guarantees that the shape-castable object is well-formed, so there is no need
        # to handle erroneous cases here.
        if isinstance(shape, ShapeCastable):
            value = shape(value)
            if not isinstance(value, (Value, ValueCastable)):
                raise TypeError(
                    f"{shape!r}.__call__() must return a value or a value-castable object, not "
                    f"{value!r}")
            return value
        if Shape.cast(shape).signed:
            return value.as_signed()
        else:
            return value

    def __getattr__(self, name):
        """Access a field of the underlying value.

        Returns :py:`self[name]`.

        Raises
        ------
        :exc:`AttributeError`
            If the layout does not define a field called :py:`name`, or if :py:`name` starts with
            an underscore.
        """
        if isinstance(self.__layout, ArrayLayout):
            raise AttributeError(
                f"View with an array layout does not have fields")
        try:
            item = self[name]
        except KeyError:
            raise AttributeError(
                f"View with layout {self.__layout!r} does not have a field {name!r}; did you mean "
                f"one of: {', '.join(repr(name) for name, field in self.__layout)}?")
        if name.startswith("_"):
            raise AttributeError(
                f"Field {name!r} of view with layout {self.__layout!r} has a reserved name and "
                f"may only be accessed by indexing")
        return item

    def __len__(self):
        if not isinstance(self.__layout, ArrayLayout):
            raise TypeError(
                f"`len()` can only be used on views of array layout, not {self.__layout!r}")
        return self.__layout.length

    def __eq__(self, other):
        if isinstance(other, View) and self.__layout == other.__layout:
            return self.__target == other.__target
        elif isinstance(other, Const) and self.__layout == other._Const__layout:
            return self.__target == other.as_value()
        else:
            raise TypeError(
                f"View with layout {self.__layout!r} can only be compared to another view or "
                f"constant with the same layout, not {other!r}")

    def __ne__(self, other):
        if isinstance(other, View) and self.__layout == other.__layout:
            return self.__target != other.__target
        elif isinstance(other, Const) and self.__layout == other._Const__layout:
            return self.__target != other.as_value()
        else:
            raise TypeError(
                f"View with layout {self.__layout!r} can only be compared to another view or "
                f"constant with the same layout, not {other!r}")

    def __add__(self, other):
        raise TypeError("Cannot perform arithmetic operations on a View")

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
        raise TypeError("Cannot perform bitwise operations on a View")

    __rand__ = __and__
    __or__ = __and__
    __ror__ = __and__
    __xor__ = __and__
    __rxor__ = __and__

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.__layout!r}, {self.__target!r})"


class Const(ValueCastable):
    """A constant value viewed through the lens of a layout.

    The :class:`Const` class is similar to the :class:`View` class, except that its target is
    a specific bit pattern and operations on it return constants.

    Creating a constant
    ###################

    A constant can be created from a :class:`dict` or :class:`list` of field values using
    :meth:`Layout.const`, or from a bit pattern using :meth:`Layout.from_bits`.

    Accessing a constant
    ####################

    Slicing a constant or accessing its attributes returns a part of the underlying value
    corresponding to the field with that index or name. If the shape of the field is
    a :class:`Layout`, the returned value is a :class:`Const`; if it is a different
    :ref:`shape-like <lang-shapelike>` object implementing :meth:`~.ShapeCastable.from_bits`,
    it will be the result of calling that method; otherwise, it is an :class:`int`.

    Slicing a constant whose layout is an :class:`ArrayLayout` can be done with an index that is
    an Amaranth value rather than a constant integer. The returned element is chosen dynamically
    in that case, and the resulting value will be a :class:`View` instead of a :class:`Const`.

    A :class:`Const` can only be compared for equality with another constant or view that has
    the same layout. When compared with another constant, the result will be a :class:`bool`.
    When compared with a view, the result will be a single-bit :class:`.Value`. No other operators
    are supported. A constant can be lowered to a :class:`.Value` using :meth:`as_value`, or to
    its underlying bit pattern using :meth:`as_bits`.
    """
    def __init__(self, layout, target):
        try:
            cast_layout = Layout.cast(layout)
        except TypeError as e:
            raise TypeError(f"Layout of a constant must be a Layout, not {layout!r}") from e
        try:
            target = operator.index(target)
        except TypeError as e:
            raise TypeError(f"Target of a constant must be an int, not {target!r}") from e
        if target not in range(1 << cast_layout.size):
            raise ValueError(f"Target of a constant does not fit in {cast_layout.size} bit(s)")
        for name, field in cast_layout:
            if isinstance(name, str) and name[0] != "_" and hasattr(type(self), name):
                warnings.warn("Layout of a constant includes a field {!r} that will be shadowed by "
                              "the attribute '{}.{}.{}'"
                              .format(name, type(self).__module__, type(self).__qualname__, name),
                              SyntaxWarning, stacklevel=2)
        self.__orig_layout = layout
        self.__layout = cast_layout
        self.__target = target

    def shape(self):
        """Get layout of this constant.

        Returns
        -------
        :class:`Layout`
            The :py:`layout` provided when constructing the constant.
        """
        return self.__orig_layout

    def as_bits(self):
        """Get underlying bit pattern.

        Returns
        -------
        :class:`int`
            The :py:`target` provided when constructing the constant.
        """
        return self.__target

    def as_value(self):
        """Convert to a value.

        Returns
        -------
        :class:`.Const`
            The bit pattern of this constant, as a :class:`.Value`.
        """
        return hdl.Const(self.__target, self.__layout.size)

    def __getitem__(self, key):
        """Slice the underlying value.

        A field corresponding to :py:`key` is looked up in the layout. If the field's shape is
        a shape-castable object that has a :meth:`~.ShapeCastable.from_bits` method, returns
        the result of calling that method. Otherwise, returns an :class:`int`.

        Arguments
        ---------
        key : :class:`str` or :class:`int` or :class:`.ValueCastable`
            Name or index of a field.

        Returns
        -------
        unspecified type or :class:`int`
            A slice of the underlying value defined by the field.

        Raises
        ------
        :exc:`KeyError`
            If the layout does not define a field corresponding to :py:`key`.
        :exc:`TypeError`
            If :py:`key` is a value-castable object, but the layout of the constant is not
            an :class:`ArrayLayout`.
        :exc:`Exception`
            If the bit pattern of the field is not valid according to
            :meth:`.ShapeCastable.from_bits`. Usually this will be a :exc:`ValueError`.
        """
        if isinstance(self.__layout, ArrayLayout):
            elem_width = Shape.cast(self.__layout.elem_shape).width
            if isinstance(key, slice):
                start, stop, stride = key.indices(self.__layout.length)
                shape = ArrayLayout(self.__layout.elem_shape, len(range(start, stop, stride)))
                if stride == 1:
                    value = (self.__target >> start * elem_width) & ((1 << elem_width * (stop - start)) - 1)
                else:
                    value = 0
                    pos = 0
                    for index in range(start, stop, stride):
                        elem_value = (self.__target >> index * elem_width) & ((1 << elem_width) - 1)
                        value |= elem_value << pos
                        pos += elem_width
            elif isinstance(key, int):
                if key not in range(-self.__layout.length, self.__layout.length):
                    raise IndexError(f"Index {key} is out of range for array layout of length "
                                     f"{self.__layout.length}")
                if key < 0:
                    key += self.__layout.length
                shape = self.__layout.elem_shape
                value = (self.__target >> key * elem_width) & ((1 << elem_width) - 1)
            elif isinstance(key, (Value, ValueCastable)):
                return View(self.__layout, self.as_value())[key]
            else:
                raise TypeError(
                    f"Constant with array layout may only be indexed with an integer or a value, "
                    f"not {key!r}")
        else:
            if isinstance(key, slice):
                raise TypeError(
                    "Non-array constant cannot be indexed with a slice; did you mean to call "
                    "`.as_value()` first?")
            if isinstance(key, (Value, ValueCastable)):
                raise TypeError(
                    f"Only constants with array layout, not {self.__layout!r}, may be indexed with "
                    f"a value")
            field = self.__layout[key]
            shape = field.shape
            value = (self.__target >> field.offset) & ((1 << field.width) - 1)
        # Field guarantees that the shape-castable object is well-formed, so there is no need
        # to handle erroneous cases here.
        if isinstance(shape, ShapeCastable):
            return shape.from_bits(value)
        return hdl.Const(value, Shape.cast(shape)).value

    def __getattr__(self, name):
        """Access a field of the underlying value.

        Returns :py:`self[name]`.

        Raises
        ------
        :exc:`AttributeError`
            If the layout does not define a field called :py:`name`, or if :py:`name` starts with
            an underscore.
        :exc:`Exception`
            If the bit pattern of the field is not valid according to
            :meth:`.ShapeCastable.from_bits`. Usually this will be a :exc:`ValueError`.
        """
        if isinstance(self.__layout, ArrayLayout):
            raise AttributeError(
                f"Constant with an array layout does not have fields")
        try:
            item = self[name]
        except KeyError:
            raise AttributeError(
                f"Constant with layout {self.__layout!r} does not have a field {name!r}; did you mean "
                f"one of: {', '.join(repr(name) for name, field in self.__layout)}?")
        if name.startswith("_"):
            raise AttributeError(
                f"Field {name!r} of constant with layout {self.__layout!r} has a reserved name and "
                f"may only be accessed by indexing")
        return item

    def __len__(self):
        if not isinstance(self.__layout, ArrayLayout):
            raise TypeError(
                f"`len()` can only be used on constants of array layout, not {self.__layout!r}")
        return self.__layout.length

    def __eq__(self, other):
        if isinstance(other, View) and self.__layout == other._View__layout:
            return self.as_value() == other._View__target
        elif isinstance(other, Const) and self.__layout == other.__layout:
            return self.__target == other.__target
        else:
            cause = None
            if isinstance(other, (dict, list)):
                try:
                    other_as_const = self.__layout.const(other)
                except (TypeError, ValueError) as exc:
                    cause = exc
                else:
                    return self == other_as_const
            raise TypeError(
                f"Constant with layout {self.__layout!r} can only be compared to another view, "
                f"a constant with the same layout, or a dictionary or a list that can be converted "
                f"to a constant with the same layout, not {other!r}") from cause

    def __ne__(self, other):
        if isinstance(other, View) and self.__layout == other._View__layout:
            return self.as_value() != other._View__target
        elif isinstance(other, Const) and self.__layout == other.__layout:
            return self.__target != other.__target
        else:
            cause = None
            if isinstance(other, (dict, list)):
                try:
                    other_as_const = self.__layout.const(other)
                except (TypeError, ValueError) as exc:
                    cause = exc
                else:
                    return self != other_as_const
            raise TypeError(
                f"Constant with layout {self.__layout!r} can only be compared to another view, "
                f"a constant with the same layout, or a dictionary or a list that can be converted "
                f"to a constant with the same layout, not {other!r}") from cause

    def __add__(self, other):
        raise TypeError("Cannot perform arithmetic operations on a lib.data.Const")

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
        raise TypeError("Cannot perform bitwise operations on a lib.data.Const")

    __rand__ = __and__
    __or__ = __and__
    __ror__ = __and__
    __xor__ = __and__
    __rxor__ = __and__

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.__layout!r}, {self.__target!r})"


class _AggregateMeta(ShapeCastable, type):
    def __new__(metacls, name, bases, namespace):
        if "__annotations__" not in namespace:
            # This is a base class without its own layout. It is not shape-castable, and cannot
            # be instantiated. It can be used to share behavior.
            return type.__new__(metacls, name, bases, namespace)
        elif all(not hasattr(base, "_AggregateMeta__layout") for base in bases):
            # This is a leaf class with its own layout. It is shape-castable and can
            # be instantiated. It can also be subclassed, and used to share layout and behavior.
            layout  = dict()
            default = dict()
            for field_name in {**namespace["__annotations__"]}:
                try:
                    Shape.cast(namespace["__annotations__"][field_name])
                except TypeError:
                    # Not a shape-castable annotation; leave as-is.
                    continue
                layout[field_name] = namespace["__annotations__"].pop(field_name)
                if field_name in namespace:
                    default[field_name] = namespace.pop(field_name)
            cls = type.__new__(metacls, name, bases, namespace)
            if cls.__layout_cls is UnionLayout:
                if len(default) > 1:
                    raise ValueError("Initial value for at most one field can be provided for "
                                     "a union class (specified: {})"
                                     .format(", ".join(default.keys())))
            cls.__layout  = cls.__layout_cls(layout)
            cls.__default = default
            return cls
        else:
            # This is a class that has a base class with a layout and annotations. Such a class
            # is not well-formed.
            raise TypeError("Aggregate class '{}' must either inherit or specify a layout, "
                            "not both"
                            .format(name))

    def as_shape(cls):
        if not hasattr(cls, "_AggregateMeta__layout"):
            raise TypeError("Aggregate class '{}.{}' does not have a defined shape"
                            .format(cls.__module__, cls.__qualname__))
        return cls.__layout

    def __call__(cls, target):
        # This method exists to pass the override check done by ShapeCastable.
        return super().__call__(cls, target)

    def const(cls, init):
        if isinstance(init, Const):
            if Layout.cast(init.shape()) != Layout.cast(cls.__layout):
                raise ValueError(f"Const layout {init.shape()!r} differs from shape layout "
                                 f"{cls.__layout!r}")
            return init
        if cls.__layout_cls is UnionLayout:
            if init is not None and len(init) > 1:
                raise ValueError("Initializer for at most one field can be provided for "
                                 "a union class (specified: {})"
                                 .format(", ".join(init.keys())))
            return cls.as_shape().const(init or cls.__default)
        else:
            fields = cls.__default.copy()
            fields.update(init or {})
            return cls.as_shape().const(fields)

    def from_bits(cls, bits):
        return cls.as_shape().from_bits(bits)

    def format(cls, value, format_spec):
        return cls.__layout.format(value, format_spec)

    def _value_repr(cls, value):
        return cls.__layout._value_repr(value)


class Struct(View, metaclass=_AggregateMeta):
    """Structures defined with annotations.

    The :class:`Struct` base class is a subclass of :class:`View` that provides a concise way
    to describe the structure layout and initial values for the fields using Python
    :term:`variable annotations <python:variable annotation>`.

    Any annotations containing :ref:`shape-like <lang-shapelike>` objects are used,
    in the order in which they appear in the source code, to construct a :class:`StructLayout`.
    The values assigned to such annotations are used to populate the initial value of the signal
    created by the view. Any other annotations are kept as-is.

    .. testsetup::

        from amaranth import *
        from amaranth.lib.data import *

    As an example, a structure for `IEEE 754 single-precision floating-point format
    <https://en.wikipedia.org/wiki/Single-precision_floating-point_format>`_ can be defined as:

    .. testcode::

        class IEEE754Single(Struct):
            fraction: 23
            exponent:  8 = 0x7f
            sign:      1

            def is_subnormal(self):
                return self.exponent == 0

    The :py:`IEEE754Single` class itself can be used where a :ref:`shape <lang-shapes>` is expected:

    .. doctest::

        >>> IEEE754Single.as_shape()
        StructLayout({'fraction': 23, 'exponent': 8, 'sign': 1})
        >>> Signal(IEEE754Single).as_value().shape().width
        32

    Instances of this class can be used where :ref:`values <lang-values>` are expected:

    .. doctest::

        >>> flt = Signal(IEEE754Single)
        >>> Signal(32).eq(flt)
        (eq (sig $signal) (sig flt))

    Accessing shape-castable properties returns slices of the underlying value:

    .. doctest::

        >>> flt.fraction
        (slice (sig flt) 0:23)
        >>> flt.is_subnormal()
        (== (slice (sig flt) 23:31) (const 1'd0))

    The initial values for individual fields can be overridden during instantiation:

    .. doctest::

        >>> hex(Signal(IEEE754Single).as_value().init)
        '0x3f800000'
        >>> hex(Signal(IEEE754Single, init={'sign': 1}).as_value().init)
        '0xbf800000'
        >>> hex(Signal(IEEE754Single, init={'exponent': 0}).as_value().init)
        '0x0'

    Classes inheriting from :class:`Struct` can be used as base classes. The only restrictions
    are that:

    * Classes that do not define a layout cannot be instantiated or converted to a shape;
    * A layout can be defined exactly once in the inheritance hierarchy.

    Behavior can be shared through inheritance:

    .. testcode::

        class HasChecksum(Struct):
            def checksum(self):
                bits = Value.cast(self)
                return sum(bits[n:n+8] for n in range(0, len(bits), 8))

        class BareHeader(HasChecksum):
            address: 16
            length:   8

        class HeaderWithParam(HasChecksum):
            address: 16
            length:   8
            param:    8

    .. doctest::

        >>> HasChecksum.as_shape()
        Traceback (most recent call last):
          ...
        TypeError: Aggregate class 'HasChecksum' does not have a defined shape
        >>> bare = Signal(BareHeader); bare.checksum()
        (+ (+ (+ (const 1'd0) (slice (sig bare) 0:8)) (slice (sig bare) 8:16)) (slice (sig bare) 16:24))
        >>> param = Signal(HeaderWithParam); param.checksum()
        (+ (+ (+ (+ (const 1'd0) (slice (sig param) 0:8)) (slice (sig param) 8:16)) (slice (sig param) 16:24)) (slice (sig param) 24:32))
    """
    _AggregateMeta__layout_cls = StructLayout


class Union(View, metaclass=_AggregateMeta):
    """Unions defined with annotations.

    The :class:`Union` base class is a subclass of :class:`View` that provides a concise way
    to describe the union layout using Python :term:`variable annotations <python:variable
    annotation>`. It is very similar to the :class:`Struct` class, except that its layout
    is a :class:`UnionLayout`.

    A :class:`Union` can have only one field with a specified initial value. If an initial value is
    explicitly provided during instantiation, it overrides the initial value specified with
    an annotation:

    .. testcode::

        class VarInt(Union):
            int8:  8
            int16: 16 = 0x100

    .. doctest::

        >>> Signal(VarInt).as_value().init
        256
        >>> Signal(VarInt, init={'int8': 10}).as_value().init
        10
    """
    _AggregateMeta__layout_cls = UnionLayout
