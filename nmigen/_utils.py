import contextlib
import functools
import warnings
from collections import OrderedDict
from collections.abc import Iterable
from contextlib import contextmanager

from .utils import *


__all__ = ["flatten", "union" , "log2_int", "bits_for", "memoize", "final", "deprecated"]


def flatten(i):
    for e in i:
        if isinstance(e, Iterable):
            yield from flatten(e)
        else:
            yield e


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
                f(*args, **kwargs)
        return decorator_like


def extend(cls):
    def decorator(f):
        if isinstance(f, property):
            name = f.fget.__name__
        else:
            name = f.__name__
        setattr(cls, name, f)
    return decorator
