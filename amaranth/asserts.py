from .hdl._ast import AnyConst, AnySeq, Initial
from . import hdl as __hdl


__all__ = ["AnyConst", "AnySeq", "Initial", "Assert", "Assume", "Cover"]


def __getattr__(name):
    import warnings
    if name in __hdl.__dict__ and name in __all__:
        if not (name.startswith("__") and name.endswith("__")):
            warnings.warn(f"instead of `{__name__}.{name}`, use `{__hdl.__name__}.{name}`",
                        DeprecationWarning, stacklevel=2)
        return getattr(__hdl, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")