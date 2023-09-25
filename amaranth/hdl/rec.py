# TODO(amaranth-0.6): remove module

import warnings
import importlib
from . import _rec


__all__ = ["Direction", "DIR_NONE", "DIR_FANOUT", "DIR_FANIN", "Layout", "Record"]


def __dir__():
    return list({*globals(), *__all__})


def __getattr__(name):
    if name in __all__:
        warnings.warn(f"instead of `{__name__}.{name}`, use the `amaranth.lib.data` and "
                      f"`amaranth.lib.wiring` libraries as appropriate for the application; "
                      f"`{__name__}` will be removed in Amaranth 0.6",
                      DeprecationWarning, stacklevel=2)
        return getattr(_rec, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
