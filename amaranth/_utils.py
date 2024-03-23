import contextlib
import functools
import warnings
import linecache
import re
import unicodedata
from collections import OrderedDict
from collections.abc import Iterable


__all__ = ["flatten", "union", "final", "deprecated", "get_linter_options",
           "get_linter_option", "validate_name"]


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

_invalid_categories = {
    "Zs", # space separators
    "Zl", # line separators
    "Zp", # paragraph separators
    "Cc", # control codepoints (e.g. \0)
    "Cs", # UTF-16 surrogate pair codepoints (no thanks WTF-8)
    "Cn", # unassigned codepoints
}

def validate_name(name, what, none_ok=False, empty_ok=False):
    if not isinstance(name, str):
        if name is None and none_ok: return
        raise TypeError(f"{what} must be a string, not {name!r}")
    if name == "" and not empty_ok:
        raise NameError(f"{what} must be a non-empty string")

    # RTLIL allows bytes >= 33. In the same spirit we allow all characters that
    # Unicode does not declare as separator or control.
    for c in name:
        if unicodedata.category(c) in _invalid_categories:
            raise NameError(f"{what} {name!r} contains whitespace/control character {c!r}")
