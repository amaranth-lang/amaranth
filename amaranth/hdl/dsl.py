# TODO(amaranth-0.6): remove module

from .. import hdl as __hdl
from . import _dsl as __origin


__all__ = ["SyntaxError", "SyntaxWarning", "Module"]


def __getattr__(name):
    import warnings
    if name in __hdl.__dict__:
        if not (name.startswith("__") and name.endswith("__")):
            warnings.warn(f"instead of `{__name__}.{name}`, use `{__hdl.__name__}.{name}`",
                        DeprecationWarning, stacklevel=2)
        return getattr(__origin, name)
    elif name in __origin.__dict__:
        warnings.warn(f"name `{__name__}.{name}` is a private implementation detail and "
                      f"should not be imported",
                      DeprecationWarning, stacklevel=2)
        return getattr(__origin, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
