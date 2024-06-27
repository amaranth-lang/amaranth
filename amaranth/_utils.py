import contextlib
import functools
import warnings
import linecache
import operator
import re
from collections import OrderedDict
from collections.abc import Iterable


__all__ = ["to_binary", "flatten", "union", "final", "deprecated", "get_linter_options",
           "get_linter_option"]


def to_binary(n: int, width: int) -> str:
    """Formats ``n`` as exactly ``width`` binary digits, including when ``width`` is 0"""
    n = operator.index(n)
    width = operator.index(width)
    if n not in range(1 << width):
        raise ValueError(f"{n} does not fit in {width} bits")
    if width == 0:
        return ""
    return f"{n:0{width}b}"


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


def final(cls):
    def init_subclass():
        raise TypeError("Subclassing {}.{} is not supported"
                        .format(cls.__module__, cls.__qualname__))
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
