import contextlib
import functools
import warnings
import linecache
import re
from abc import ABCMeta
from collections import OrderedDict
from collections.abc import Iterable

from .utils import *


__all__ = ["flatten", "union" , "log2_int", "bits_for", "memoize", "final", "deprecated",
           "get_linter_options", "get_linter_option", "TypePatched", "ABCMetaPatched"]


def flatten(i):
    for e in i:
        if isinstance(e, str) or not isinstance(e, Iterable):
            yield e
        else:
            yield from flatten(e)


def union(i, start=None):
    r = start
    for e in i:
        if r is None:
            r = e
        else:
            r |= e
    return r


def memoize(f):
    memo = OrderedDict()
    @functools.wraps(f)
    def g(*args):
        if args not in memo:
            memo[args] = f(*args)
        return memo[args]
    return g


def final(cls):
    def init_subclass():
        raise TypeError("Subclassing {}.{} is not supported"
                        .format(cls.__module__, cls.__name__))
    cls.__init_subclass__ = init_subclass
    return cls


def deprecated(message, stacklevel=2):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            warnings.warn(message, DeprecationWarning, stacklevel=stacklevel)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def _ignore_deprecated(f=None):
    if f is None:
        @contextlib.contextmanager
        def context_like():
            with warnings.catch_warnings():
                warnings.filterwarnings(action="ignore", category=DeprecationWarning)
                yield
        return context_like()
    else:
        @functools.wraps(f)
        def decorator_like(*args, **kwargs):
            with warnings.catch_warnings():
                warnings.filterwarnings(action="ignore", category=DeprecationWarning)
                return f(*args, **kwargs)
        return decorator_like


def extend(cls):
    def decorator(f):
        if isinstance(f, property):
            name = f.fget.__name__
        else:
            name = f.__name__
        setattr(cls, name, f)
    return decorator


def get_linter_options(filename):
    first_line = linecache.getline(filename, 1)
    if first_line:
        match = re.match(r"^#\s*amaranth:\s*((?:\w+=\w+\s*)(?:,\s*\w+=\w+\s*)*)\n$", first_line)
        if match:
            return dict(map(lambda s: s.strip().split("=", 2), match.group(1).split(",")))
    return dict()


def get_linter_option(filename, name, type, default):
    options = get_linter_options(filename)
    if name not in options:
        return default

    option = options[name]
    if type is bool:
        if option in ("1", "yes", "enable"):
            return True
        if option in ("0", "no", "disable"):
            return False
        return default
    if type is int:
        try:
            return int(option, 0)
        except ValueError:
            return default
    assert False


class BindToReceiverMethod:
    """
    A descriptor which binds to a given method on its receiver, even if the
    receiver is the defining class for that method.

    This is a workaround for https://github.com/python/cpython/issues/81062;
    namely, given these classes::

        class C(metaclass=ABCMeta): pass
        class SC(C, type): pass

    then ``isinstance(obj, C)`` for any obj that isn't ``C()`` will raise a
    TypeError in the middle of :meth:`ABCMeta.__subclasscheck__`.

    :meth:`ABCMeta.__subclasscheck__` calls ``cls.__subclasses__()`` towards the
    end, but if ``cls`` ends up being a metaclass, such as ``SC`` here, then
    we're calling the inherited instance method :meth:`type.__subclasses__`
    without an instance.

    Similarly, ``isinstance(obj, SC)`` for anything that isn't an ``SC``
    instance will fail in :meth:`ABCMeta.__instancecheck__` when it tries to
    call ``cls.__subclasscheck__()`` and invokes the inherited instance method
    :meth:`ABCMeta.__subclasscheck__` without an instance.

    This descriptor gives the instance-bound variant when accessed through an
    instance, and the class-bound variant when accessed without, and can be used
    for such methods called by ABCMeta.  We must search the MRO ourselves to
    avoid calling ourselves.

    ABCMeta works hard to cache its results, which includes calls to the methods
    we use this descriptor with, so cost of lookup is rendered negligible.  We
    cannot meaningfully cache the results ourselves without loss of generality
    and possible surprise later.
    """
    __slots__ = ("name",)

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        objtype = objtype or type(obj)
        for target in objtype.__mro__:
            fn = vars(target).get(self.name)
            if fn is not None and not isinstance(fn, BindToReceiverMethod):
                break
        else:
            descr = f"'{objtype.__name__}' object" if obj is not None else f"type object '{objtype.__name__}'"
            raise AttributeError(f"{descr} has no attribute '{self.name}'")

        if obj is not None:
            return fn.__get__(obj, objtype)
        else:
            return fn.__get__(objtype)


class TypePatched(type):
    # Metaclass which patches ``__subclasses__`` and ``__subclasscheck__`` to
    # address ``ABCMeta.__subclasscheck__`` issue described in
    # :class:`BindToReceiverMethod`.
    #
    # Use with metaclasses that don't want all of :class:`ABCMeta`, but do have
    # a superclass that itself uses :class:`ABCMeta` (or a subclass of it).
    __subclasses__ = BindToReceiverMethod()
    __subclasscheck__ = BindToReceiverMethod()


class ABCMetaPatched(TypePatched, ABCMeta):
    # :class:`ABCMeta` subclass which includes :class:`TypePatched`. This should
    # be used instead of :class:`ABCMeta` whenever a subclass may also be a
    # metaclass.
    pass
