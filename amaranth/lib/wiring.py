from collections.abc import Mapping
import enum
import types
import inspect
import re
import warnings

from ..hdl.ast import Shape, ShapeCastable, Const, Signal, Value, ValueCastable
from ..hdl.ir import Elaboratable
from .._utils import final


__all__ = ["In", "Out", "Signature", "connect", "flipped", "Component"]


class Flow(enum.Enum):
    Out = 0
    In = 1

    def flip(self):
        if self == Out:
            return In
        if self == In:
            return Out
        assert False # :nocov:

    def __call__(self, description, *, reset=None):
        return Member(self, description, reset=reset)

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


In = Flow.In
Out = Flow.Out


@final
class Member:
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
        return Member(self._flow.flip(), self._description, reset=self._reset,
                      _dimensions=self._dimensions)

    def array(self, *dimensions):
        for dimension in dimensions:
            if not (isinstance(dimension, int) and dimension >= 0):
                raise TypeError(f"Member array dimensions must be non-negative integers, "
                                f"not {dimension!r}")
        return Member(self._flow, self._description, reset=self._reset,
                      _dimensions=(*dimensions, *self._dimensions))

    @property
    def flow(self):
        return self._flow

    @property
    def is_port(self):
        return not isinstance(self._description, Signature)

    @property
    def is_signature(self):
        return isinstance(self._description, Signature)

    @property
    def shape(self):
        if self.is_signature:
            raise AttributeError(f"A signature member does not have a shape")
        return self._description

    @property
    def reset(self):
        if self.is_signature:
            raise AttributeError(f"A signature member does not have a reset value")
        return self._reset

    @property
    def signature(self):
        if self.is_port:
            raise AttributeError(f"A port member does not have a signature")
        if self.flow == Out:
            return self._description
        if self.flow == In:
            return self._description.flip()
        assert False # :nocov:

    @property
    def dimensions(self):
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
    pass


# Inherits from Mapping and not MutableMapping because it's only mutable in a very limited way
# and most of the methods (except for `update`) added by MutableMapping are useless.
@final
class SignatureMembers(Mapping):
    def __init__(self, members=()):
        self._dict = dict()
        self._frozen = False
        self += members

    def flip(self):
        return FlippedSignatureMembers(self)

    def __eq__(self, other):
        return (isinstance(other, (SignatureMembers, FlippedSignatureMembers)) and
                list(self.flatten()) == list(other.flatten()))

    def __contains__(self, name):
        return name in self._dict

    def _check_name(self, name):
        if not isinstance(name, str):
            raise TypeError(f"Member name must be a string, not {name!r}")
        if not re.match(r"^[A-Za-z][0-9A-Za-z_]*$", name):
            raise NameError(f"Member name '{name}' must be a valid, public Python attribute name")
        if name == "signature":
            raise NameError(f"Member name cannot be '{name}'")

    def __getitem__(self, name):
        self._check_name(name)
        if name not in self._dict:
            raise SignatureError(f"Member '{name}' is not a part of the signature")
        return self._dict[name]

    def __setitem__(self, name, member):
        self._check_name(name)
        if name in self._dict:
            raise SignatureError(f"Member '{name}' already exists in the signature and cannot "
                                 f"be replaced")
        if type(member) is not Member:
            raise TypeError(f"Assigned value {member!r} must be a member; "
                            f"did you mean In({member!r}) or Out({member!r})?")
        if self._frozen:
            raise SignatureError("Cannot add members to a frozen signature")
        self._dict[name] = member

    def __delitem__(self, name):
        raise SignatureError("Members cannot be removed from a signature")

    def __iter__(self):
        return iter(sorted(self._dict))

    def __len__(self):
        return len(self._dict)

    def __iadd__(self, members):
        for name, member in dict(members).items():
            self[name] = member
        return self

    @property
    def frozen(self):
        return self._frozen

    def freeze(self):
        self._frozen = True
        for member in self.values():
            if member.is_signature:
                member.signature.freeze()

    def flatten(self, *, path=()):
        for name, member in self.items():
            yield ((*path, name), member)
            if member.is_signature:
                yield from member.signature.members.flatten(path=(*path, name))

    def create(self, *, path=()):
        attrs = {}
        for name, member in self.items():
            def create_value(path):
                if member.is_port:
                    return Signal(member.shape, reset=member.reset,
                                  name="__".join(str(item) for item in path))
                if member.is_signature:
                    return member.signature.create(path=path)
                assert False # :nocov:
            def create_dimensions(dimensions, *, path):
                if not dimensions:
                    return create_value(path)
                dimension, *rest_of_dimensions = dimensions
                return [create_dimensions(rest_of_dimensions, path=(*path, index))
                        for index in range(dimension)]
            attrs[name] = create_dimensions(member.dimensions, path=(*path, name))
        return attrs

    def __repr__(self):
        frozen_repr = ".freeze()" if self._frozen else ""
        return f"SignatureMembers({self._dict}){frozen_repr}"


@final
class FlippedSignatureMembers(Mapping):
    def __init__(self, unflipped):
        self.__unflipped = unflipped

    def flip(self):
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

    def __iadd__(self, members):
        self.__unflipped.__iadd__({name: member.flip() for name, member in members.items()})
        return self

    @property
    def frozen(self):
        return self.__unflipped.frozen

    def freeze(self):
        self.__unflipped.freeze()

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
    def __subclasscheck__(cls, subclass):
        # `FlippedSignature` is a subclass of `Signature` or any of its subclasses because all of
        # them may return a Liskov-compatible instance of it from `self.flip()`.
        if subclass is FlippedSignature:
            return True
        return super().__subclasscheck__(subclass)

    def __instancecheck__(cls, instance):
        # `FlippedSignature` is an instance of a `Signature` or its subclass if the unflipped
        # object is.
        if type(instance) is FlippedSignature:
            return super().__instancecheck__(instance.flip())
        return super().__instancecheck__(instance)


class Signature(metaclass=SignatureMeta):
    def __init__(self, members):
        self.__members = SignatureMembers(members)

    def flip(self):
        return FlippedSignature(self)

    @property
    def members(self):
        return self.__members

    def __eq__(self, other):
        other_unflipped = other.flip() if type(other) is FlippedSignature else other
        if type(self) is type(other_unflipped) is Signature:
            # If both `self` and `other` are anonymous signatures, compare structurally.
            return self.members == other.members
        else:
            # Otherwise (if `self` refers to a derived class) compare by identity. This will
            # usually be overridden in a derived class.
            return self is other

    @property
    def frozen(self):
        return self.members.frozen

    def freeze(self):
        self.members.freeze()
        return self

    def flatten(self, obj):
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
                                                   path=(path, index))

            yield from iter_dimensions(value, dimensions=member.dimensions, path=path)

    def is_compliant(self, obj, *, reasons=None, path=("obj",)):
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

    def create(self, *, path=()):
        return Interface(self, path=path)

    def __repr__(self):
        if type(self) is Signature:
            return f"Signature({dict(self.members.items())})"
        return super().__repr__()


# To simplify implementation and reduce API surface area `FlippedSignature` is made final. This
# restriction could be lifted if there is a compelling use case.
@final
class FlippedSignature:
    def __init__(self, signature):
        object.__setattr__(self, "_FlippedSignature__unflipped", signature)

    def flip(self):
        return self.__unflipped

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

    # These methods do not access instance variables and so their implementation can be shared
    # between the normal and the flipped member collections.
    frozen = Signature.frozen
    freeze = Signature.freeze
    is_compliant = Signature.is_compliant
    create = Signature.create

    # FIXME: document this logic
    def __getattr__(self, name):
        value = getattr(self.__unflipped, name)
        if inspect.ismethod(value):
            return types.MethodType(value.__func__, self)
        else:
            return value

    def __setattr__(self, name, value):
        return setattr(self.__unflipped, name, value)

    def __repr__(self):
        return f"{self.__unflipped!r}.flip()"


class Interface:
    def __init__(self, signature, *, path):
        self.__dict__.update({
            "signature": signature,
            **signature.members.create(path=path)
        })


# To reduce API surface area `FlippedInterface` is made final. This restriction could be lifted
# if there is a compelling use case.
@final
class FlippedInterface:
    def __init__(self, interface):
        if not (hasattr(interface, "signature") and isinstance(interface.signature, Signature)):
            raise TypeError(f"flipped() can only flip an interface object, not {interface!r}")
        object.__setattr__(self, "_FlippedInterface__unflipped", interface)

    @property
    def signature(self):
        return self.__unflipped.signature.flip()

    def __eq__(self, other):
        return type(self) is type(other) and self.__unflipped == other.__unflipped

    # FIXME: document this logic
    def __getattr__(self, name):
        value = getattr(self.__unflipped, name)
        if inspect.ismethod(value):
            return types.MethodType(value.__func__, self)
        else:
            return value

    def __setattr__(self, name, value):
        return setattr(self.__unflipped, name, value)

    def __repr__(self):
        return f"flipped({self.__unflipped!r})"


def flipped(interface):
    if type(interface) is FlippedInterface:
        return interface._FlippedInterface__unflipped
    else:
        return FlippedInterface(interface)


@final
class ConnectionError(Exception):
    pass


def connect(m, *args, **kwargs):
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
        signatures[handle] = obj.signature.freeze()

    # Collate signatures and build connections.
    flattens = {handle: signature.members.flatten()
                for handle, signature in signatures.items()}
    connections = []
    # Each iteration of the outer loop is intended to connect several (usually a pair) members
    # to each other, e.g. an out member `[0].a` to an in member `[1].a`. However, because we
    # do not just check signatures for equality (in order to improve diagnostics), it is possible
    # that we will find that in `[0]`, the first member is `a`, and in `[1]`, the first member
    # is completely unrelated `[b]`. Since the assumption that all signatures are equal, or even
    # of equal length, cannot be made, it is necessary to simultaneously iterate (like with `zip`)
    # the signature of every object being connected, making sure each set of next members is
    # is_compliant with each other.
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
            # inis_compliant flow, kind (signature or port), signature, or shape. Collect all of
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
                            f"Cannot connect to the input member {_format_path(in_path)} that has "
                            f"a constant value {in_value.value!r}")
                    # If the output is a constant, the connection is legal only if the value is
                    # the same for both the input and the output.
                    if type(out_value) is Const and in_value.value != out_value.value:
                        raise ConnectionError(
                            f"Cannot connect input member {_format_path(in_path)} that has "
                            f"a constant value {in_value.value!r} to an output member "
                            f"{_format_path(out_path)} that has a differing constant value "
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
    def __init__(self):
        for name in self.signature.members:
            if hasattr(self, name):
                raise NameError(f"Cannot initialize attribute for signature member {name!r} "
                                f"because an attribute with the same name already exists")
        self.__dict__.update(self.signature.members.create())

    # TODO(py3.9): This should be a class method, but descriptors don't stack this way
    # in Python 3.8 and below.
    # @classmethod
    @property
    def signature(self):
        cls = type(self)
        signature = Signature({})
        for base in cls.mro()[:cls.mro().index(Component)]:
            for name, annot in getattr(base, "__annotations__", {}).items():
                if name.startswith("_"):
                    continue
                if (annot is Value or annot is Signal or annot is Const or
                        (isinstance(annot, type) and issubclass(annot, ValueCastable)) or
                        isinstance(annot, Signature)):
                    if isinstance(annot, type):
                        annot_repr = annot.__name__
                    else:
                        annot_repr = repr(annot)
                    # To suppress this warning in the rare cases where it is necessary (and naming
                    # the field with a leading underscore is infeasible), override the property.
                    warnings.warn(
                        message=f"Component '{cls.__module__}.{cls.__qualname__}' has "
                                f"an annotation '{name}: {annot_repr}', which is not "
                                f"a signature member; did you mean '{name}: In({annot_repr})' "
                                f"or '{name}: Out({annot_repr})'?",
                        category=SyntaxWarning,
                        stacklevel=2)
                elif type(annot) is Member:
                    signature.members[name] = annot
        if not signature.members:
            raise NotImplementedError(
                f"Component '{cls.__module__}.{cls.__qualname__}' does not have signature member "
                f"annotations")
        return signature
