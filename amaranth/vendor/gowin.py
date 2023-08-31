# TODO(amaranth-0.5): remove module

import warnings
import importlib
from .. import vendor


def __getattr__(name):
    if name in ("GowinPlatform",):
        warnings.warn(f"instead of `{__name__}.{name}`, use `amaranth.vendor.{name}",
                      DeprecationWarning, stacklevel=2)
        return getattr(vendor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
