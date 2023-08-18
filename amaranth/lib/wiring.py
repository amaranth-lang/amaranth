from collections.abc import Mapping
import enum
import re
import warnings

from .. import tracer
from ..hdl.ast import Shape, ShapeCastable, Const, Signal, Value, ValueCastable
from ..hdl.ir import Elaboratable
from .._utils import final


__all__ = ["In", "Out", "Signature", "PureInterface", "connect", "flipped", "Component"]


class Flow(enum.Enum):
    """Direction of data flow. This enumeration has two values, :attr:`Out` and :attr:`In`,
    the meaning of which depends on the context in which they are used.
    """

    #: `Outgoing` data flow.
    #:
    #: When included in a standalone :class:`Signature`, a port :class:`Member` with an :attr:`Out`
    #: data flow carries data from an `initiator` to a `responder`. That is, the signature
    #: describes the initiator `driving` the signal and the responder `sampling` the signal.
    #:
    #: When used as the flow of a signature :class:`Member`, indicates that the data flow of
    #: the port members of the inner signature `remains the same`.
    #:
    #: When included in the ``signature`` property of an :class:`Elaboratable`, the signature
    #: describes the elaboratable `driving` the corresponding signal. That is, the elaboratable is
    #: treated as the `initiator`.
    Out = "Out"

    #: `Incoming` data flow.
    #:
    #: When included in a standalone :class:`Signature`, a port :class:`Member` with an :attr:`In`
    #: data flow carries data from an `responder` to a `initiator`. That is, the signature
    #: describes the initiator `sampling` the signal and the responder `driving` the signal.
    #:
    #: When used as the flow of a signature :class:`Member`, indicates that the data flow of
    #: the port members of the inner signature `is flipped`.
    #:
    #: When included in the ``signature`` property of an :class:`Elaboratable`, the signature
    #: describes the elaboratable `sampling` the corresponding signal. That is, the elaboratable is
    #: treated as the `initiator`, the same as in the :attr:`Out` case.
    In = "In"

    def flip(self):
        """Flip the direction of data flow.

        Returns
        -------
        :class:`Flow`
            :attr:`In` if called as :pc:`Out.flip()`; :attr:`Out` if called as :pc:`In.flip()`.
        """
        if self == Out:
            return In
        if self == In:
            return Out
        assert False # :nocov:

    def __call__(self, description, *, reset=None):
        """Create a :class:`Member` with this data flow and the provided description and
        reset value.

        Returns
        -------
        :class:`Member`
            :pc:`Member(self, description, reset=reset)`
        """
        return Member(self, description, reset=reset)

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


#: A shortcut for importing :attr:`Flow.Out` as :data:`amaranth.lib.wiring.Out`.
Out = Flow.Out


#: A shortcut for importing :attr:`Flow.In` as :data:`amaranth.lib.wiring.In`.
In = Flow.In


@final
class Member:
    """Description of a signature member.

    This class is a discriminated union: its instances describe either a `port member` or
    a `signature member`, and accessing properties for the wrong kind of member raises
    an :exc:`AttributeError`.

    The class is created from a `description`: a :class:`Signature` instance (in which case
    the :class:`Member` is created as a signature member), or a :ref:`shape-like <lang-shapelike>`
    object (in which case it is created as a port member). After creation the :class:`Member`
    instance cannot be modified.

    When a :class:`Signal` is created from a description of a port member, the signal's reset value
    is taken from the member description. If this signal is never explicitly assigned a value, it
    will equal ``reset``.

    Although instances can be created directly, most often they will be created through
    :data:`In` and :data:`Out`, e.g. :pc:`In(unsigned(1))` or :pc:`Out(stream.Signature(RGBPixel))`.
    """
    def __init__(self, flow, description, *, reset=None, _dimensions=()):
        self._flow = flow
        self._description = description
        self._reset = reset
        self._dimensions = _dimensions

        # Check that the description is valid, and populate derived properties.
        if self.is_port:
            # Cast the description to a shape for typechecking, but keep the original
            # shape-castable so that it can be provided
            try:
                shape = Shape.cast(self._description)
            except TypeError as e:
                raise TypeError(f"Port member description must be a shape-castable object or "
                                f"a signature, not {description!r}") from e
            # This mirrors the logic that handles Signal(reset=).
            # TODO: We need a simpler way to check for "is this a valid constant initializer"
            if issubclass(type(self._description), ShapeCastable):
                try:
                    self._reset_as_const = Const.cast(self._description.const(self._reset))
                except Exception as e:
                    raise TypeError(f"Port member reset value {self._reset!r} is not a valid "
                                    f"constant initializer for {self._description}") from e
            else:
                try:
                    self._reset_as_const = Const.cast(reset or 0)
                except TypeError:
                    raise TypeError(f"Port member reset value {self._reset!r} is not a valid "
                                    f"constant initializer for {shape}")
        if self.is_signature:
            if self._reset is not None:
                raise ValueError(f"A signature member cannot have a reset value")

    def flip(self):
        """Flip the data flow of this member.

        Returns
        -------
        :class:`Member`
            A new :pc:`member` with :pc:`member.flow` equal to :pc:`self.flow.flip()`, and identical
            to :pc:`self` other than that.
        """
        return Member(self._flow.flip(), self._description, reset=self._reset,
                      _dimensions=self._dimensions)

    def array(self, *dimensions):
        """Add array dimensions to this member.

        The dimensions passed to this method are `prepended` to the existing dimensions.
        For example, :pc:`Out(1).array(2)` describes an array of 2 elements, whereas both
        :pc:`Out(1).array(2, 3)` and :pc:`Out(1).array(3).array(2)` both describe a two dimensional
        array of 2 by 3 elements.

        Dimensions are passed to :meth:`array` in the order in which they would be indexed.
        That is, :pc:`.array(x, y)` creates a member that can be indexed up to :pc:`[x-1][y-1]`.

        The :meth:`array` method is composable: calling :pc:`member.array(x)` describes an array of
        :pc:`x` members even if :pc:`member` was already an array.

        Returns
        -------
        :class:`Member`
            A new :pc:`member` with :pc:`member.dimensions` extended by :pc:`dimensions`, and
            identical to :pc:`self` other than that.
        """
        for dimension in dimensions:
            if not (isinstance(dimension, int) and dimension >= 0):
                raise TypeError(f"Member array dimensions must be non-negative integers, "
                                f"not {dimension!r}")
        return Member(self._flow, self._description, reset=self._reset,
                      _dimensions=(*dimensions, *self._dimensions))

    @property
    def flow(self):
        """Data flow of this member.

        Returns
        -------
        :class:`Flow`
        """
        return self._flow

    @property
    def is_port(self):
        """Whether this is a description of a port member.

        Returns
        -------
        :class:`bool`
            :pc:`True` if this is a description of a port member,
            :pc:`False` if this is a description of a signature member.
        """
        return not isinstance(self._description, Signature)

    @property
    def is_signature(self):
        """Whether this is a description of a signature member.

        Returns
        -------
        :class:`bool`
            :pc:`True` if this is a description of a signature member,
            :pc:`False` if this is a description of a port member.
        """
        return isinstance(self._description, Signature)

    @property
    def shape(self):
        """Shape of a port member.

        Returns
        -------
        :ref:`shape-like object <lang-shapelike>`
            The shape that was provided when constructing this :class:`Member`.

        Raises
        ------
        :exc:`AttributeError`
            If :pc:`self` describes a signature member.
        """
        if self.is_signature:
            raise AttributeError(f"A signature member does not have a shape")
        return self._description

    @property
    def reset(self):
        """Reset value of a port member.

        Returns
        -------
        :ref:`const-castable object <lang-constcasting>`
            The reset value that was provided when constructing this :class:`Member`.

        Raises
        ------
        :exc:`AttributeError`
            If :pc:`self` describes a signature member.
        """
        if self.is_signature:
            raise AttributeError(f"A signature member does not have a reset value")
        return self._reset

    @property
    def signature(self):
        """Signature of a signature member.

        Returns
        -------
        :class:`Signature`
            The signature that was provided when constructing this :class:`Member`.

        Raises
        ------
        :exc:`AttributeError`
            If :pc:`self` describes a port member.
        """
        if self.is_port:
            raise AttributeError(f"A port member does not have a signature")
        if self.flow == Out:
            return self._description
        if self.flow == In:
            return self._description.flip()
        assert False # :nocov:

    @property
    def dimensions(self):
        """Array dimensions.

        A member will usually have no dimensions; in this case it does not describe an array.
        A single dimension describes one-dimensional array, and so on.

        Returns
        -------
        :class:`tuple` of :class:`int`
            Dimensions, if any, of this member, from most to least major.
        """
        return self._dimensions

    def __eq__(self, other):
        return (type(other) is Member and
                self._flow == other._flow and
                self._description == other._description and
                self._reset == other._reset and
                self._dimensions == other._dimensions)

    def __repr__(self):
        reset_repr = dimensions_repr = ""
        if self._reset:
            reset_repr = f", reset={self._reset!r}"
        if self._dimensions:
            dimensions_repr = f".array({', '.join(map(str, self._dimensions))})"
        return f"{self._flow!r}({self._description!r}{reset_repr}){dimensions_repr}"


@final
class SignatureError(Exception):
    """
    This exception is raised when an invalid operation specific to signature manipulation is
    performed with :class:`SignatureMembers`, such as adding a member to a frozen signature.
    Other exceptions, such as :exc:`TypeError` or :exc:`NameError`, will still be raised where
    appropriate.
    """


# Inherits from Mapping and not MutableMapping because it's only mutable in a very limited way
# and most of the methods (except for `update`) added by MutableMapping are useless.
@final
class SignatureMembers(Mapping):
    """Mapping of signature member names to their descriptions.

    This container, a :class:`collections.abc.Mapping`, is used to implement the :pc:`members`
    attribute of signature objects.

    The keys in this container must be valid Python attribute names that are public (do not begin
    with an underscore. The values must be instances of :class:`Member`. The container is mutable
    in a restricted manner: new keys may be added, but existing keys may not be modified or removed.
    In addition, the container can be `frozen`, which disallows addition of new keys. Freezing
    a container recursively freezes the members of any signatures inside.

    In addition to the use of the superscript operator, multiple members can be added at once with
    the :pc:`+=` opreator.

    The :meth:`create` method converts this mapping into a mapping of names to signature members
    (signals and interface objects) by creating them from their descriptions. The created mapping
    can be used to populate an interface object.
    """

    def __init__(self, members=()):
        self._dict = dict()
        for name, member in dict(members).items():
            self._check_name(name)
            if type(member) is not Member:
                raise TypeError(f"Value {member!r} must be a member; "
                                f"did you mean In({member!r}) or Out({member!r})?")
            self._dict[name] = member

    def flip(self):
        """Flip the data flow of the members in this mapping.

        Returns
        -------
        :class:`FlippedSignatureMembers`
            Proxy collection :pc:`FlippedSignatureMembers(self)` that flips the data flow of
            the members that are accessed using it.
        """
        return FlippedSignatureMembers(self)

    def __eq__(self, other):
        """Compare the members in this and another mapping.

        Returns
        -------
        :class:`bool`
            :pc:`True` if the mappings contain the same key-value pairs, :pc:`False` otherwise.
        """
        return (isinstance(other, (SignatureMembers, FlippedSignatureMembers)) and
                list(sorted(self.flatten())) == list(sorted(other.flatten())))

    def __contains__(self, name):
        """Check whether a member with a given name exists.

        Returns
        -------
        :class:`bool`
        """
        return name in self._dict

    def _check_name(self, name):
        if not isinstance(name, str):
            raise TypeError(f"Member name must be a string, not {name!r}")
        if not re.match(r"^[A-Za-z][0-9A-Za-z_]*$", name):
            raise NameError(f"Member name '{name}' must be a valid, public Python attribute name")
        if name == "signature":
            raise NameError(f"Member name cannot be '{name}'")

    def __getitem__(self, name):
        """Retrieves the description of a member with a given name.

        Returns
        -------
        :class:`Member`

        Raises
        ------
        :exc:`TypeError`
            If :pc:`name` is not a string.
        :exc:`NameError`
            If :pc:`name` is not a valid, public Python attribute name.
        :exc:`SignatureError`
            If a member called :pc:`name` does not exist in the collection.
        """
        self._check_name(name)
        if name not in self._dict:
            raise SignatureError(f"Member '{name}' is not a part of the signature")
        return self._dict[name]

    def __setitem__(self, name, member):
        """Stub that forbids addition of members to the collection.

        Raises
        ------
        :exc:`SignatureError`
            Always.
        """
        raise SignatureError("Members cannot be added to a signature once constructed")

    def __delitem__(self, name):
        """Stub that forbids removal of members from the collection.

        Raises
        ------
        :exc:`SignatureError`
            Always.
        """
        raise SignatureError("Members cannot be removed from a signature")

    def __iter__(self):
        """Iterate through the names of members in the collection.

        Returns
        -------
        iterator of :class:`str`
            Names of members, in the order of insertion.
        """
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def flatten(self, *, path=()):
        """Recursively iterate through this collection.

        .. note::

            The :ref:`paths <wiring-path>` returned by this method and by :meth:`Signature.flatten`
            differ. This method yields a single result for each :class:`Member` in the collection,
            disregarding their dimensions:

            .. doctest::

                >>> sig = wiring.Signature({
                ...     "items": In(1).array(2)
                ... })
                >>> list(sig.members.flatten())
                [(('items',), In(1).array(2))]

            The :meth:`Signature.flatten` method yields multiple results for such a member; see
            the documentation for that method for an example.

        Returns
        -------
        iterator of (:class:`tuple` of :class:`str`, :class:`Member`)
            Pairs of :ref:`paths <wiring-path>` and the corresponding members. A path yielded by
            this method is a tuple of strings where each item is a key through which the item may
            be reached.
        """
        for name, member in self.items():
            yield ((*path, name), member)
            if member.is_signature:
                yield from member.signature.members.flatten(path=(*path, name))

    def create(self, *, path=None, src_loc_at=0):
        """Create members from their descriptions.

        For each port member, this function creates a :class:`Signal` with the shape and reset
        value taken from the member description, and the name constructed from
        the :ref:`paths <wiring-path>` to the member (by concatenating path items with a double
        underscore, ``__``).

        For each signature member, this function calls :meth:`Signature.create` for that signature.
        The resulting object can have any type if a :class:`Signature` subclass overrides
        the :class:`create` method.

        If the member description includes dimensions, in each case, instead of a single member,
        a :class:`list` of members is created for each dimension. (That is, for a single dimension
        a list of members is returned, for two dimensions a list of lists is returned, and so on.)

        Returns
        -------
        dict of :class:`str` to :ref:`value-like <lang-valuelike>` or interface object or a potentially nested list of these
            Mapping of names to actual signature members.
        """
        if path is None:
            path = (tracer.get_var_name(depth=2 + src_loc_at, default="$signature"),)
        attrs = {}
        for name, member in self.items():
            def create_value(path, *, src_loc_at):
                if member.is_port:
                    return Signal(member.shape, reset=member.reset, src_loc_at=1 + src_loc_at,
                                  name="__".join(str(item) for item in path))
                if member.is_signature:
                    return member.signature.create(path=path, src_loc_at=1 + src_loc_at)
                assert False # :nocov:
            def create_dimensions(dimensions, *, path, src_loc_at):
                if not dimensions:
                    return create_value(path, src_loc_at=1 + src_loc_at)
                dimension, *rest_of_dimensions = dimensions
                return [create_dimensions(rest_of_dimensions, path=(*path, index),
                                          src_loc_at=1 + src_loc_at)
                        for index in range(dimension)]
            attrs[name] = create_dimensions(member.dimensions, path=(*path, name),
                                            src_loc_at=1 + src_loc_at)
        return attrs

    def __repr__(self):
        return f"SignatureMembers({self._dict})"


@final
class FlippedSignatureMembers(Mapping):
    """Mapping of signature member names to their descriptions, with the directions flipped.

    Although an instance of :class:`FlippedSignatureMembers` could be created directly, it will
    be usually created by a call to :meth:`SignatureMembers.flip`.

    This container is a wrapper around :class:`SignatureMembers` that contains the same members
    as the inner mapping, but flips their data flow when they are accessed. For example:

    .. testcode::

        members = wiring.SignatureMembers({"foo": Out(1)})

        flipped_members = members.flip()
        assert flipped_members["foo"].flow == In

    This class implements the same methods, with the same functionality (other than the flipping of
    the data flow), as the :class:`SignatureMembers` class; see the documentation for that class
    for details.
    """

    def __init__(self, unflipped):
        self.__unflipped = unflipped

    def flip(self):
        """
        Flips this mapping back to the original one.

        Returns
        -------
        :class:`SignatureMembers`
            :pc:`unflipped`
        """
        return self.__unflipped

    # See the note below.
    __eq__ = SignatureMembers.__eq__

    def __contains__(self, name):
        return name in self.__unflipped

    def __getitem__(self, name):
        return self.__unflipped.__getitem__(name).flip()

    def __setitem__(self, name, member):
        self.__unflipped.__setitem__(name, member.flip())

    def __delitem__(self, name):
        self.__unflipped.__delitem__(name)

    def __iter__(self):
        return self.__unflipped.__iter__()

    def __len__(self):
        return self.__unflipped.__len__()

    # These methods do not access instance variables and so their implementation can be shared
    # between the normal and the flipped member collections.
    flatten = SignatureMembers.flatten
    create = SignatureMembers.create

    def __repr__(self):
        return f"{self.__unflipped!r}.flip()"


def _format_path(path):
    first, *rest = path
    if isinstance(first, int):
        # only happens in connect()
        chunks = [f"arg{first}"]
    else:
        chunks = [first]
    for item in rest:
        if isinstance(item, int):
            chunks.append(f"[{item}]")
        else:
            chunks.append(f".{item}")
    return f"'{''.join(chunks)}'"


def _traverse_path(path, obj):
    first, *rest = path
    obj = obj[first]
    for item in rest:
        if isinstance(item, int):
            obj = obj[item]
        else:
            obj = getattr(obj, item)
    return obj


def _format_shape(shape):
    if type(shape) is Shape:
        return f"{shape}"
    if isinstance(shape, int):
        return f"{Shape.cast(shape)}"
    return f"{Shape.cast(shape)} ({shape!r})"


class SignatureMeta(type):
    """Metaclass for :class:`Signature` that makes :class:`FlippedSignature` its
    'virtual subclass'.

    The object returned by :meth:`Signature.flip` is an instance of :class:`FlippedSignature`.
    It implements all of the methods :class:`Signature` has, and for subclasses of
    :class:`Signature`, it implements all of the methods defined on the subclass as well.
    This makes it effectively a subtype of :class:`Signature` (or a derived class of it), but this
    relationship is not captured by the Python type system: :class:`FlippedSignature` only has
    :class:`object` as its base class.

    This metaclass extends :func:`issubclass` and :func:`isinstance` so that they take into
    account the subtyping relationship between :class:`Signature` and :class:`FlippedSignature`,
    described below.
    """

    def __subclasscheck__(cls, subclass):
        """
        Override of :pc:`issubclass(cls, Signature)`.

        In addition to the standard behavior of :func:`issubclass`, this override makes
        :class:`FlippedSignature` a subclass of :class:`Signature` or any of its subclasses.
        """

        # `FlippedSignature` is a subclass of `Signature` or any of its subclasses because all of
        # them may return a Liskov-compatible instance of it from `self.flip()`.
        if subclass is FlippedSignature:
            return True
        return super().__subclasscheck__(subclass)

    def __instancecheck__(cls, instance):
        """
        Override of :pc:`isinstance(obj, Signature)`.

        In addition to the standard behavior of :func:`isinstance`, this override makes
        :pc:`isinstance(obj, cls)` act as :pc:`isinstance(obj.flip(), cls)` where
        :pc:`obj` is an instance of :class:`FlippedSignature`.
        """

        # `FlippedSignature` is an instance of a `Signature` or its subclass if the unflipped
        # object is.
        if type(instance) is FlippedSignature:
            return super().__instancecheck__(instance.flip())
        return super().__instancecheck__(instance)


class Signature(metaclass=SignatureMeta):
    """Description of an interface object.

    An interface object is a Python object that has a :pc:`signature` attribute containing
    a :class:`Signature` object, as well as an attribute for every member of its signature.
    Signatures and interface objects are tightly linked: an interface object can be created out
    of a signature, and the signature is used when :func:`connect` ing two interface objects
    together. See the :ref:`introduction to interfaces <wiring-intro1>` for a more detailed
    explanation of why this is useful.

    :class:`Signature` can be used as a base class to define :ref:`customized <wiring-customizing>`
    signatures and interface objects.

    .. important::

        :class:`Signature` objects are immutable. Classes inheriting from :class:`Signature` must
        ensure this remains the case when additional functionality is added.
    """

    def __init__(self, members):
        self.__members = SignatureMembers(members)

    def flip(self):
        """Flip the data flow of the members in this signature.

        Returns
        -------
        :class:`FlippedSignature`
            Proxy object :pc:`FlippedSignature(self)` that flips the data flow of the attributes
            corresponding to the members that are accessed using it.

            See the documentation for the :class:`FlippedSignature` class for a detailed discussion
            of how this proxy object works.
        """
        return FlippedSignature(self)

    @property
    def members(self):
        """Members in this signature.

        Returns
        -------
        :class:`SignatureMembers`
        """
        return self.__members

    def __eq__(self, other):
        """Compare this signature with another.

        The behavior of this operator depends on the types of the arguments. If both :pc:`self`
        and :pc:`other` are instances of the base :class:`Signature` class, they are compared
        structurally (the result is :pc:`self.members == other.members`); otherwise they are
        compared by identity (the result is :pc:`self is other`).

        Subclasses of :class:`Signature` are expected to override this method to take into account
        the specifics of the domain. If the subclass has additional properties that do not influence
        the :attr:`members` dictionary but nevertheless make its instance incompatible with other
        instances (for example, whether the feedback is combinational or registered),
        the overridden method must take that into account.

        Returns
        -------
        :class:`bool`
        """
        other_unflipped = other.flip() if type(other) is FlippedSignature else other
        if type(self) is type(other_unflipped) is Signature:
            # If both `self` and `other` are anonymous signatures, compare structurally.
            return self.members == other.members
        else:
            # Otherwise (if `self` refers to a derived class) compare by identity. This will
            # usually be overridden in a derived class.
            return self is other

    def flatten(self, obj):
        """Recursively iterate through this signature, retrieving member values from an interface
        object.

        .. note::

            The :ref:`paths <wiring-path>` returned by this method and by
            :meth:`SignatureMembers.flatten` differ. This method yield several results for each
            :class:`Member` in the collection that has a dimension:

            .. doctest::
                :options: +NORMALIZE_WHITESPACE

                >>> sig = wiring.Signature({
                ...     "items": In(1).array(2)
                ... })
                >>> obj = sig.create()
                >>> list(sig.flatten(obj))
                [(('items', 0), In(1), (sig obj__items__0)),
                 (('items', 1), In(1), (sig obj__items__1))]

            The :meth:`SignatureMembers.flatten` method yields one result for such a member; see
            the documentation for that method for an example.

        Returns
        -------
        iterator of (:class:`tuple` of :class:`str` or :class:`int`, :class:`Flow`, :ref:`value-like <lang-valuelike>`)
            Tuples of :ref:`paths <wiring-path>`, flow, and the corresponding member values. A path
            yielded by this method is a tuple of strings or integers where each item is an attribute
            name or index (correspondingly) using which the member value was retrieved.
        """
        for name, member in self.members.items():
            path = (name,)
            value = getattr(obj, name)

            def iter_member(value, *, path):
                if member.is_port:
                    yield path, Member(member.flow, member.shape, reset=member.reset), value
                elif member.is_signature:
                    for sub_path, sub_member, sub_value in member.signature.flatten(value):
                        if member.flow == In:
                            sub_member = sub_member.flip()
                        yield ((*path, *sub_path), sub_member, sub_value)
                else:
                    assert False # :nocov:

            def iter_dimensions(value, dimensions, *, path):
                if not dimensions:
                    yield from iter_member(value, path=path)
                else:
                    dimension, *rest_of_dimensions = dimensions
                    for index in range(dimension):
                        yield from iter_dimensions(value[index], rest_of_dimensions,
                                                   path=(*path, index))

            yield from iter_dimensions(value, dimensions=member.dimensions, path=path)

    def is_compliant(self, obj, *, reasons=None, path=("obj",)):
        """Check whether an object matches the description in this signature.

        This module places few restrictions on what an interface object may be; it does not
        prescribe a specific base class or a specific way of constructing the object, only
        the values that its attributes should have. This method ensures consistency between
        the signature and the interface object, checking every aspect of the provided interface
        object for compliance with the signature.

        It verifies that:

        * :pc:`obj` has a :pc:`signature` attribute whose value a :class:`Signature` instance
          such that ``self == obj.signature``;
        * for each member, :pc:`obj` has an attribute with the same name, whose value:

          * for members with :meth:`dimensions <Member.dimensions>` specified, contains a list or
            a tuple (or several levels of nested lists or tuples, for multiple dimensions)
            satisfying the requirements below;
          * for port members, is a :ref:`value-like <lang-valuelike>` object casting to
            a :class:`Signal` or a :class:`Const` whose width and signedness is the same as that
            of the member, and (in case of a :class:`Signal`) which is not reset-less and whose
            reset value is that of the member;
          * for signature members, matches the description in the signature as verified by
            :meth:`Signature.is_compliant`.

        If the verification fails, this method reports the reason(s) by filling the :pc:`reasons`
        container. These reasons are intended to be human-readable: more than one reason may be
        reported but only in cases where this is helpful (e.g. the same error message will not
        repeat 10 times for each of the 10 ports in a list).

        Arguments
        ---------
        reasons : :class:`list` or :pc:`None`
            If provided, a container that receives diagnostic messages.
        path : :class:`tuple` of :class:`str`
            The :ref:`path <wiring-path>` to :pc:`obj`. Could be set to improve diagnostic
            messages if :pc:`obj` is nested within another object, or for clarity.

        Returns
        -------
        :class:`bool`
            :pc:`True` if :pc:`obj` matches the description in this signature, :pc:`False`
            otherwise. If :pc:`False` and :pc:`reasons` was not :pc:`None`, it will contain
            a detailed explanation why.
        """

        if not hasattr(obj, "signature"):
            if reasons is not None:
                reasons.append(f"{_format_path(path)} does not have an attribute 'signature'")
            return False
        if not isinstance(obj.signature, Signature):
            if reasons is not None:
                reasons.append(f"{_format_path(path + ('signature',))} is expected to be "
                               f"a signature, but it is a {obj.signature!r}")
            return False
        if self != obj.signature:
            if reasons is not None:
                reasons.append(f"{_format_path(path + ('signature',))} is expected to be equal "
                               f"to this signature, {self!r}, but it is a {obj.signature!r}")
            return False

        def check_attr_value(member, attr_value, *, path):
            if member.is_port:
                try:
                    attr_value_cast = Value.cast(attr_value)
                except:
                    if reasons is not None:
                        reasons.append(f"{_format_path(path)} is not a value-castable object, "
                                       f"but {attr_value!r}")
                    return False
                if not isinstance(attr_value_cast, (Signal, Const)):
                    if reasons is not None:
                        reasons.append(f"{_format_path(path)} is neither a signal nor a constant, "
                                       f"but {attr_value_cast!r}")
                    return False
                attr_shape = attr_value_cast.shape()
                if Shape.cast(attr_shape) != Shape.cast(member.shape):
                    if reasons is not None:
                        reasons.append(f"{_format_path(path)} is expected to have "
                                       f"the shape {_format_shape(member.shape)}, but it has "
                                       f"the shape {_format_shape(attr_shape)}")
                    return False
                if isinstance(attr_value_cast, Signal):
                    if attr_value_cast.reset != member._reset_as_const.value:
                        if reasons is not None:
                            reasons.append(f"{_format_path(path)} is expected to have "
                                           f"the reset value {member.reset!r}, but it has "
                                           f"the reset value {attr_value_cast.reset!r}")
                        return False
                    if attr_value_cast.reset_less:
                        if reasons is not None:
                            reasons.append(f"{_format_path(path)} is expected to not be reset-less")
                        return False
                return True
            if member.is_signature:
                return member.signature.is_compliant(attr_value, reasons=reasons, path=path)
            assert False # :nocov:

        def check_dimensions(member, attr_value, dimensions, *, path):
            if not dimensions:
                return check_attr_value(member, attr_value, path=path)

            dimension, *rest_of_dimensions = dimensions
            if not isinstance(attr_value, (tuple, list)):
                if reasons is not None:
                    reasons.append(f"{_format_path(path)} is expected to be a tuple or a list, "
                                   f"but it is a {attr_value!r}")
                return False
            if len(attr_value) != dimension:
                if reasons is not None:
                    reasons.append(f"{_format_path(path)} is expected to have dimension "
                                   f"{dimension}, but its length is {len(attr_value)}")
                return False

            result = True
            for index in range(dimension):
                if not check_dimensions(member, attr_value[index], rest_of_dimensions,
                                        path=(*path, index)):
                    result = False
                    if reasons is None:
                        break # short cicruit if detailed error message isn't required
            return result

        result = True
        for attr_name, member in self.members.items():
            try:
                attr_value = getattr(obj, attr_name)
            except AttributeError:
                if reasons is None:
                    return False
                else:
                    reasons.append(f"{_format_path(path)} does not have an attribute "
                                   f"{attr_name!r}")
                    result = False
                    continue
            if not check_dimensions(member, attr_value, member.dimensions, path=(*path, attr_name)):
                if reasons is None:
                    return False
                else:
                    # `reasons` was mutated by check_dimensions()
                    result = False
                    continue
        return result

    def create(self, *, path=None, src_loc_at=0):
        """Create an interface object from this signature.

        The default :meth:`Signature.create` implementation consists of one line:

        .. code::

            def create(self, *, path=None, src_loc_at=0):
                return PureInterface(self, path=path, src_loc_at=1 + src_loc_at)

        This implementation creates an interface object from this signature that serves purely
        as a container for the attributes corresponding to the signature members, and implements
        no behavior. Such an implementation is sufficient for signatures created ad-hoc using
        the :pc:`Signature({ ... })` constructor as well as simple signature subclasses.

        When defining a :class:`Signature` subclass that needs to customize the behavior of
        the created interface objects, override this method with a similar implementation
        that references the class of your custom interface object:

        .. testcode::

            class CustomSignature(wiring.Signature):
                def create(self, *, path=None, src_loc_at=0):
                    return CustomInterface(self, path=path, src_loc_at=1 + src_loc_at)

            class CustomInterface(wiring.PureInterface):
                @property
                def my_property(self):
                    ...

        The :pc:`path` and :pc:`src_loc_at` arguments are necessary to ensure the generated signals
        have informative names and accurate source location information.

        The custom :meth:`create` method may take positional or keyword arguments in addition to
        the two listed above. Such arguments must have a default value, because
        the :meth:`SignatureMembers.create` method will call the :meth:`Signature.create` member
        without these additional arguments when this signature is a member of another signature.
        """
        return PureInterface(self, path=path, src_loc_at=1 + src_loc_at)

    def __repr__(self):
        if type(self) is Signature:
            return f"Signature({dict(self.members.items())})"
        return super().__repr__()


def _gettypeattr(obj, attr):
    # Resolve the attribute on the object's class, without triggering the descriptor protocol for
    # attributes that are class methods, etc.
    for cls in type(obj).__mro__:
        try:
            return cls.__dict__[attr]
        except KeyError:
            pass
    # Call `getattr` in case there is `__getattr__` on the metaclass, or just to generate
    # an `AttributeError` with the standard message.
    return getattr(type(obj), attr)


# To simplify implementation and reduce API surface area `FlippedSignature` is made final. This
# restriction could be lifted if there is a compelling use case.
@final
class FlippedSignature:
    """Description of an interface object, with the members' directions flipped.

    Although an instance of :class:`FlippedSignature` could be created directly, it will be usually
    created by a call to :meth:`Signature.flip`.

    This proxy is a wrapper around :class:`Signature` that contains the same description as
    the inner mapping, but flips the members' data flow when they are accessed. It is useful
    because :class:`Signature` objects are mutable and may include custom behavior, and if one was
    copied (rather than wrapped) by :meth:`Signature.flip`, the wrong object would be mutated, and
    custom behavior would be unavailable.

    For example:

    .. testcode::

        sig = wiring.Signature({"foo": Out(1)})

        flipped_sig = sig.flip()
        assert flipped_sig.members["foo"].flow == In

        sig.attr = 1
        assert flipped_sig.attr == 1
        flipped_sig.attr += 1
        assert sig.attr == flipped_sig.attr == 2

    This class implements the same methods, with the same functionality (other than the flipping of
    the members' data flow), as the :class:`Signature` class; see the documentation for that class
    for details.

    It is not possible to inherit from :class:`FlippedSignature` and :meth:`Signature.flip` must not
    be overridden. If a :class:`Signature` subclass defines a method and this method is called on
    a flipped instance of the subclass, it receives the flipped instance as its :pc:`self` argument.
    To distinguish being called on the flipped instance from being called on the unflipped one, use
    :pc:`isinstance(self, FlippedSignature)`:

    .. testcode::

        class SignatureKnowsWhenFlipped(wiring.Signature):
            @property
            def is_flipped(self):
                return isinstance(self, wiring.FlippedSignature)

        sig = SignatureKnowsWhenFlipped({})
        assert sig.is_flipped == False
        assert sig.flip().is_flipped == True
    """
    def __init__(self, signature):
        object.__setattr__(self, "_FlippedSignature__unflipped", signature)

    def flip(self):
        """
        Flips this signature back to the original one.

        Returns
        -------
        :class:`Signature`
            :pc:`unflipped`
        """
        return self.__unflipped

    # Flipped version of :meth:`Signature.members`. Documented only on :class:`Signature`.
    @property
    def members(self):
        return FlippedSignatureMembers(self.__unflipped.members)

    def __eq__(self, other):
        if type(other) is FlippedSignature:
            # Trivial case.
            return self.flip() == other.flip()
        else:
            # Delegate comparisons back to Signature (or its descendant) by flipping the arguments;
            # equality must be reflexive but the implementation of `__eq__` need not be, and we can
            # take advantage of it here. This is done by returning `NotImplemented`, otherwise if
            # the other object cannot be compared to a `FlippedSignature` either this will result
            # in infinite recursion.
            return NotImplemented

    # This method does not access instance variables and so its implementation can be shared
    # between the normal and the flipped member collections.
    is_compliant = Signature.is_compliant

    # Because we would like to forward attribute access (other than what is explicitly overridden)
    # to the unflipped signature, including access via e.g. @property-decorated functions, we have
    # to reimplement the Python decorator protocol here. Note that in all of these functions, there
    # are two possible exits via `except AttributeError`: from `getattr` and from `.__get__()`.

    def __getattr__(self, name):
        """Retrieves attribute or method :pc:`name` of the unflipped signature.

        Performs :pc:`getattr(unflipped, name)`, ensuring that, if :pc:`name` refers to a property
        getter or a method, its :pc:`self` argument receives the *flipped* signature. A class
        method's :pc:`cls` argument receives the class of the *unflipped* signature, as usual.
        """
        try: # descriptor first
            return _gettypeattr(self.__unflipped, name).__get__(self, type(self.__unflipped))
        except AttributeError:
            return getattr(self.__unflipped, name)

    def __setattr__(self, name, value):
        """Assigns attribute :pc:`name` of the unflipped signature to ``value``.

        Performs :pc:`setattr(unflipped, name, value)`, ensuring that, if :pc:`name` refers to
        a property setter, its :pc:`self` argument receives the flipped signature.
        """
        try: # descriptor first
            _gettypeattr(self.__unflipped, name).__set__(self, value)
        except AttributeError:
            setattr(self.__unflipped, name, value)

    def __delattr__(self, name):
        """Removes attribute :pc:`name` of the unflipped signature.

        Performs :pc:`delattr(unflipped, name)`, ensuring that, if :pc:`name` refers to a property
        deleter, its :pc:`self` argument receives the flipped signature.
        """
        try: # descriptor first
            _gettypeattr(self.__unflipped, name).__delete__(self)
        except AttributeError:
            delattr(self.__unflipped, name)

    # Flipped version of :meth:`Signature.create`. Documented only on :class:`Signature`.
    def create(self, *args, path=None, src_loc_at=0, **kwargs):
        return flipped(self.__unflipped.create(*args, path=path, src_loc_at=1 + src_loc_at,
                                               **kwargs))

    def __repr__(self):
        return f"{self.__unflipped!r}.flip()"


class PureInterface:
    """A helper for constructing ad-hoc interfaces.

    The :class:`PureInterface` helper primarily exists to be used by the default implementation of
    :meth:`Signature.create`, but it can also be used in any other context where an interface
    object needs to be created without the overhead of defining a class for it.

    .. important::

        Any object can be an interface object; it only needs a :pc:`signature` property containing
        a compliant signature. It is **not** necessary to use :class:`PureInterface` in order to
        create an interface object, but it may be used either directly or as a base class whenever
        it is convenient to do so.
    """

    def __init__(self, signature, *, path=None, src_loc_at=0):
        """Create attributes from a signature.

        The sole method defined by this helper is its constructor, which only defines
        the :pc:`self.signature` attribute as well as the attributes created from the signature
        members:

        .. code::

            def __init__(self, signature, *, path):
                self.__dict__.update({
                    "signature": signature,
                    **signature.members.create(path=path)
                })

        .. note::

            This implementation can be copied and reused in interface objects that *do* include
            custom behavior, if the signature serves as the source of truth for attributes
            corresponding to its members. Although it is less repetitive, this approach can confuse
            IDEs and type checkers.
        """
        self.__dict__.update({
            "signature": signature,
            **signature.members.create(path=path, src_loc_at=1 + src_loc_at)
        })

    def __repr__(self):
        attrs = ''.join(f", {name}={value!r}"
                        for name, value in self.__dict__.items()
                        if name != "signature")
        return f'<{type(self).__name__}: {self.signature}{attrs}>'


# To reduce API surface area `FlippedInterface` is made final. This restriction could be lifted
# if there is a compelling use case.
@final
class FlippedInterface:
    """An interface object, with its members' directions flipped.

    An instance of :class:`FlippedInterface` should only be created by calling :func:`flipped`,
    which ensures that a :pc:`FlippedInterface(FlippedInterface(...))` object is never created.

    This proxy wraps any interface object and forwards attribute and method access to the wrapped
    interface object while flipping its signature and the values of any attributes corresponding to
    interface members. It is useful because interface objects may be mutable or include custom
    behavior, and explicitly keeping track of whether the interface object is flipped would be very
    burdensome.

    For example:

    .. testcode::

        intf = wiring.PureInterface(wiring.Signature({"foo": Out(1)}), path=())

        flipped_intf = wiring.flipped(intf)
        assert flipped_intf.signature.members["foo"].flow == In

        intf.attr = 1
        assert flipped_intf.attr == 1
        flipped_intf.attr += 1
        assert intf.attr == flipped_intf.attr == 2

    It is not possible to inherit from :class:`FlippedInterface`. If an interface object class
    defines a method or a property and it is called on the flipped interface object, the method
    receives the flipped interface object as its :pc:`self` argument. To distinguish being called
    on the flipped interface object from being called on the unflipped one, use
    :pc:`isinstance(self, FlippedInterface)`:

    .. testcode::

        class InterfaceKnowsWhenFlipped:
            signature = wiring.Signature({})

            @property
            def is_flipped(self):
                return isinstance(self, wiring.FlippedInterface)

        intf = InterfaceKnowsWhenFlipped()
        assert intf.is_flipped == False
        assert wiring.flipped(intf).is_flipped == True
    """
    def __init__(self, interface):
        if not (hasattr(interface, "signature") and isinstance(interface.signature, Signature)):
            raise TypeError(f"flipped() can only flip an interface object, not {interface!r}")
        object.__setattr__(self, "_FlippedInterface__unflipped", interface)

    @property
    def signature(self):
        """Signature of the flipped interface.

        Returns
        -------
        Signature
            :pc:`unflipped.signature.flip()`
        """
        return self.__unflipped.signature.flip()

    def __eq__(self, other):
        """Compare this flipped interface with another.

        Returns
        -------
        bool
            :pc:`True` if :pc:`other` is an instance :pc:`FlippedInterface(other_unflipped)` where
            :pc:`unflipped == other_unflipped`, :pc:`False` otherwise.
        """
        return type(self) is type(other) and self.__unflipped == other.__unflipped

    # See the note in `FlippedSignature`. In addition, these accessors also handle flipping of
    # an interface member.

    def __getattr__(self, name):
        """Retrieves attribute or method :pc:`name` of the unflipped interface.

        Performs :pc:`getattr(unflipped, name)`, with the following caveats:

        1. If :pc:`name` refers to a signature member, the returned interface object is flipped.
        2. If :pc:`name` refers to a property getter or a method, its :pc:`self` argument receives
           the *flipped* interface. A class method's :pc:`cls` argument receives the class of
           the *unflipped* interface, as usual.
        """
        if (name in self.__unflipped.signature.members and
                self.__unflipped.signature.members[name].is_signature):
            return flipped(getattr(self.__unflipped, name))
        else:
            try: # descriptor first
                return _gettypeattr(self.__unflipped, name).__get__(self, type(self.__unflipped))
            except AttributeError:
                return getattr(self.__unflipped, name)

    def __setattr__(self, name, value):
        """Assigns attribute :pc:`name` of the unflipped interface to ``value``.

        Performs :pc:`setattr(unflipped, name, value)`, with the following caveats:

        1. If :pc:`name` refers to a signature member, the assigned interface object is flipped.
        2. If :pc:`name` refers to a property setter, its :pc:`self` argument receives the flipped
           interface.
        """
        if (name in self.__unflipped.signature.members and
                self.__unflipped.signature.members[name].is_signature):
            setattr(self.__unflipped, name, flipped(value))
        else:
            try: # descriptor first
                _gettypeattr(self.__unflipped, name).__set__(self, value)
            except AttributeError:
                setattr(self.__unflipped, name, value)

    def __delattr__(self, name):
        """Removes attribute :pc:`name` of the unflipped interface.

        Performs :pc:`delattr(unflipped, name)`, ensuring that, if :pc:`name` refers to a property
        deleter, its :pc:`self` argument receives the flipped interface.
        """
        try: # descriptor first
            _gettypeattr(self.__unflipped, name).__delete__(self)
        except AttributeError:
            delattr(self.__unflipped, name)

    def __repr__(self):
        return f"flipped({self.__unflipped!r})"


def flipped(interface):
    """
    Flip the data flow of the members of the interface object :pc:`interface`.

    If an interface object is flipped twice, returns the original object:
    :pc:`flipped(flipped(interface)) is interface`. Otherwise, wraps :pc:`interface` in
    a :class:`FlippedInterface` proxy object that flips the directions of its members.

    See the documentation for the :class:`FlippedInterface` class for a detailed discussion of how
    this proxy object works.
    """
    if type(interface) is FlippedInterface:
        return interface._FlippedInterface__unflipped
    else:
        return FlippedInterface(interface)


@final
class ConnectionError(Exception):
    """Exception raised when the :func:`connect` function is requested to perform an impossible,
    meaningless, or forbidden connection."""


def connect(m, *args, **kwargs):
    """Connect interface objects to each other.

    This function creates connections between ports of several interface objects. (Any number of
    interface objects may be provided; in most cases it is two.)

    The connections can be made only if all of the objects satisfy a number of requirements:

    * Every interface object must have the same set of port members, and they must have the same
      :meth:`dimensions <Member.dimensions>`.
    * For each path, the port members of every interface object must have the same width and reset
      value (for port members corresponding to signals) or constant value (for port members
      corresponding to constants). Signedness may differ.
    * For each path, at most one interface object must have the corresponding port member be
      an output.
    * For a given path, if any of the interface objects has an input port member corresponding
      to a constant value, then the rest of the interface objects must have output port members
      corresponding to the same constant value.

    For example, if :pc:`obj1` is being connected to :pc:`obj2` and :pc:`obj3`, and :pc:`obj1.a.b`
    is an output, then :pc:`obj2.a.b` and :pc:`obj2.a.b` must exist and be inputs. If :pc:`obj2.c`
    is an input and its value is :pc:`Const(1)`, then :pc:`obj1.c` and :pc:`obj3.c` must be outputs
    whose value is also :pc:`Const(1)`. If no ports besides :pc:`obj1.a.b` and :pc:`obj1.c` exist,
    then no ports except for those two must exist on :pc:`obj2` and :pc:`obj3` either.

    Once it is determined that the interface objects can be connected, this function performs
    an equivalent of:

    .. code::

        m.d.comb += [
            in1.eq(out1),
            in2.eq(out1),
            ...
        ]

    Where :pc:`out1` is an output and :pc:`in1`, :pc:`in2`, ... are the inputs that have the same
    path. (If no interface object has an output for a given path, **no connection at all** is made.)

    The positions (within :pc:`args`) or names (within :pc:`kwargs`) of the arguments do not affect
    the connections that are made. There is no difference in behavior between :pc:`connect(m, a, b)`
    and :pc:`connect(m, b, a)` or :pc:`connect(m, arbiter=a, decoder=b)`. The names of the keyword
    arguments serve only a documentation purpose: they clarify the diagnostic messages when
    a connection cannot be made.
    """

    objects = {
        **{index:   arg for index,   arg in enumerate(args)},
        **{keyword: arg for keyword, arg in kwargs.items()}
    }

    # Extract signatures from arguments.
    signatures = {}
    for handle, obj in objects.items():
        if not hasattr(obj, "signature"):
            raise AttributeError(f"Argument {handle!r} must have a 'signature' attribute")
        if not isinstance(obj.signature, Signature):
            raise TypeError(f"Signature of argument {handle!r} must be a signature, "
                            f"not {obj.signature!r}")
        if not obj.signature.is_compliant(obj):
            reasons = []
            obj.signature.is_compliant(obj, reasons=reasons, path=(handle,))
            reasons_as_string = "".join("\n- " + reason for reason in reasons)
            raise ConnectionError(f"Argument {handle!r} does not match its signature:" +
                                  reasons_as_string)
        signatures[handle] = obj.signature

    # Collate signatures and build connections.
    flattens = {handle: iter(sorted(signature.members.flatten()))
                for handle, signature in signatures.items()}
    connections = []
    # Each iteration of the outer loop is intended to connect several (usually a pair) members
    # to each other, e.g. an out member `[0].a` to an in member `[1].a`. However, because we
    # do not just check signatures for equality (in order to improve diagnostics), it is possible
    # that we will find that in `[0]`, the first member is `a`, and in `[1]`, the first member
    # is completely unrelated `[b]`. Since the assumption that all signatures are equal, or even
    # of equal length, cannot be made, it is necessary to simultaneously iterate (like with `zip`)
    # the signature of every object being connected, making sure each set of next members is
    # compliant with each other.
    while True:
        # Classify the members by kind and flow: signature, In, Out. Flow of signature members is
        # implied in the flow of each port member, so the signature members are only classified
        # here to ensure they are not connected to port members.
        is_first = True
        sig_kind, out_kind, in_kind = [], [], []
        for handle, flattened_members in flattens.items():
            path_for_handle, member = next(flattened_members, (None, None))
            # First, ensure that the paths are equal (i.e. that the hierarchy matches for all of
            # the objects up to this point).
            if is_first:
                is_first = False
                first_path = path_for_handle
            else:
                first_handle = next(iter(flattens))
                if first_path != path_for_handle:
                    # The paths are inequal. It is ambiguous how exactly the diagnostic should be
                    # displayed, and the choices of which other member to use below is arbitrary.
                    # Signature members are iterated in ascending lexicographical order, so the path
                    # that sorts greater corresponds to the handle that's missing a member.
                    if (path_for_handle is None or
                            (first_path is not None and path_for_handle > first_path)):
                        first_path_as_string = _format_path(first_path)
                        raise ConnectionError(f"Member {first_path_as_string} is present in "
                                              f"{first_handle!r}, but not in {handle!r}")
                    if (first_path is None or
                            (path_for_handle is not None and path_for_handle < first_path)):
                        path_for_handle_as_string = _format_path(path_for_handle)
                        raise ConnectionError(f"Member {path_for_handle_as_string} is present in "
                                              f"{handle!r}, but not in {first_handle!r}")
                    assert False # :nocov:
            # If there is no actual member, the signature has been fully iterated through.
            # Other signatures may still have extraneous members, so continue iterating until
            # a diagnostic is returned.
            if member is None:
                continue
            # At this point we know the paths are equal, but the members can still have
            # incompliant flow, kind (signature or port), signature, or shape. Collect all of
            # these for later evaluation.
            if member.is_port:
                if member.flow == Out:
                    out_kind.append(((handle, *path_for_handle), member))
                if member.flow == In:
                    in_kind.append(((handle, *path_for_handle), member))
            if member.is_signature:
                sig_kind.append(((handle, *path_for_handle), member))
        # If there's no path and an error wasn't raised above, we're done!
        if first_path is None:
            break
        # At this point, valid possibilities are:
        # - All of the members are signature members. In this case, we move on to their contents,
        #   and ignore the signatures themselves.
        # - There are no signature members, and there is exactly one Out flow member. In this case,
        #   this member is connected to the remaining In members, of which there may be any amount.
        # All other cases must be rejected with a diagnostic.
        if sig_kind and (out_kind or in_kind):
            sig_member_paths_as_string = \
                ", ".join(_format_path(h) for h, m in sig_kind)
            port_member_paths_as_string = \
                ", ".join(_format_path(h) for h, m in out_kind + in_kind)
            raise ConnectionError(
                f"Cannot connect signature member(s) {sig_member_paths_as_string} with "
                f"port member(s) {port_member_paths_as_string}")
        if sig_kind:
            # There are no port members at this point; we're done with this path.
            continue
        # There are only port members after this point.
        is_first = True
        for (path, member) in in_kind + out_kind:
            member_shape = member.shape
            if is_first:
                is_first = False
                first_path = path
                first_member_shape = member.shape
                first_member_reset = member.reset
                first_member_reset_as_const = member._reset_as_const
                continue
            if Shape.cast(first_member_shape).width != Shape.cast(member_shape).width:
                raise ConnectionError(
                    f"Cannot connect the member {_format_path(first_path)} with shape "
                    f"{_format_shape(first_member_shape)} to the member {_format_path(path)} with "
                    f"shape {_format_shape(member_shape)} because the shape widths "
                    f"({Shape.cast(first_member_shape).width} and "
                    f"{Shape.cast(member_shape).width}) do not match")
            if first_member_reset_as_const.value != member._reset_as_const.value:
                raise ConnectionError(
                    f"Cannot connect together the member {_format_path(first_path)} with reset "
                    f"value {first_member_reset!r} and the member {_format_path(path)} with reset "
                    f"value {member.reset} because the reset values do not match")
        # If there are no Out members, there is nothing to connect. The In members, while not
        # explicitly connected, will stay at the same value since we ensured their reset values
        # are all identical.
        if len(out_kind) == 0:
            continue
        # Check that there is only one Out member. In the future we could extend connection to
        # handle wired-OR and wired-AND, and this check may go away.
        if len(out_kind) != 1:
            out_member_paths_as_string = \
                ", ".join(_format_path(h) for h, m in out_kind)
            raise ConnectionError(
                f"Cannot connect several output members {out_member_paths_as_string} together")
        # There is exactly one Out member after this point, and any amount of In members.
        # Traversing the paths to all of them should always succeed, since the signature check
        # at the beginning of `connect()` passed, and so should casting the result to a Value.
        (out_path, out_member), = out_kind
        for (in_path, in_member) in in_kind:
            def connect_value(*, out_path, in_path):
                in_value = Value.cast(_traverse_path(in_path, objects))
                out_value = Value.cast(_traverse_path(out_path, objects))
                assert type(in_value) in (Const, Signal)
                # If the input is a constant, only a constant may be connected to it. Ensure that
                # this is the case.
                if type(in_value) is Const:
                    # If the output is not a constant, the connection is illegal.
                    if type(out_value) is not Const:
                        raise ConnectionError(
                            f"Cannot connect input member {_format_path(in_path)} that has "
                            f"a constant value {in_value.value!r} to an output member "
                            f"{_format_path(out_path)} that has a varying value")
                    # If the output is a constant, the connection is legal only if the value is
                    # the same for both the input and the output.
                    if type(out_value) is Const and in_value.value != out_value.value:
                        raise ConnectionError(
                            f"Cannot connect input member {_format_path(in_path)} that has "
                            f"a constant value {in_value.value!r} to an output member "
                            f"{_format_path(out_path)} that has a different constant value "
                            f"{out_value.value!r}")
                    # We never actually connect anything to the constant input; we only ensure its
                    # value (which is constant) is consistent with a connection that would have
                    # been made.
                    return
                # A connection that is made at this point is guaranteed to be valid.
                connections.append(in_value.eq(out_value))
            def connect_dimensions(dimensions, *, out_path, in_path):
                if not dimensions:
                    return connect_value(out_path=out_path, in_path=in_path)
                dimension, *rest_of_dimensions = dimensions
                for index in range(dimension):
                    connect_dimensions(rest_of_dimensions,
                                       out_path=(*out_path, index), in_path=(*in_path, index))
            assert out_member.dimensions == in_member.dimensions
            connect_dimensions(out_member.dimensions, out_path=out_path, in_path=in_path)
    # Now that we know all of the connections are legal, add them to the module. This is done
    # instead of returning them because adding them to a non-comb domain would subtly violate
    # assumptions that `connect()` is intended to provide.
    m.d.comb += connections


class Component(Elaboratable):
    """Base class for elaboratable interface objects.

    A component is an :class:`Elaboratable` whose interaction with other parts of the design is
    defined by its signature. Most if not all elaboratables in idiomatic Amaranth code should be
    components, as the signature clarifies the direction of data flow at their boundary. See
    the :ref:`introduction to interfaces <wiring-intro1>` section for a practical guide to defining
    and using components.

    There are two ways to define a component. If all instances of a component have the same
    signature, it can be defined using :term:`variable annotations <python:variable annotation>`:

    .. testcode::

        class FixedComponent(wiring.Component):
            en: In(1)
            data: Out(8)

    The variable annotations are collected by the constructor :meth:`Component.__init__`. Only
    public (not starting with ``_``) annotations with :class:`In <Member>` or :class:`Out <Member>`
    objects are considered; all other annotations are ignored under the assumption that they are
    interpreted by some other tool.

    It is possible to use inheritance to extend a component: the component's signature is composed
    from the variable annotations in the class that is being constructed as well as all of its
    base classes. It is an error to have more than one variable annotation for the same attribute.

    If different instances of a component may need to have different signatures, variable
    annotations cannot be used. In this case, the constructor should be overridden, and
    the computed signature members should be provided to the superclass constructor:

    .. testcode::

        class ParametricComponent(wiring.Component):
            def __init__(self, data_width):
                super().__init__({
                    "en": In(1),
                    "data": Out(data_width)
                })

    It is also possible to pass a :class:`Signature` instance to the superclass constructor.

    Aside from initializing the :attr:`signature` attribute, the :meth:`Component.__init__`
    constructor creates attributes corresponding to all of the members defined in the signature.
    If an attribute with the same name as that of a member already exists, an error is raied.

    Raises
    ------
    :exc:`TypeError`
        If the :pc:`signature` object is neither a :class:`Signature` nor a :class:`dict`.
        If neither variable annotations nor the :pc:`signature` argument are present, or if
        both are present.
    :exc:`NameError`
        If a name conflict is detected between two variable annotations, or between a member
        and an existing attribute.
    """
    def __init__(self, signature=None):
        cls = type(self)
        members = {}
        for base in reversed(cls.mro()[:cls.mro().index(Component)]):
            for name, annot in base.__dict__.get("__annotations__", {}).items():
                if name.startswith("_"):
                    continue
                if type(annot) is Member:
                    if name in members:
                        raise NameError(
                            f"Member '{name}' is redefined in {base.__module__}.{base.__qualname__}")
                    members[name] = annot
        if not members:
            if signature is None:
                raise TypeError(
                    f"Component '{cls.__module__}.{cls.__qualname__}' does not have signature "
                    f"member annotations")
            if isinstance(signature, dict):
                signature = Signature(signature)
            elif not isinstance(signature, Signature):
                raise TypeError(f"Object {signature!r} is not a signature nor a dict")
        else:
            if signature is not None:
                raise TypeError(
                    f"Signature was passed as an argument, but component "
                    f"'{cls.__module__}.{cls.__qualname__}' already has signature "
                    f"member annotations")
            signature = Signature(members)

        self.__signature = signature
        for name in signature.members:
            if hasattr(self, name):
                raise NameError(f"Cannot initialize attribute for signature member {name!r} "
                                f"because an attribute with the same name already exists")
        self.__dict__.update(signature.members.create(path=()))

    @property
    def signature(self):
        """The signature of the component.

        .. important::

            Do not override this property. Once a component is constructed, its :attr:`signature`
            property must always return the same :class:`Signature` instance. The constructor
            can be used to customize a component's signature.
        """
        return self.__signature
